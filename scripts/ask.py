"""Ask the user something on Telegram and wait for the answer.
python scripts/ask.py "Question?" --options "Yes,No" --timeout 900
Prints the tapped option / typed reply, or TIMEOUT.
A lock makes sure 3 chats never steal each other's replies."""
import argparse, json, os, time, datetime as dt
from common import tg_api, ROOT

p = argparse.ArgumentParser()
p.add_argument("question")
p.add_argument("--options", default="")
p.add_argument("--timeout", type=int, default=900)
a = p.parse_args()

chat = str(os.environ["TELEGRAM_CHAT_ID"])
opts = [o.strip() for o in a.options.split(",") if o.strip()]
lock = ROOT / "state" / "ask.lock"
lock.parent.mkdir(exist_ok=True)


def cut(s, n=60):
    """Telegram limits callback_data to 64 bytes, not 64 characters."""
    return s.encode("utf-8")[:n].decode("utf-8", "ignore")


def save_inbox(text):
    inbox = ROOT / "state" / "telegram_inbox.jsonl"
    line = {"ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "text": text}
    inbox.parent.mkdir(exist_ok=True)
    with inbox.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def consume(off):
    """Confirm the answer update so the next ask() cannot replay it into the inbox."""
    try:
        tg_api("getUpdates", {"offset": off, "timeout": 0})
    except Exception:
        pass

deadline = time.time() + a.timeout
got_lock = False
while time.time() < deadline:
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        got_lock = True
        break
    except FileExistsError:
        try:
            if time.time() - lock.stat().st_mtime > a.timeout + 30:
                lock.unlink()  # stale lock (ask died without cleaning up)
        except Exception:
            pass
        time.sleep(3)
if not got_lock:
    print("TIMEOUT")
    raise SystemExit(0)

try:
    old = tg_api("getUpdates", {"timeout": 0}).get("result", [])
    # Pre-drain skip stale updates, but NEVER throw away Bhagyansh's text messages
    # or button taps. Save them so a later cycle can use them for the matching open question.
    for u in old:
        m = u.get("message")
        if m and str(m.get("chat", {}).get("id")) == chat and m.get("text"):
            save_inbox(m["text"])
        cb = u.get("callback_query")
        if cb and str(cb.get("message", {}).get("chat", {}).get("id")) == chat and cb.get("data"):
            save_inbox(cb["data"])
    offset = (old[-1]["update_id"] + 1) if old else None
    payload = {"chat_id": chat, "text": a.question}
    if opts:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": o, "callback_data": cut(o)}] for o in opts]}
    tg_api("sendMessage", payload)
    end = time.time() + a.timeout
    while time.time() < end:
        params = {"timeout": 25}
        if offset:
            params["offset"] = offset
        try:
            res = tg_api("getUpdates", params, timeout=40).get("result", [])
        except Exception:
            time.sleep(3)
            continue
        for u in res:
            offset = u["update_id"] + 1
            cb = u.get("callback_query")
            if cb and str(cb["message"]["chat"]["id"]) == chat:
                try:
                    tg_api("answerCallbackQuery", {"callback_query_id": cb["id"]})
                except Exception:
                    pass
                consume(offset)
                print(cb["data"])
                raise SystemExit(0)
            m = u.get("message")
            if m and str(m["chat"]["id"]) == chat and m.get("text"):
                consume(offset)
                print(m["text"])
                raise SystemExit(0)
    print("TIMEOUT")
finally:
    try:
        lock.unlink()
    except Exception:
        pass
