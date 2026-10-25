"""Application tracker (CSV is the source of truth, Google Sheet is synced if configured).

python scripts/tracker.py add --portal naukri --company X --role Y --location Z --url U --match 86 --status applied_auto --resume file.pdf --notes "..." --chat chat1
python scripts/tracker.py exists --url U            (prints YES/NO)
python scripts/tracker.py check --portal naukri --chat chat1   (prints OK used/limit or LIMIT used/limit; exit code 3 on LIMIT)
python scripts/tracker.py summary --portal naukri   (today's audit lines for a portal; omit --portal for everything)
python scripts/tracker.py init-sheet                (writes header row in Google Sheet tab 'Applications')
Statuses: applied_auto, applied_approved, skipped, needs_input, failed, saved
DRY_RUN=1 in .env -> statuses get a dry_ prefix, nothing is applied, sheet sync skipped, dry_ rows don't count toward limits.
"""
import argparse, csv, os, sys
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
    with F.open(encoding="utf-8", newline="") as f:
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
        print("sheet sync skipped:", e, file=sys.stderr)


def add(d):
    F.parent.mkdir(exist_ok=True)
    new = not F.exists()
    row = {c: safe_cell(d.get(c, "") or "") for c in COLS}
    row["date"], row["time"] = today(), now()
    if dry_run():
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
        p_used, g_used = used_today(args.portal), used_today()
        per_chat = lim.get("per_chat", {}).get(args.chat) if args.chat else None
        if g_used >= lim["global_daily"]:
            print(f"LIMIT global {g_used}/{lim['global_daily']}")
            sys.exit(3)
        if p_used >= per:
            print(f"LIMIT {args.portal} {p_used}/{per}")
            sys.exit(3)
        if per_chat is not None and used_today(chat=args.chat) >= per_chat:
            print(f"LIMIT {args.chat} {used_today(chat=args.chat)}/{per_chat}")
            sys.exit(3)
        tail = f", {args.chat} {used_today(chat=args.chat)}/{per_chat}" if per_chat is not None else ""
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
