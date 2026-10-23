"""Store the password for a NEW career-page account, and nothing else.

HARD RULE 4 exception: a password for an account the agent creates itself may be
stored in secrets/portal_accounts.csv. Existing accounts are never stored, read
back, or typed by the agent.

    python scripts/portal_account.py new --portal workday --email him@gmail.com

Prints PASSWORD=<generated> once so the agent can fill the signup form, then the
row is already on disk. Re-running for the same portal+email refuses.
"""
import argparse
import csv
import datetime as dt
import secrets as pysecrets
import string
import sys

from common import ROOT, FileLock

F = ROOT / "secrets" / "portal_accounts.csv"
LOCK = ROOT / "state" / "portal_accounts.lock"
COLS = ["portal", "email", "password", "date"]
LOWER = string.ascii_lowercase
UPPER = string.ascii_uppercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*"
ALPHABET = LOWER + UPPER + DIGITS + SYMBOLS


def new_password(length: int = 20) -> str:
    if length < 12:
        raise ValueError("length must be at least 12")
    chars = [pysecrets.choice(UPPER), pysecrets.choice(LOWER),
             pysecrets.choice(DIGITS), pysecrets.choice(SYMBOLS)]
    chars += [pysecrets.choice(ALPHABET) for _ in range(length - len(chars))]
    for i in range(len(chars) - 1, 0, -1):
        j = pysecrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def load() -> list[dict]:
    if not F.exists():
        return []
    try:
        with F.open(encoding="utf-8", newline="") as fh:
            return [{c: (r.get(c) or "") for c in COLS} for r in csv.DictReader(fh)]
    except Exception as exc:  # noqa: BLE001
        print(f"STORE_UNREADABLE: {type(exc).__name__}")
        sys.exit(2)


def save(rows: list[dict]) -> None:
    F.parent.mkdir(parents=True, exist_ok=True)
    tmp = F.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLS})
    tmp.replace(F)


def main() -> int:
    ap = argparse.ArgumentParser(description="New career-page account password store")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("--portal", required=True)
    n.add_argument("--email", required=True)
    n.add_argument("--length", type=int, default=20)
    a = ap.parse_args()

    portal = a.portal.strip().lower()
    email = a.email.strip().lower()
    if not portal or "@" not in email:
        print("INVALID: need --portal and a valid --email")
        return 2

    with FileLock(LOCK):
        rows = load()
        if any(r["portal"] == portal and r["email"].lower() == email for r in rows):
            print(f"EXISTS: {portal} / {email} already has a stored password")
            return 2
        try:
            pw = new_password(a.length)
        except ValueError as exc:
            print(f"INVALID_LENGTH: {exc}")
            return 2
        rows.append({"portal": portal, "email": email, "password": pw,
                     "date": dt.date.today().isoformat()})
        save(rows)

    print(f"PASSWORD={pw}")
    print(f"SAVED {portal} / {email} -> secrets/portal_accounts.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
