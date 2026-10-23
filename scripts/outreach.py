"""LinkedIn outreach tracker (connection requests, referral DMs, follow-ups).

python scripts/outreach.py add --name N --title T --company C --url U --type recruiter|engineer|alumni|founder
python scripts/outreach.py update --url U --status requested|accepted|dm_sent|followup_sent|replied|ignored [--notes ..]
python scripts/outreach.py count            -> connection requests sent today + daily limit
python scripts/outreach.py due              -> who needs a DM now (accepted, no DM yet) and who needs a follow-up
python scripts/outreach.py exists --url U
"""
import argparse, csv, os, sys, datetime as dt
from common import ROOT, today, cfg, FileLock, safe_cell

F = ROOT / "tracker" / "outreach.csv"
LOCK = ROOT / "state" / "outreach.lock"
COLS = ["date", "name", "title", "company", "url", "type", "status", "status_date", "dm_date", "notes"]


def rows():
    if not F.exists():
        return []
    with F.open(encoding="utf-8", newline="") as f:
        # older CSV without every column must not crash the outreach step
        return [{c: (r.get(c) or "") for c in COLS} for r in csv.DictReader(f)]


def save(rs):
    F.parent.mkdir(exist_ok=True)
    with FileLock(LOCK):
        tmp = F.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            for r in rs:
                w.writerow({c: safe_cell(r.get(c, "")) for c in COLS})
        tmp.replace(F)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    for c in ("name", "title", "company", "url", "type", "status", "notes"):
        a.add_argument("--" + c, default="")
    a.set_defaults(status="requested")
    u = sub.add_parser("update")
    u.add_argument("--url", required=True)
    u.add_argument("--status", required=True)
    u.add_argument("--notes", default="")
    sub.add_parser("count")
    sub.add_parser("due")
    e = sub.add_parser("exists")
    e.add_argument("--url", required=True)
    args = ap.parse_args()
    rs = rows()
    o = cfg("profile.yaml")["outreach"]

    if args.cmd == "add":
        if any(r["url"] == args.url for r in rs):
            print("ALREADY")
            return
        status = args.status or "requested"
        if os.environ.get("DRY_RUN", "0").strip().lower() in ("1", "true", "yes") \
                and status in ("requested", "dm_sent", "followup_sent"):
            status = "draft_ready"
            print("DRY_RUN forced draft_ready (nothing was sent)")
        rs.append({"date": today(), "name": args.name, "title": args.title, "company": args.company, "url": args.url,
                   "type": args.type, "status": status, "status_date": today(), "dm_date": "", "notes": args.notes})
        save(rs)
        print("logged")
    elif args.cmd == "update":
        dry = os.environ.get("DRY_RUN", "0").strip().lower() in ("1", "true", "yes")
        if dry and args.status in ("requested", "dm_sent", "followup_sent"):
            print(f"DRY_RUN_BLOCKED: cannot mark {args.status} while DRY_RUN=1 (nothing was sent)")
            sys.exit(5)
        found = False
        for r in rs:
            if r["url"] == args.url:
                found = True
                r["status"], r["status_date"] = args.status, today()
                if args.status == "dm_sent":
                    r["dm_date"] = today()
                if args.notes:
                    r["notes"] = args.notes
        if not found:
            print(f"NOT_FOUND: {args.url}")
            sys.exit(2)
        save(rs)
        print("updated")
    elif args.cmd == "count":
        SENT = ("requested", "accepted", "dm_sent", "followup_sent", "replied", "ignored")
        n = sum(1 for r in rs if r["date"] == today() and r.get("status") in SENT)
        lim = o["connection_requests_per_day"]
        drafts = sum(1 for r in rs if r["status"] == "draft_ready")
        print(f"{'OK' if n < lim else 'LIMIT'} connection_requests {n}/{lim}"
              + (f" (drafts waiting: {drafts})" if drafts else ""))
        sys.exit(0 if n < lim else 3)
    elif args.cmd == "exists":
        print("YES" if any(r["url"] == args.url for r in rs) else "NO")
    elif args.cmd == "due":
        days = o["followup_after_days"]
        for r in rs:
            if r["status"] == "accepted" and not r["dm_date"]:
                print(f"DM_NOW | {r['name']} | {r['title']} @ {r['company']} | {r['url']}")
            if r["status"] == "dm_sent" and r["dm_date"]:
                try:
                    age = (dt.date.today() - dt.date.fromisoformat(r["dm_date"])).days
                except ValueError:
                    continue
                if age >= days:
                    print(f"FOLLOWUP | {r['name']} | {r['title']} @ {r['company']} | {r['url']} | dm {age}d ago")
            if r["status"] == "requested":
                try:
                    age = (dt.date.today() - dt.date.fromisoformat(r["status_date"])).days
                except ValueError:
                    continue
                if age >= 2:
                    print(f"CHECK_ACCEPTED | {r['name']} | {r['company']} | {r['url']}")


if __name__ == "__main__":
    main()
