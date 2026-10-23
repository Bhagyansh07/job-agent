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
            if time.time() - lock.stat().st_mtime > a.timeout + 120:
                lock.unlink()  # stale lock
        except Exception:
            pass
        time.sleep(3)
if not got_lock:
    print("TIMEOUT")
    raise SystemExit(0)

try:
    old = tg_api("getUpdates", {"timeout": 0}).get("result", [])
    # Pre-drain skip stale updates, but NEVER throw away Bhagyansh's text messages.
    # Save them so a later cycle can use them for the matching open question.
    inbox = ROOT / "state" / "telegram_inbox.jsonl"
    for u in old:
        m = u.get("message")
        if m and str(m.get("chat", {}).get("id")) == chat and m.get("text"):
            line = {"ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "text": m["text"]}
            inbox.parent.mkdir(exist_ok=True)
            with inbox.open("a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
    offset = (old[-1]["update_id"] + 1) if old else None
    payload = {"chat_id": chat, "text": a.question}
    if opts:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": o, "callback_data": o[:60]}] for o in opts]}
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
                print(cb["data"])
                raise SystemExit(0)
            m = u.get("message")
            if m and str(m["chat"]["id"]) == chat and m.get("text"):
                print(m["text"])
                raise SystemExit(0)
    print("TIMEOUT")
finally:
    try:
        lock.unlink()
    except Exception:
        pass
