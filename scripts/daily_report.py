"""Daily summary on Telegram.

python scripts/daily_report.py          -> build + send the report
python scripts/daily_report.py --dry    -> build + print only, send nothing (testing)

Reads tracker/applications.csv, counts today's rows by status and by portal,
average match score, and total rows. Adds the Google Sheet link if GOOGLE_SHEET_ID is set."""
import argparse, csv, os
from collections import Counter
from common import ROOT, today, is_dry


def rows():
    f = ROOT / "tracker" / "applications.csv"
    if not f.exists():
        return []
    with f.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def build():
    rs = rows()
    todays = [r for r in rs if r.get("date") == today()]
    by_status = Counter((r.get("status") or "").strip() for r in todays if (r.get("status") or "").strip())
    by_portal = Counter((r.get("portal") or "").strip() for r in todays if (r.get("portal") or "").strip())
    scores = []
    for r in todays:
        try:
            scores.append(int(float(r.get("match") or 0)))
        except (TypeError, ValueError):
            pass
    avg = (sum(scores) / len(scores)) if scores else None

    lines = [f"Aaj ka report - {today()}"]
    if is_dry():
        lines.append("MODE: DRY_RUN=1 - kuch submit nahi hua, sirf decisions log hue")
    lines.append(f"Total rows in sheet: {len(rs)}")
    lines.append("Aaj ke decisions: " + (", ".join(f"{k}={v}" for k, v in by_status.items()) if by_status else "kuch nahi"))
    lines.append("Portal wise: " + (", ".join(f"{k}={v}" for k, v in by_portal.items()) if by_portal else "kuch nahi"))
    lines.append(f"Average match: {avg:.1f}" if avg is not None else "Average match: n/a (aaj koi row nahi)")
    sid = os.environ.get("GOOGLE_SHEET_ID")
    if sid:
        lines.append(f"Sheet: https://docs.google.com/spreadsheets/d/{sid}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="print only, do not send")
    ap.add_argument("--force", action="store_true", help="send even if today's report already went out")
    args = ap.parse_args()
    msg = build()
    if args.dry:
        print(msg)
        return 0
    guard = ROOT / "state" / ".daily_report_date"
    try:
        last = guard.read_text(encoding="utf-8").strip() if guard.exists() else ""
    except Exception:
        last = ""
    if last == today() and not args.force:
        print("ALREADY_SENT")
        return 0
    # Write the guard BEFORE sending, then remove it if the send fails. A crash after a
    # successful send can no longer produce a duplicate, and a failed send is still retried.
    try:
        guard.parent.mkdir(parents=True, exist_ok=True)
        guard.write_text(today(), encoding="utf-8")
    except Exception:
        pass
    from notify import send
    try:
        send(msg)
    except Exception as exc:  # noqa: BLE001
        try:
            guard.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"DAILY_REPORT_SEND_FAILED: {type(exc).__name__}: {str(exc)[:160]}")
        try:
            import subprocess, sys
            subprocess.run([sys.executable, str(ROOT / "scripts" / "alert.py"),
                            f"Daily report could not be sent ({type(exc).__name__}). Check the Telegram token.",
                            "--key", "daily_report", "--cooldown", "360"], cwd=ROOT, timeout=60)
        except Exception:
            pass
        return 1
    print("sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
