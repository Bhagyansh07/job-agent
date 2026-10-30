"""Application tracker (CSV is the source of truth, Google Sheet is synced if configured).

python scripts/tracker.py add --portal naukri --company X --role Y --location Z --url U --match 86 --status applied_auto --resume file.pdf --notes "..." --chat chat1
python scripts/tracker.py exists --url U            (prints YES/NO)
python scripts/tracker.py check --portal naukri --chat chat1   (prints OK used/limit or LIMIT used/limit; exit code 3 on LIMIT)
python scripts/tracker.py summary --portal naukri   (today's audit lines for a portal; omit --portal for everything)
python scripts/tracker.py init-sheet                (writes header row in Google Sheet tab 'Applications')
Statuses: applied_auto, applied_approved, skipped, needs_input, failed, saved
DRY_RUN=1 in .env -> statuses get a dry_ prefix, nothing is applied, sheet sync skipped, dry_ rows don't count toward limits.
"""
import argparse, csv, os, re, sys
from collections import Counter
from common import ROOT, today, now, cfg, FileLock, safe_cell, is_dry

F = ROOT / "tracker" / "applications.csv"
LOCK = ROOT / "state" / "tracker.lock"
COLS = ["date", "time", "portal", "company", "role", "location", "url", "match", "status", "resume", "notes", "chat"]
APPLIED = ("applied_auto", "applied_approved", "applied")


def dry_run():
    return is_dry()


def rows():
    if not F.exists():
        return []
    # utf-8-sig: the CSV gets edited in Excel/PowerShell sometimes, which prepends a BOM.
    # With plain utf-8 the first column reads as "\ufeffdate" and every limit/dedupe check
    # silently sees an empty date.
    with F.open(encoding="utf-8-sig", newline="") as f:
        # normalise: an older CSV without every column must not crash the runner
        return [{c: (r.get(c) or "") for c in COLS} for r in csv.DictReader(f)]


def norm(s):
    return " ".join((s or "").lower().split())


_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_content",
                    "utm_term", "ref", "source", "gclid", "fbclid", "mc_cid", "mc_eid"}


def base(url):
    """Strip only utm/tracking params; keep job-identifying params like jk, currentJobId, gh_jid."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(url)
        if not parsed.query:
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))
        qs = parse_qs(parsed.query, keep_blank_values=True)
        keep = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
        if not keep:
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))
        new_qs = urlencode(keep, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", new_qs, ""))
    except Exception:
        return (url or "").split("?")[0].rstrip("/")


def exists(url=None, company=None, role=None):
    for r in rows():
        if url and base(r["url"]) == base(url):
            return True
        if company and role and norm(r["company"]) == norm(company) and norm(r["role"]) == norm(role):
            if r["status"] in APPLIED or r["status"] == "skipped":
                return True
    return False


def sync_sheet(row):
    sid = os.environ.get("GOOGLE_SHEET_ID")
    if not sid:
        return
    try:
        from google_auth import service
        svc = service("sheets", "v4", interactive=False)   # never open a browser unattended
        svc.spreadsheets().values().append(
            spreadsheetId=sid, range="Applications!A1", valueInputOption="RAW",
            insertDataOption="INSERT_ROWS", body={"values": [[row[c] for c in COLS]]},
        ).execute()
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:160]}"
        print("sheet sync skipped:", err, file=sys.stderr)
        # A silent Sheet drift is how you lose trust in the tracker. Tell him, at most once per 6h.
        try:
            import subprocess
            subprocess.run([sys.executable, str(ROOT / "scripts" / "alert.py"),
                            f"Google Sheet sync failed ({err}). CSV is safe, Sheet is behind. "
                            f"Check quota/sharing, then re-run tracker.py init-sheet if needed.",
                            "--key", "sheet_sync", "--cooldown", "360"],
                           cwd=ROOT, timeout=60)
        except Exception:
            pass


def auto_apply_min():
    """Threshold from config/profile.yaml (match.auto_apply_min). 80 if it cannot be read."""
    try:
        mc = (cfg() or {}).get("match") or {}
        return float(mc.get("auto_apply_min", 80))
    except Exception:
        return 80.0


def add(d):
    # Hard guard. The agent twice logged applied_auto below 80 (65 on Naukri, 75 on Instahyre)
    # because the docs said "batch approval" and the model took the shortcut anyway. Code wins.
    status = str(d.get("status") or "")
    if status == "applied_auto":
        try:
            m = float(str(d.get("match") or 0))
        except ValueError:
            m = 0.0
        floor = auto_apply_min()
        if m < floor:
            raise SystemExit(
                f"BLOCKED: applied_auto needs match >= {floor:g}, got {m:g}. "
                f"Send it in the 60-79 batch approval instead, then log --status applied_approved. "
                f"Nothing was written.")
    if status == "applied_auto" and not str(d.get("url") or "").startswith("http"):
        raise SystemExit("BLOCKED: applied_auto needs the real job URL (--url), not an empty value.")
    # A list page is not a job. On 28 Oct all three Instahyre rows pointed at
    # /candidate/opportunities/?matching=true, so duplicates were undetectable and the audit
    # link opened the same feed for every job.
    LIST_URL_RE = re.compile(
        r"instahyre\.com/candidate/opportunities/?(\?|$)"
        r"|(?:linkedin\.com/jobs/search|naukri\.com/[a-z-]*jobs(?:-in)?(?:\?|$)"
        r"|indeed\.[a-z.]+/jobs\?|wellfound\.com/(?:jobs|role)(?:\?|$)"
        r"|cutshort\.io/jobs(?:\?|$)|hirist\.(?:tech|com)/jobs(?:\?|$))", re.I)
    if status in ("applied_auto", "applied_approved", "applied", "saved") and LIST_URL_RE.search(str(d.get("url") or "")):
        raise SystemExit(
            "BLOCKED: that is a search/list URL, not the job. Open the job and log its real URL "
            "(Instahyre: /candidate/opportunities/<id>/). Nothing was written.")
    # 60-79 belongs to Bhagyansh. Skipping it on the model's own judgement is exactly what
    # happened to eShopbox (78) on 28 Oct. Only hard filters may skip before approval, and
    # those log match < 60 or use a hard-filter reason.
    if status == "skipped":
        try:
            m = float(str(d.get("match") or 0))
        except ValueError:
            m = 0.0
        floor = auto_apply_min()
        hard = str(d.get("notes") or "").lower()
        hard_markers = ("sales", "bpo", "telecall", "unpaid", "commission", "training fee",
                        "bond", "deposit", "walk-in", "senior", "2+ years", "sensitive",
                        "payment", "aadhaar", "pan card", "passport", "non-tech")
        if floor > m >= 60 and not any(k in hard for k in hard_markers):
            raise SystemExit(
                f"BLOCKED: match {m:g} is in 60-79. It goes to batch approval, not skipped. "
                f"Collect it, send the numbered list, log applied_approved or skipped only after "
                f"his reply. Nothing was written.")
    F.parent.mkdir(exist_ok=True)
    new = not F.exists()
    row = {c: safe_cell(d.get(c, "") or "") for c in COLS}
    row["date"], row["time"] = today(), now()
    if dry_run() and not row["status"].startswith("dry_"):
        row["status"] = "dry_" + row["status"]      # log the decision, never apply
    with FileLock(LOCK):
        with F.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            if new:
                w.writeheader()
            w.writerow(row)
    if not dry_run():
        sync_sheet(row)


def used_today(portal=None, chat=None):
    n = 0
    for r in rows():
        if r["status"].startswith("dry_"):
            continue        # dry_ rows never count toward limits
        if r["date"] == today() and r["status"] in APPLIED and (portal is None or r["portal"] == portal) \
                and (chat is None or r.get("chat") == chat):
            n += 1
    return n


def counts_today(all_rows=None):
    """One CSV read -> (global, per_portal, per_chat). Snapshot consistent with itself."""
    rs = rows() if all_rows is None else all_rows
    d, per_portal, per_chat = today(), {}, {}
    for r in rs:
        if r["date"] != d or r["status"].startswith("dry_") or r["status"] not in APPLIED:
            continue
        per_portal[r["portal"]] = per_portal.get(r["portal"], 0) + 1
        per_chat[r.get("chat", "")] = per_chat.get(r.get("chat", ""), 0) + 1
    return sum(per_portal.values()), per_portal, per_chat


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    for c in COLS[2:]:
        a.add_argument("--" + c, default="")
    a.set_defaults(status="applied_auto")
    e = sub.add_parser("exists")
    e.add_argument("--url")
    e.add_argument("--company")
    e.add_argument("--role")
    c = sub.add_parser("check")
    c.add_argument("--portal", required=True)
    c.add_argument("--chat", default="")
    s = sub.add_parser("summary")
    s.add_argument("--portal")
    sub.add_parser("init-sheet")
    args = ap.parse_args()

    if args.cmd == "add":
        d = vars(args)
        if not d.get("status"):
            d["status"] = "applied_auto"
        add(d)
        print("logged")
    elif args.cmd == "exists":
        print("YES" if exists(args.url, args.company, args.role) else "NO")
    elif args.cmd == "check":
        lim = cfg("profile.yaml")["limits"]
        per = lim.get("per_portal", {}).get(args.portal, lim.get("default_per_portal", 15))
        g_used, per_portal, per_chat_used = counts_today()   # single consistent snapshot
        p_used = per_portal.get(args.portal, 0)
        per_chat = lim.get("per_chat", {}).get(args.chat) if args.chat else None
        chat_used = per_chat_used.get(args.chat, 0)
        if g_used >= lim["global_daily"]:
            print(f"LIMIT global {g_used}/{lim['global_daily']}")
            sys.exit(3)
        if p_used >= per:
            print(f"LIMIT {args.portal} {p_used}/{per}")
            sys.exit(3)
        if per_chat is not None and chat_used >= per_chat:
            print(f"LIMIT {args.chat} {chat_used}/{per_chat}")
            sys.exit(3)
        tail = f", {args.chat} {chat_used}/{per_chat}" if per_chat is not None else ""
        print(f"OK {args.portal} {p_used}/{per} (global {g_used}/{lim['global_daily']}{tail})")
    elif args.cmd == "summary":
        rs = [r for r in rows() if r["date"] == today() and (not args.portal or r["portal"] == args.portal)]
        cnt = Counter(r["status"] for r in rs)
        print(f"AUDIT {args.portal or 'ALL'} {today()}: " + ", ".join(f"{k}={v}" for k, v in cnt.items()))
        top = sorted(rs, key=lambda r: int(r["match"] or 0), reverse=True)[:10]
        for r in top:
            print(f"- [{r['status']}] {r['company']} | {r['role']} | {r['location']} | match {r['match']} | {r['notes']}")
        if len(rs) > len(top):
            print(f"... and {len(rs) - len(top)} more")
    elif args.cmd == "init-sheet":
        from google_auth import service
        sid = os.environ["GOOGLE_SHEET_ID"]
        service("sheets", "v4").spreadsheets().values().update(
            spreadsheetId=sid, range="Applications!A1", valueInputOption="RAW", body={"values": [COLS]}
        ).execute()
        print("header written")


if __name__ == "__main__":
    main()
