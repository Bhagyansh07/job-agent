"""Send a Telegram message.  python scripts/notify.py "text" """
import os, sys
from common import tg_api


def send(text):
    chat = os.environ["TELEGRAM_CHAT_ID"]
    for i in range(0, len(text), 3800):
        tg_api("sendMessage", {"chat_id": chat, "text": text[i:i + 3800]})


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) or sys.stdin.read()
    send(msg)
    print("sent")
