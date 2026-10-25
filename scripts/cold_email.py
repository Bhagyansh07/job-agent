"""Cold-email queue: Apollo lead discovery + drafts + gated sending.

    python scripts/cold_email.py apollo --role "software engineer" --limit 20
    python scripts/cold_email.py apollo --company "Acme" --limit 10 --reveal --queue
    python scripts/cold_email.py queue --company "Acme" --email hr@acme.com --name "Rahul" --title "HR" --source apollo
    python scripts/cold_email.py queued [--limit 20]
    python scripts/cold_email.py draft --id <id> --subject "..." --body-file state/tmp/email_<id>.txt
    python scripts/cold_email.py review [--limit 10]
    python scripts/cold_email.py send --id <id>
    python scripts/cold_email.py count
    python scripts/cold_email.py resolve --domain acme.com [--company "Acme"]
    python scripts/cold_email.py mark --id <id> --status replied|failed|skipped

Rules enforced in code (not just in prompts):
- mode: draft (config/cold_email.yaml) -> send refuses, nothing leaves the machine
- one email per address, ever (dedupe across queued/draft_ready/sent/replied)
- warm-up ramp from the FIRST send ever: days 1-7 max 5/day, days 8-14 max 15/day, then daily_cap
- min_gap_hours between two sends (no bursts)
- strict hours from profile.yaml active_hours_ist
- DRY_RUN=1 prints what would happen and sends nothing
- sends use the gmail.send scope; a missing grant prints REAUTH_NEEDED instead of crashing

Exit codes: 0 ok, 2 usage/validation, 3 limit/hours/gap/mode block, 4 duplicate,
5 DRY_RUN hold, 6 auth/send block.
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from common import ROOT, cfg, today, safe_cell, is_dry

IST = ZoneInfo("Asia/Kolkata")
F = ROOT / "tracker" / "cold_emails.csv"
LOCK = ROOT / "state" / "cold_email.lock"
CFG = ROOT / "config" / "cold_email.yaml"
DRAFTS = ROOT / "tracker" / "email_drafts"
ACTIVITY = ROOT / "state" / "cold_email_activity.jsonl"
ACTIVITY_LOCK = ROOT / "state" / "cold_email_activity.lock"
CYCLE_WINDOW_MIN = 15
COLS = ["id", "queued_date", "company", "contact_name", "contact_title", "email", "source", "notes",
        "status", "subject", "sent_at", "last_sent_at", "apollo_id", "linkedin"]
SAFE_FIELDS = {"company", "contact_name", "contact_title", "notes"}
STATUSES = {"queued", "draft_ready", "sent", "replied", "failed", "skipped"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


# ---------------------------------------------------------------- config
def cc() -> dict:
    if CFG.exists():
        return yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
    return (cfg("profile.yaml").get("outreach", {}) or {}).get("cold_email", {}) or {}


def mode() -> str:
    return str(cc().get("mode", "draft")).strip().lower()


def limits() -> tuple[int, dict]:
    c = cc()
    cap = int(c.get("daily_cap", 25))
    w1, w2 = int(c.get("warmup_week1", 5)), int(c.get("warmup_week2", 15))
    return cap, {"w1": w1, "w2": w2, "gap_h": float(c.get("min_gap_hours", 4)),
                 "max_cycle": int(c.get("max_per_cycle", 3))}


# ---------------------------------------------------------------- storage
class FileLock:
    """Tiny cross-process lock; a lock older than 10 minutes is treated as stale."""

    def __init__(self, path: Path, timeout: float = 30.0):
        self.path, self.timeout = path, timeout

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 600:
                        self.path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    raise RuntimeError(f"LOCK_TIMEOUT {self.path}")
                time.sleep(0.2)

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


def rows_unlocked() -> list[dict[str, str]]:
    if not F.exists():
        return []
    with F.open(encoding="utf-8-sig", newline="") as fh:
        return [{c: (r.get(c) or "") for c in COLS} for r in csv.DictReader(fh)]


def save_unlocked(rs: list[dict[str, str]]) -> None:
    F.parent.mkdir(parents=True, exist_ok=True)
    tmp = F.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rs:
            # only display-only fields are escaped; email/subject are reused verbatim when sending
            w.writerow({c: (safe_cell(r.get(c, "")) if c in SAFE_FIELDS else (r.get(c, "") or ""))
                        for c in COLS})
    os.replace(tmp, F)


def next_id(rs: list[dict[str, str]]) -> str:
    seq = 1 + max([int(r["id"].split("-")[-1]) for r in rs
                   if r["id"] and r["id"].split("-")[-1].isdigit()] or [0])
    return f"{today()}-{seq:03d}"


def add_row(rs: list[dict[str, str]], **kw) -> str:
    rid = next_id(rs)
    rs.append({"id": rid, "queued_date": today(), "company": kw.get("company", ""),
               "contact_name": kw.get("name", ""), "contact_title": kw.get("title", ""),
               "email": kw.get("email", "").strip().lower(), "source": kw.get("source", ""),
               "notes": kw.get("notes", ""), "status": "queued", "subject": "",
               "sent_at": "", "last_sent_at": "", "apollo_id": kw.get("apollo_id", ""),
               "linkedin": kw.get("linkedin", "")})
    return rid


# ---------------------------------------------------------------- limits
def day_index(rs: list[dict[str, str]]) -> int:
    sent = sorted(r["sent_at"][:10] for r in rs if r["sent_at"])
    if not sent:
        return -1
    return (dt.date.fromisoformat(today()) - dt.date.fromisoformat(sent[0])).days


def daily_limit(rs: list[dict[str, str]]) -> int:
    cap, w = limits()
    d = day_index(rs)
    if d < 0 or d < 7:
        return w["w1"]
    if d < 14:
        return w["w2"]
    return cap


def sent_today(rs: list[dict[str, str]]) -> int:
    # replied/failed rows still count: the email did leave the machine that day
    return sum(1 for r in rs if r["sent_at"][:10] == today())


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def hours_ok() -> bool:
    h = cfg("profile.yaml").get("active_hours_ist") or {}
    lo, hi = h.get("from", "08:00"), h.get("to", "23:30")
    return lo <= now_ist().strftime("%H:%M") <= hi


def dry() -> bool:
    return is_dry()


def cycle_quota() -> tuple[bool, str]:
    """max_per_cycle = at most N drafts+sends inside one rolling 15-minute window."""
    _, w = limits()
    n, cutoff = 0, now_ist().timestamp() - CYCLE_WINDOW_MIN * 60
    try:
        if ACTIVITY.exists():
            for line in ACTIVITY.read_text(encoding="utf-8").splitlines()[-200:]:
                try:
                    if dt.datetime.fromisoformat(json.loads(line)["ts"]).timestamp() >= cutoff:
                        n += 1
                except Exception:
                    continue
    except Exception:
        n = 0
    if n >= w["max_cycle"]:
        return False, f"CYCLE_LIMIT {n}/{w['max_cycle']} in last {CYCLE_WINDOW_MIN} min"
    return True, ""


def record_activity(kind: str, rid: str) -> None:
    with FileLock(ACTIVITY_LOCK):
        ACTIVITY.parent.mkdir(parents=True, exist_ok=True)
        with ACTIVITY.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now_ist().isoformat(timespec="seconds"),
                                "kind": kind, "id": rid}) + "\n")


# ---------------------------------------------------------------- apollo
def _apollo_key() -> str:
    return os.environ.get("APOLLO_API_KEY", "").strip()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        raise RuntimeError(f"APOLLO_REDIRECT_BLOCKED: {newurl}")


def apollo_request(path_key: str, payload: dict) -> dict:
    a = cc().get("apollo", {}) or {}
    base = str(a.get("base_url", "https://api.apollo.io/v1")).rstrip("/")
    path = str(a.get(path_key, "/mixed_people/search"))
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Cache-Control": "no-cache",
                 "x-api-key": _apollo_key()},
        method="POST",
    )
    try:
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"APOLLO_HTTP_{exc.code}: {body}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"APOLLO_FAILED: {type(exc).__name__}: {exc}") from exc


def cmd_apollo(a) -> int:
    if not _apollo_key():
        print("APOLLO_NO_KEY: APOLLO_API_KEY missing in .env")
        print("Free account: https://app.apollo.io  (register with a WORK/college email;")
        print("plain Gmail blocks people-search on the free plan).")
        print("Fallback without Apollo: python scripts/cold_email.py resolve --domain <company.com>")
        return 2
    ac = cc().get("apollo", {}) or {}
    if not ac.get("enabled", True):
        print("APOLLO_DISABLED in config/cold_email.yaml")
        return 2
    if a.reveal and not ac.get("reveal_emails", True):
        print("APOLLO_REVEAL_DISABLED: set apollo.reveal_emails: true in config/cold_email.yaml")
        return 2

    titles = [a.role] if a.role else list(ac.get("person_titles") or [])
    payload = {
        "person_titles": titles,
        "person_locations": list(ac.get("person_locations") or ["India"]),
        "organization_num_employees_ranges": list(ac.get("organization_num_employees_ranges") or []),
        "page": 1,
        "per_page": max(1, min(int(a.limit or ac.get("per_page", 25)), 100)),
    }
    if a.company:
        payload["q_organization_name"] = a.company
    if a.domain:
        payload["q_organization_domains"] = a.domain
    for k in ("person_locations", "organization_num_employees_ranges"):
        if not payload[k]:
            payload.pop(k, None)

    print(f"apollo search: titles={titles} company={a.company or '-'} domain={a.domain or '-'}")
    data = apollo_request("search_path", payload)
    people = data.get("people") or data.get("contacts") or []
    if not people:
        print("APOLLO_EMPTY: no people returned (check filters / plan / work-email requirement)")
        print(json.dumps(data, ensure_ascii=False)[:400])
        return 0

    reveal_budget = int(ac.get("max_reveals_per_run", 5)) if (a.reveal or a.queue) else 0
    if a.queue and not a.reveal:
        reveal_budget = 0
    reveals = 0
    queued = 0
    out = []
    for p in people:
        org = p.get("organization") or {}
        email = (p.get("email") or "").strip().lower()
        if not email and reveal_budget and reveals < reveal_budget:
            try:
                m = apollo_request("match_path", {"id": p.get("id"), "reveal_personal_emails": False})
                email = ((m.get("person") or {}).get("email") or "").strip().lower()
                reveals += 1
            except RuntimeError as exc:
                print(f"  reveal failed for {p.get('name')}: {exc}")
        rec = {
            "id": p.get("id") or "",
            "name": p.get("name") or " ".join(filter(None, [p.get("first_name"), p.get("last_name")])),
            "title": p.get("title") or "",
            "company": org.get("name") or "",
            "domain": org.get("primary_domain") or "",
            "linkedin": p.get("linkedin_url") or "",
            "email": email,
        }
        out.append(rec)
        print(f"{rec['name']} | {rec['title']} | {rec['company']} | "
              f"{rec['email'] or '(no email - use --reveal, costs 1 credit)'} | {rec['linkedin']}")

    if a.queue:
        t = cc().get("targeting", {}) or {}
        never = [str(p).lower() for p in (t.get("never_email") or [])]
        dom_cap = int(t.get("max_per_domain", 1))

        def active(r):
            return r["status"] in ("queued", "draft_ready", "sent", "replied") or bool(r.get("sent_at"))

        with FileLock(LOCK):
            rs = rows_unlocked()
            for rec in out:
                addr = rec["email"]
                if not addr or not EMAIL_RE.match(addr):
                    continue
                if any(addr.startswith(p) for p in never):
                    continue
                if any(r["email"].lower() == addr and active(r) for r in rs):
                    continue
                domain = addr.split("@")[-1]
                if sum(1 for r in rs
                       if r["email"].lower().endswith("@" + domain) and active(r)) >= dom_cap:
                    continue
                add_row(rs, company=rec["company"], name=rec["name"], title=rec["title"],
                        email=addr, source="apollo", notes=rec["domain"],
                        apollo_id=rec.get("id", ""), linkedin=rec["linkedin"])
                queued += 1
            save_unlocked(rs)
        print(f"\nQUEUED {queued} new contact(s); reveals used this run: {reveals}")
    else:
        print(f"\nfound={len(out)} with_email={sum(1 for r in out if r['email'])} reveals_used={reveals}")
        print("Nothing queued. Add --queue (and optionally --reveal) to store them.")
    return 0


# ---------------------------------------------------------------- commands
def cmd_queue(a) -> int:
    email = (a.email or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        print(f"INVALID_EMAIL: {a.email}")
        return 2
    bad = [p for p in (cc().get("targeting", {}) or {}).get("never_email", []) if email.startswith(p)]
    if bad:
        print(f"BLOCKED_MAILBOX: {email} matches never_email rule ({bad[0]})")
        return 2
    with FileLock(LOCK):
        rs = rows_unlocked()
        if any(r["email"].lower() == email and
               (r["status"] in ("queued", "draft_ready", "sent", "replied") or r.get("sent_at"))
               for r in rs):
            print(f"DUPLICATE: {email} already queued/sent")
            return 4
        domain = email.split("@")[-1]
        cap = int((cc().get("targeting", {}) or {}).get("max_per_domain", 1))
        same_domain = sum(1 for r in rs if r["email"].lower().endswith("@" + domain)
                          and (r["status"] in ("queued", "draft_ready", "sent", "replied")
                               or r.get("sent_at")))
        if same_domain >= cap:
            print(f"DOMAIN_LIMIT: {domain} already has {same_domain} contact(s) (max {cap})")
            return 4
        rid = add_row(rs, company=a.company, name=a.name or "", title=a.title or "",
                      email=email, source=a.source or "", notes=a.notes or "",
                      linkedin=a.linkedin or "")
        save_unlocked(rs)
    print(f"QUEUED {rid} {email}")
    return 0


def cmd_queued(a) -> int:
    rs = rows_unlocked()
    pend = [r for r in rs if r["status"] in ("queued", "draft_ready")]
    for r in pend[: a.limit]:
        print(f"{r['id']} | {r['status']} | {r['company']} | {r['contact_name']} ({r['contact_title']}) "
              f"| {r['email']} | subj: {r['subject']}")
    print(f"pending={len(pend)} draft_ready={sum(1 for r in pend if r['status'] == 'draft_ready')}")
    return 0


def _copy_limits() -> dict:
    return cc().get("copy", {}) or {}


def cmd_draft(a) -> int:
    body_path = ROOT / a.body_file
    if not body_path.exists():
        print(f"BODY_MISSING: {body_path}")
        return 2
    body = body_path.read_text(encoding="utf-8-sig").strip()
    if not body:
        print("BODY_EMPTY")
        return 2
    subject = a.subject.strip()
    if not subject:
        print("SUBJECT_EMPTY")
        return 2
    if "\r" in subject or "\n" in subject:
        print("SUBJECT_HAS_NEWLINE: header injection blocked")
        return 2
    cl = _copy_limits()
    smax = int(cl.get("subject_max_chars", 60))
    wmax = int(cl.get("body_max_words", 120))
    if len(subject) > smax:
        print(f"SUBJECT_TOO_LONG: {len(subject)} > {smax}")
        return 2
    words = len(re.findall(r"\S+", body))
    if words > wmax:
        print(f"BODY_TOO_LONG: {words} words > {wmax}")
        return 2
    with FileLock(LOCK):
        rs = rows_unlocked()
        row = next((r for r in rs if r["id"] == a.id), None)
        if not row:
            print(f"NOT_FOUND: {a.id}")
            return 2
        if row["status"] not in ("queued", "draft_ready"):
            print(f"BAD_STATUS: {row['status']}")
            return 2
        if any(ch in subject + body for ch in ("\u2014", "\u2013")):
            print("STYLE_DASH: em dash or en dash found in subject/body (hard rule 20)")
            return 2
        t = cc().get("targeting", {}) or {}
        if t.get("require_personalization", False):
            name = (row.get("contact_name") or "").strip()
            first = name.split()[0].lower() if name else ""
            comp = (row.get("company") or "").strip().lower()
            low = body.lower()
            if not ((first and first in low) or (comp and comp in low)):
                print("PERSONALIZATION_MISSING: mention the contact's first name or the company")
                return 2
        ok, why = cycle_quota()
        if not ok:
            print(why)
            return 3
        DRAFTS.mkdir(parents=True, exist_ok=True)
        (DRAFTS / f"{a.id}.txt").write_text(body, encoding="utf-8")
        row["status"], row["subject"] = "draft_ready", subject
        save_unlocked(rs)
    record_activity("draft", a.id)
    print(f"DRAFT_READY {a.id} ({words} words, subject {len(subject)} chars)")
    return 0


def cmd_review(a) -> int:
    rs = rows_unlocked()
    ready = [r for r in rs if r["status"] == "draft_ready"][: a.limit]
    if not ready:
        print("NO_DRAFTS")
        return 0
    for r in ready:
        print(f"\n[{r['id']}] {r['contact_name']} ({r['contact_title']}) @ {r['company']} <{r['email']}>")
        print(f"Subject: {r['subject']}")
        p = DRAFTS / f"{r['id']}.txt"
        print(p.read_text(encoding="utf-8-sig") if p.exists() else "(body file missing)")
    print(f"\ndrafts={len(ready)} mode={mode()}")
    return 0


def cmd_send(a) -> int:
    if mode() != "auto":
        print("MODE_DRAFT: nothing sent. Review it, then set mode: auto in config/cold_email.yaml")
        return 3
    if not hours_ok():
        h = cfg("profile.yaml").get("active_hours_ist") or {}
        print(f"LIMIT outside hours ({now_ist().strftime('%H:%M')} IST, "
              f"allowed {h.get('from', '08:00')}-{h.get('to', '23:30')})")
        return 3
    with FileLock(LOCK):
        rs = rows_unlocked()
        row = next((r for r in rs if r["id"] == a.id), None)
        if not row:
            print(f"NOT_FOUND: {a.id}")
            return 2
        if row["status"] != "draft_ready":
            print(f"BAD_STATUS: {row['status']} (need draft_ready)")
            return 2
        body_file = DRAFTS / f"{a.id}.txt"
        if not body_file.exists():
            print(f"BODY_MISSING: {body_file}")
            return 2
        limit = daily_limit(rs)
        n = sent_today(rs)
        if n >= limit:
            print(f"LIMIT cold_email {n}/{limit} today (warm-up ramp applies until day 15)")
            return 3
        gap_h = limits()[1]["gap_h"]
        last = [r["sent_at"] for r in rs if r["sent_at"]]
        if last:
            last_dt = dt.datetime.fromisoformat(max(last))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=IST)
            elapsed = (now_ist() - last_dt).total_seconds() / 3600.0
            if elapsed < gap_h:
                print(f"GAP {elapsed:.1f}h since last send; minimum {gap_h}h (no bursts)")
                return 3
        if dry():
            print(f"DRY_RUN_HELD {a.id} -> {row['email']} (would send, limit {n + 1}/{limit})")
            return 5
        ok, why = cycle_quota()
        if not ok:
            print(why)
            return 3
        subject, body = row["subject"], body_file.read_text(encoding="utf-8")
        try:
            from google_auth import creds_send
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
            svc = build("gmail", "v1", credentials=creds_send(interactive=False),
                        cache_discovery=False)
            msg = MIMEText(body, "plain", "utf-8")
            msg["To"] = row["email"]
            msg["Subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        except RuntimeError as exc:
            print(str(exc))
            return 6
        except HttpError as exc:
            code = getattr(getattr(exc, "resp", None), "status", "?")
            row["status"], row["notes"] = "failed", f"gmail http {code}: {row['notes']}"[:400]
            save_unlocked(rs)
            print(f"SEND_FAILED {a.id}: HTTP {code}")
            return 6
        except Exception as exc:  # noqa: BLE001
            row["status"] = "failed"
            save_unlocked(rs)
            print(f"SEND_FAILED {a.id}: {type(exc).__name__}: {str(exc)[:160]}")
            return 6
        row["status"] = "sent"
        row["sent_at"] = now_ist().isoformat(timespec="seconds")
        row["last_sent_at"] = row["sent_at"]
        save_unlocked(rs)
    record_activity("send", a.id)
    print(f"SENT {a.id} -> {row['email']} ({n + 1}/{limit} today)")
    return 0


def cmd_count(a) -> int:
    rs = rows_unlocked()
    n, limit = sent_today(rs), daily_limit(rs)
    d = day_index(rs)
    phase = "warm-up week 1" if d < 7 else ("warm-up week 2" if d < 14 else "warmed up")
    print(f"mode={mode()} sent_today={n} limit={limit} "
          f"({phase}, day {max(d, 0) + 1} since first send) pending="
          f"{sum(1 for r in rs if r['status'] in ('queued', 'draft_ready'))}")
    return 0


def cmd_resolve(a) -> int:
    """Hunter.io if HUNTER_API_KEY is set. No pattern guessing: generic inboxes are policy-blocked."""
    domain = (a.domain or "").strip().lower().lstrip("@")
    if "." not in domain:
        print(f"INVALID_DOMAIN: {a.domain}")
        return 2
    key = os.environ.get("HUNTER_API_KEY", "").strip()
    if key:
        try:
            url = (f"https://api.hunter.io/v2/domain-search?domain={domain}"
                   f"&api_key={key}&limit=5")
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            for m in (data.get("data", {}).get("emails") or [])[:5]:
                addr = (m.get("value") or "").lower()
                if addr and EMAIL_RE.match(addr):
                    print(f"{addr} | {m.get('first_name') or ''} {m.get('last_name') or ''} | "
                          f"{m.get('position') or ''} | verified")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"HUNTER_FAILED ({type(exc).__name__}); no pattern fallback")
    print(f"NO_VERIFIED_EMAIL: {domain}")
    print("Pattern guesses (hello@, careers@, jobs@, contact@) are blocked by the generic-mailbox policy.")
    print("Find a named contact with Apollo or LinkedIn, then queue that address.")
    return 2


def cmd_mark(a) -> int:
    if a.status not in STATUSES:
        print(f"BAD_STATUS: {a.status}")
        return 2
    with FileLock(LOCK):
        rs = rows_unlocked()
        row = next((r for r in rs if r["id"] == a.id), None)
        if not row:
            print(f"NOT_FOUND: {a.id}")
            return 2
        BLOCKED = {("sent", "queued"), ("sent", "draft_ready"),
                   ("replied", "queued"), ("replied", "draft_ready")}
        if (row["status"], a.status) in BLOCKED or (row.get("sent_at") and a.status in ("queued", "draft_ready")):
            print(f"BAD_TRANSITION: {row['status']} -> {a.status} would allow a second email to the same address")
            return 2
        row["status"] = a.status
        save_unlocked(rs)
    print(f"MARKED {a.id} -> {a.status}")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Cold-email queue (draft-first, gated sending)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("apollo", help="find contacts with Apollo.io")
    p.add_argument("--role", default="", help="job title filter, e.g. 'software engineer'")
    p.add_argument("--company", default="")
    p.add_argument("--domain", default="")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--reveal", action="store_true", help="reveal emails (1 credit each)")
    p.add_argument("--queue", action="store_true", help="store usable emails in the queue")

    q = sub.add_parser("queue")
    q.add_argument("--company", required=True)
    q.add_argument("--email", required=True)
    q.add_argument("--name", default="")
    q.add_argument("--title", default="")
    q.add_argument("--source", default="")
    q.add_argument("--notes", default="")
    q.add_argument("--linkedin", default="")

    ql = sub.add_parser("queued")
    ql.add_argument("--limit", type=int, default=20)

    d = sub.add_parser("draft")
    d.add_argument("--id", required=True)
    d.add_argument("--subject", required=True)
    d.add_argument("--body-file", required=True)

    rv = sub.add_parser("review")
    rv.add_argument("--limit", type=int, default=10)

    s = sub.add_parser("send")
    s.add_argument("--id", required=True)

    sub.add_parser("count")

    r = sub.add_parser("resolve")
    r.add_argument("--domain", required=True)

    m = sub.add_parser("mark")
    m.add_argument("--id", required=True)
    m.add_argument("--status", required=True)

    a = ap.parse_args()
    return {"apollo": cmd_apollo, "queue": cmd_queue, "queued": cmd_queued, "draft": cmd_draft,
            "review": cmd_review, "send": cmd_send, "count": cmd_count, "resolve": cmd_resolve,
            "mark": cmd_mark}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
