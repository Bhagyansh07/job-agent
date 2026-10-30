"""Read a page through the agent's Chrome over raw CDP, with no model tokens.

Used to verify what the live browser actually shows (logged in? applied list? confirmation?)
when a cycle's claims need evidence. Read-only: it opens one tab and navigates it.

    python tools/cdp_read.py --chat chat1 --url https://www.instahyre.com/candidate/opportunities/
    python tools/cdp_read.py --chat chat1 --url <url> --js "document.title"
"""
import argparse
import json
import sys
import time
import urllib.request

from websockets.sync.client import connect

PORTS = {"chat1": 9332, "chat2": 9333, "chat3": 9334}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", default="chat1")
    ap.add_argument("--url", required=True)
    ap.add_argument("--js", default="document.body.innerText")
    ap.add_argument("--js-file", default="", help="read the JS expression from a file (avoids quoting pain)")
    ap.add_argument("--wait", type=float, default=8.0)
    ap.add_argument("--keep-tab", action="store_true")
    ap.add_argument("--await", dest="await_promise", action="store_true",
                    help="the JS returns a Promise; wait for it")
    args = ap.parse_args()

    port = PORTS.get(args.chat, 9332)
    if args.js_file:
        from pathlib import Path
        args.js = Path(args.js_file).read_text(encoding="utf-8")
    try:
        ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5))
    except Exception:
        print(f"NO_BROWSER on {port}: run start_chrome.ps1 -Chats {args.chat}")
        return 3

    i = 0
    with connect(ver["webSocketDebuggerUrl"], max_size=64 * 1024 * 1024) as ws:
        def send(method, params=None, session=None):
            nonlocal i
            i += 1
            payload = {"id": i, "method": method, "params": params or {}}
            if session:
                payload["sessionId"] = session
            ws.send(json.dumps(payload))
            while True:
                msg = json.loads(ws.recv(timeout=60))
                if msg.get("id") == i:
                    return msg

        target = send("Target.createTarget", {"url": "about:blank"})["result"]["targetId"]
        session = send("Target.attachToTarget", {"targetId": target, "flatten": True})["result"]["sessionId"]
        send("Page.enable", {}, session)
        send("Page.navigate", {"url": args.url}, session)
        time.sleep(args.wait)
        out = send("Runtime.evaluate", {"expression": args.js, "returnByValue": True,
                                        "awaitPromise": args.await_promise}, session)
        val = out.get("result", {}).get("result", {}).get("value")
        loc = send("Runtime.evaluate", {"expression": "location.href", "returnByValue": True}, session)
        print("FINAL_URL:", loc.get("result", {}).get("result", {}).get("value"))
        print("---CONTENT---")
        print(val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)[:6000])
        if not args.keep_tab:
            send("Target.closeTarget", {"targetId": target})
    return 0


if __name__ == "__main__":
    sys.exit(main())

