"""Read-only Gmail helper.
python scripts/gmail_reader.py otp --minutes 10 [--sender naukri]   -> prints the newest OTP/verification code or NOT_FOUND
python scripts/gmail_reader.py recent --hours 24 [--notify]          -> recruiter/interview style mails not seen before
The agent must NEVER reply to mails. Reading only."""
import argparse, base64, json, re, time
from common import ROOT
from google_auth import service

SEEN = ROOT / "state" / "seen_mail.json"
KEYWORDS = re.compile(r"interview|shortlist|short-list|assessment|test link|schedule|call|opportunity|next round|hiring|offer|your application|selected|regret", re.I)


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
    svc = service("gmail", "v1")

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
                return
        print("NOT_FOUND")
    else:
        q = f"after:{int(time.time()) - args.hours * 3600} -category:promotions -category:social"
        seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
        lines = []
        for m in fetch(svc, q, 40):
            if m["id"] in seen:
                continue
            subj, frm = hdr(m, "Subject"), hdr(m, "From")
            if KEYWORDS.search(subj) or KEYWORDS.search(m.get("snippet", "")):
                lines.append(f"- {frm} | {subj} | {m.get('snippet', '')[:140]}")
            seen.add(m["id"])
        SEEN.parent.mkdir(exist_ok=True)
        SEEN.write_text(json.dumps(sorted(seen)[-2000:]))
        if not lines:
            print("NONE")
            return
        text = "Recruiter / application mails (reply khud karna):\n" + "\n".join(lines)
        print(text)
        if args.notify:
            from notify import send
            send(text)


if __name__ == "__main__":
    main()
