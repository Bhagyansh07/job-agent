"""Urgent Telegram escalation - the agent's "I need you right now" channel.

    python scripts/alert.py "Naukri login chahiye | browser me login karke Done bolo" --key naukri_login --urgent
    python scripts/alert.py "12 naye jobs queue me hain" --key queue_info
    python scripts/alert.py --resolve naukri_login

Why this exists: a 24x7 agent must never sit silently on a blocker. Anything that needs
Bhagyansh (login, OTP, CAPTCHA, approval, missing key/resume, ban warning, repeated failure)
goes out immediately and is also written to state/needs_you.md so it is not lost if Telegram
is down.

Guarantees:
- never raises into a work cycle (exit 0 even when Telegram is unreachable)
- same --key is not repeated inside its cooldown window (default: 30 min urgent, 6 h info)
- every alert is appended to state/needs_you.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys

from common import ROOT, FileLock

ALERTS = ROOT / "state" / "alerts.json"
LOCK = ROOT / "state" / "alerts.lock"
NEEDS = ROOT / "state" / "needs_you.md"
FAILED = ROOT / "state" / "alerts_failed.log"


def _load() -> dict:
    try:
        return json.loads(ALERTS.read_text(encoding="utf-8")) if ALERTS.exists() else {}
    except Exception:  # corrupted cache must not block an urgent alert
        return {}


def _save(d: dict) -> None:
    tmp = ALERTS.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=0, sort_keys=True), encoding="utf-8")
    tmp.replace(ALERTS)


def _append_needs(kind: str, key: str, msg: str) -> None:
    NEEDS.parent.mkdir(parents=True, exist_ok=True)
    new = not NEEDS.exists()
    with NEEDS.open("a", encoding="utf-8") as f:
        if new:
            f.write("# NEEDS YOU - agent ke open asks\n")
            f.write("# Resolve: python scripts/alert.py --resolve <key>\n\n")
        ts = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
        f.write(f"- {ts} | {kind} | {key} | {msg.replace(chr(10), ' / ')}\n")


def _auto_key(message: str) -> str:
    """Stable, collision-resistant key for alerts sent without --key.

    Digits and URLs are normalised so the same recurring problem dedupes even when the
    counts change ("3 failures" vs "7 failures"), and sha256/16 hex makes collisions
    practically impossible compared with the old sha1[:12].
    """
    norm = re.sub(r"https?://\S+", "<url>", message.lower())
    norm = re.sub(r"\d+", "<n>", norm)
    norm = " ".join(norm.split())
    return "auto_" + hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser(description="Urgent Telegram escalation")
    ap.add_argument("message", nargs="?", default="")
    ap.add_argument("--key", default="", help="stable topic id for dedupe/resolve, e.g. naukri_login")
    ap.add_argument("--urgent", action="store_true", help="prefix [ACTION NEEDED] and short cooldown")
    ap.add_argument("--cooldown", type=int, default=0, help="minutes before the same key repeats (0 = default)")
    ap.add_argument("--no-dedupe", action="store_true", help="send even if the key was sent recently")
    ap.add_argument("--resolve", default="", help="mark a key resolved and print it")
    a = ap.parse_args()

    key = (a.key or "").strip() or _auto_key(a.message or "")

    if a.resolve:
        with FileLock(LOCK):
            d = _load()
            d.pop(a.resolve.strip(), None)
            _save(d)
        _append_needs("RESOLVED", a.resolve.strip(), "marked resolved")
        print(f"RESOLVED {a.resolve.strip()}")
        return 0

    if not a.message.strip():
        print("EMPTY_MESSAGE")
        return 2

    cooldown = a.cooldown or (30 if a.urgent else 360)
    now = dt.datetime.now(dt.timezone.utc)

    with FileLock(LOCK):
        d = _load()
        if not a.no_dedupe and key in d:
            try:
                last = dt.datetime.fromisoformat(d[key])
                if (now - last).total_seconds() < cooldown * 60:
                    left = int((cooldown * 60 - (now - last).total_seconds()) / 60) + 1
                    print(f"SKIPPED_DUPLICATE {key} (next in ~{left} min)")
                    return 0
            except Exception:
                pass
        d[key] = now.isoformat(timespec="seconds")
        _save(d)

    kind = "ACTION" if a.urgent else "INFO"
    text = f"[{kind} NEEDED]\n{a.message.strip()}\n\nkey: {key}"
    try:
        from notify import send
        send(text)
        print(f"ALERT_SENT {key}")
    except Exception as exc:  # noqa: BLE001 - a failed alert must never kill the cycle
        FAILED.parent.mkdir(parents=True, exist_ok=True)
        with FAILED.open("a", encoding="utf-8") as f:
            f.write(f"{now.isoformat(timespec='seconds')} | {key} | {type(exc).__name__}: {exc}\n")
        print(f"ALERT_UNSENT {key}: {type(exc).__name__}")

    _append_needs(kind, key, a.message.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
