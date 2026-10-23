"""Recruiter email sheet: fetch, audit, and queue contacts for cold email.

The sheet is public, so no Google OAuth is needed (gviz CSV endpoint).

    python scripts/recruiter_sheet.py fetch
    python scripts/recruiter_sheet.py stats
    python scripts/recruiter_sheet.py verify --limit 40
    python scripts/recruiter_sheet.py queue --limit 25 --max-per-domain 1
    python scripts/recruiter_sheet.py queue --limit 10 --roles "talent,recruit,people" --verify

Safety rules enforced here:
- only valid, unique addresses
- generic mailboxes (info@, hr@, careers@ ...) are skipped
- one contact per company domain by default (no blasting a company)
- optional MX check so dead domains never enter the queue
- never queues an address that is already queued, sent or replied in tracker/cold_emails.csv
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from common import ROOT

SID = "1pF_d6Zu5eWoKtAo5K6bFJ6d2BYA0m8VEXOVf2NHtiuA"
URL = f"https://docs.google.com/spreadsheets/d/{SID}/gviz/tq?tqx=out:csv"
RAW = ROOT / "state" / "import" / "recruiter_sheet.csv"
MX_CACHE = ROOT / "state" / "import" / "domain_mx.json"
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
GENERIC = re.compile(r"^(info|hr|careers|jobs|contact|support|hello|admin|sales|marketing|team|recruit|"
                     r"talent|noreply|no-reply|enquiry|enquiries|query|office)\d*$")
SERVICE = ("bpo", "staffing", "manpower", "outsourcing", "recruitment", "consultancy", "consulting",
           "infotech", "it services", "kpo", "bpo/ites")
PRODUCT = ("ai", "labs", "software", "cloud", "data", "fintech", "health", "edtech", "saas", "analytics",
           "robotics", "payments", "security", "platform", "studio", "systems", "digital", "app",
           "technologies", "tech", "network", "cyber", "mobile", "games", "media", "commerce")


def _field(row: dict, *names: str) -> str:
    for n in names:
        if n in row and row[n]:
            return str(row[n]).strip()
    return ""


def load() -> list[dict]:
    if not RAW.exists():
        fetch()
    raw = RAW.read_text(encoding="utf-8-sig")
    out = []
    for r in csv.DictReader(io.StringIO(raw)):
        email = _field(r, "Email", "email", "E-mail").lower()
        out.append({
            "sno": _field(r, "SNo"),
            "name": _field(r, "Name", "name"),
            "email": email,
            "title": _field(r, "Click Here Title", "Title", "Role", "Designation"),
            "company": _field(r, "Company", "company", "Organisation"),
        })
    return out


def fetch() -> list[dict]:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        raw = resp.read().decode("utf-8-sig", "replace")
    RAW.write_text(raw, encoding="utf-8", newline="")
    rows = load()
    print(f"FETCHED {len(rows)} rows -> {RAW.relative_to(ROOT)}")
    return rows


def score(company: str) -> int:
    c = company.lower()
    s = 0
    if any(k in c for k in SERVICE):
        s -= 3
    if any(k in c for k in PRODUCT):
        s += 1
    return s


def clean(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        e = r["email"]
        if not EMAIL_RE.match(e) or len(e) > 254:
            continue
        local, _, domain = e.partition("@")
        if GENERIC.match(local):
            continue
        if e in seen:
            continue
        seen.add(e)
        r = dict(r)
        r["domain"] = domain
        r["score"] = score(r["company"])
        out.append(r)
    return out


def cmd_stats(a) -> int:
    rows = clean(load())
    dom = collections.Counter(r["domain"] for r in rows)
    roles = collections.Counter(r["title"] or "(none)" for r in rows)
    print(f"usable={len(rows)} unique_domains={len(dom)}")
    print("generic/service-heavy domains:", sum(1 for r in rows if r["score"] < 0))
    print("top domains:", dom.most_common(8))
    print("top titles:", roles.most_common(10))
    print("priority product companies:", [r["company"] for r in sorted(rows, key=lambda x: -x["score"])[:10]])
    return 0


def _probe_mx(domain: str) -> bool | None:
    """True = MX exists, False = domain definitely has no mail, None = could not tell."""
    try:
        res = subprocess.run(["nslookup", "-type=MX", domain], capture_output=True, text=True,
                             timeout=12, errors="replace")
        low = (res.stdout + res.stderr).lower()
        if "mail exchanger" in low or "mx preference" in low:
            return True
        if ("non-existent domain" in low or "nxdomain" in low or "can't find" in low
                or "no answer" in low):
            return False
        return None
    except Exception:  # noqa: BLE001
        return None


def mx_ok(domain: str, cache: dict) -> bool | None:
    if domain in cache:
        return cache[domain]
    ok = _probe_mx(domain)
    if ok is None:            # one retry; a transient DNS hiccup must not blacklist a domain
        time.sleep(0.4)
        ok = _probe_mx(domain)
    if ok is not None:
        cache[domain] = ok
    return ok


def save_mx(cache: dict) -> None:
    MX_CACHE.parent.mkdir(parents=True, exist_ok=True)
    MX_CACHE.write_text(json.dumps(cache, indent=0), encoding="utf-8")


def cmd_verify(a) -> int:
    rows = clean(load())
    cache = json.loads(MX_CACHE.read_text()) if MX_CACHE.exists() else {}
    checked = good = bad = unknown = 0
    for r in rows[: a.limit]:
        ok = mx_ok(r["domain"], cache)
        checked += 1
        if ok is True:
            good += 1
        elif ok is False:
            bad += 1
            print(f"NO_MX {r['email']} ({r['company']})")
        else:
            unknown += 1
    save_mx(cache)
    print(f"checked={checked} mx_ok={good} no_mx={bad} unknown={unknown}")
    return 0


def cmd_queue(a) -> int:
    from cold_email import EMAIL_RE as CE_RE  # noqa: F401  (same rules)
    from cold_email import FileLock, LOCK, add_row, rows_unlocked, save_unlocked

    rows = clean(load())
    if a.roles:
        wanted = [w.strip().lower() for w in a.roles.split(",") if w.strip()]
        rows = [r for r in rows if any(w in r["title"].lower() for w in wanted)]
    if a.min_score is not None:
        rows = [r for r in rows if r["score"] >= a.min_score]
    rows.sort(key=lambda r: (-r["score"], r["company"].lower()))

    cache = json.loads(MX_CACHE.read_text()) if MX_CACHE.exists() else {}
    added = skipped_dup = skipped_mx = skipped_domain = 0
    per_domain: dict[str, int] = {}
    with FileLock(LOCK):
        existing = rows_unlocked()
        known = {r["email"].lower() for r in existing
                 if r["status"] in ("queued", "draft_ready", "sent", "replied")}
        for r in rows:
            if added >= a.limit:
                break
            if r["email"] in known:
                skipped_dup += 1
                continue
            if per_domain.get(r["domain"], 0) >= a.max_per_domain:
                skipped_domain += 1
                continue
            if a.verify:
                ok = mx_ok(r["domain"], cache)
                if ok is False:
                    skipped_mx += 1
                    continue
            add_row(existing, company=r["company"], name=r["name"], title=r["title"],
                    email=r["email"], source="recruiter_sheet",
                    notes=f"domain={r['domain']} score={r['score']}")
            known.add(r["email"])
            per_domain[r["domain"]] = per_domain.get(r["domain"], 0) + 1
            added += 1
        save_unlocked(existing)
    if a.verify:
        save_mx(cache)
    print(f"queued={added} duplicate={skipped_dup} same_domain={skipped_domain} "
          f"no_mx={skipped_mx} mode=check config/cold_email.yaml")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Recruiter sheet -> cold email queue")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    sub.add_parser("stats")
    v = sub.add_parser("verify")
    v.add_argument("--limit", type=int, default=40)
    q = sub.add_parser("queue")
    q.add_argument("--limit", type=int, default=25)
    q.add_argument("--max-per-domain", type=int, default=1)
    q.add_argument("--roles", default="", help="comma list, e.g. talent,recruit,people,hr")
    q.add_argument("--min-score", type=int, default=None)
    q.add_argument("--verify", action="store_true", help="skip domains without MX")
    a = ap.parse_args()
    return {"fetch": lambda _a: (fetch(), 0)[1], "stats": cmd_stats, "verify": cmd_verify,
            "queue": cmd_queue}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
