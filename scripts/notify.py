"""Send a Telegram message.  python scripts/notify.py "text"

Telegram's 4096 limit is counted in UTF-16 code units, not Python characters.
An emoji costs 2 units, so a plain len() split can still be rejected. The splitter
below counts real UTF-16 units and leaves a safety margin.
"""
import os, sys
from common import tg_api


def _split(text, limit=3800):
    out, buf, n = [], [], 0
    for ch in text:
        w = 2 if ord(ch) > 0xFFFF else 1
        if n + w > limit:
            out.append("".join(buf))
            buf, n = [], 0
        buf.append(ch)
        n += w
    if buf:
        out.append("".join(buf))
    return out or [""]


def send(text):
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat:
        raise SystemExit("TELEGRAM_CHAT_ID missing in .env")
    for part in _split(text):
        tg_api("sendMessage", {"chat_id": chat, "text": part})


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) or sys.stdin.read()
    send(msg)
    print("sent")
