"""Read-only Gmail helper.
python scripts/gmail_reader.py otp --minutes 10 [--sender naukri]   -> prints the newest OTP/verification code or NOT_FOUND
python scripts/gmail_reader.py recent --hours 24 [--notify]          -> recruiter/interview style mails not seen before
The agent must NEVER reply to mails. Reading only."""
import argparse, base64, json, re, sys, time
from common import ROOT
from google_auth import service

SEEN = ROOT / "state" / "seen_mail.json"
KEYWORDS = re.compile(r"interview|shortlist|short-list|assessment|test link|schedule|call|opportunity|next round|hiring|offer|your application|selected|regret", re.I)


def _alert_auth(reason: str) -> None:
    """A dead Gmail auth silently stops OTPs and recruiter-mail alerts. Tell him, at most 6-hourly."""
    try:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts" / "alert.py"),
                        f"Gmail not usable: {reason} | run python scripts/google_auth.py "
                        f"(and --send) again, OTP reading is blocked",
                        "--key", "gmail_auth", "--cooldown", "360"],
                       cwd=ROOT, timeout=60)
    except Exception:
        pass


def walk_text(payload):
    out = []

    def walk(p):
        if p.get("mimeType", "").startswith("text/") and p.get("body", {}).get("data"):
            out.append(base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", "ignore"))
        for x in p.get("parts", []) or []:
            walk(x)

    walk(payload)
    t = "\n".join(out)
    return re.sub(r"<[^>]+>", " ", t)


def hdr(m, name):
    for h in m["payload"]["headers"]:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def fetch(svc, q, n=15):
    res = svc.users().messages().list(userId="me", q=q, maxResults=n).execute().get("messages", [])
    return [svc.users().messages().get(userId="me", id=m["id"], format="full").execute() for m in res]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("otp")
    o.add_argument("--minutes", type=int, default=10)
    o.add_argument("--sender", default="")
    r = sub.add_parser("recent")
    r.add_argument("--hours", type=int, default=24)
    r.add_argument("--notify", action="store_true")
    args = ap.parse_args()

    try:
        svc = service("gmail", "v1", interactive=False)
    except FileNotFoundError:
        print("GMAIL_NOT_CONFIGURED: secrets/credentials.json missing")
        _alert_auth("secrets/credentials.json missing")
        return 6
    except RuntimeError as exc:
        print(f"GMAIL_NOT_CONFIGURED: {exc}")
        _alert_auth(str(exc)[:200])
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"GMAIL_AUTH_FAILED: {type(exc).__name__}: {str(exc)[:160]}")
        _alert_auth(f"{type(exc).__name__}: {str(exc)[:160]}")
        return 7

    try:
        if args.cmd == "otp":
            q = f"after:{int(time.time()) - args.minutes * 60}"
            if args.sender:
                q += f" from:{args.sender}"
            for m in fetch(svc, q, 10):
                text = hdr(m, "Subject") + "\n" + walk_text(m["payload"])
                hit = re.search(r"(?i)(otp|code|verification|passcode|pin)[^\d]{0,60}(\d{4,8})", text)
                if not hit and args.sender:
                    # only trust a bare 6 digit code when the sender filter is set
                    hit = re.search(r"\b(\d{6})\b", text)
                if hit:
                    print(hit.group(hit.lastindex))
                    return 0
            print("NOT_FOUND")
        else:
            q = f"after:{int(time.time()) - args.hours * 3600} -category:promotions -category:social"
            try:
                seen = set(json.loads(SEEN.read_text(encoding="utf-8")))
            except Exception:  # corrupted/missing cache must not stop the cycle
                seen = set()
            lines = []
            pending_seen = set()  # Mails to mark as seen (only after successful send)
            for m in fetch(svc, q, 40):
                if m["id"] in seen:
                    continue
                pending_seen.add(m["id"])
                subj, frm = hdr(m, "Subject"), hdr(m, "From")
                if KEYWORDS.search(subj) or KEYWORDS.search(m.get("snippet", "")):
                    lines.append(f"- {frm} | {subj} | {m.get('snippet', '')[:140]}")
            if not lines:
                # No matching mails, update seen cache
                SEEN.parent.mkdir(exist_ok=True)
                tmp = SEEN.with_suffix(".tmp")
                tmp.write_text(json.dumps(sorted(seen | pending_seen)[-2000:]), encoding="utf-8")
                tmp.replace(SEEN)
                print("NONE")
                return 0
            text = "Recruiter / application mails (reply khud karna):\n" + "\n".join(lines)
            print(text)
            if args.notify:
                from notify import send
                try:
                    send(text)
                except Exception as e:
                    print(f"NOTIFY_FAILED: {e}", file=sys.stderr)
                    # Do NOT save pending_seen - matching mails stay unseen for retry
                    return 0
            # Telegram send succeeded - now save seen IDs
            SEEN.parent.mkdir(exist_ok=True)
            tmp = SEEN.with_suffix(".tmp")
            tmp.write_text(json.dumps(sorted(seen | pending_seen)[-2000:]), encoding="utf-8")
            tmp.replace(SEEN)
    except Exception as exc:  # noqa: BLE001
        print(f"GMAIL_ERROR: {type(exc).__name__}: {str(exc)[:160]}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
