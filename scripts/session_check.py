"""Is the chat's browser actually logged in? Read the real cookies over CDP.

Why this exists: on 28 Oct the agent clicked "Apply" three times and logged three
applications. On 30 Oct the same profile had no Instahyre session cookie at all and
/candidate/opportunities/ redirected to /login/, so nothing could have been submitted.
A click is not an application. This script is the cheap, token-free check that says
"yes, there is a session" or "no, you are looking at a login page".

    python scripts/session_check.py --chat chat1                 # every known portal in that profile
    python scripts/session_check.py --chat chat1 --portal instahyre
    python scripts/session_check.py --chat chat1 --dump          # just list cookie names per domain

Exit codes: 0 = all checked portals have a session, 2 = at least one does not, 3 = no browser.
"""
import argparse
import json
import sys
import urllib.request

PORTS = {"chat1": 9332, "chat2": 9333, "chat3": 9334}

# A portal is "logged in" only if one of these session cookies exists. HttpOnly cookies do
# not show up in document.cookie, which is why this goes through CDP instead of JS.
REQUIRED = {
    "instahyre": ("sessionid",),
    "linkedin": ("li_at",),
    "naukri": ("nauk_at", "NPSSESSIONID"),
    "google": ("__Secure-1PSID", "SID"),
    "wellfound": ("_wellfound_session", "session"),
    "internshala": ("_internshala_session", "session"),
}
DOMAIN = {
    "instahyre": "instahyre.com",
    "linkedin": "linkedin.com",
    "naukri": "naukri.com",
    "google": "google.com",
    "wellfound": "wellfound.com",
    "internshala": "internshala.com",
}


def cookies(port, timeout=20):
    try:
        ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5))
    except Exception:
        return None
    from websockets.sync.client import connect

    ws = connect(ver["webSocketDebuggerUrl"], max_size=32 * 1024 * 1024, open_timeout=timeout)
    try:
        ws.send(json.dumps({"id": 1, "method": "Storage.getCookies", "params": {}}))
        while True:
            msg = json.loads(ws.recv(timeout=timeout))
            if msg.get("id") == 1:
                return msg.get("result", {}).get("cookies", [])
    finally:
        ws.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", default="chat1")
    ap.add_argument("--portal", default="")
    ap.add_argument("--dump", action="store_true")
    args = ap.parse_args()

    port = PORTS.get(args.chat)
    if not port:
        print(f"unknown chat {args.chat}")
        return 2
    jar = cookies(port)
    if jar is None:
        print(f"NO_BROWSER: nothing on port {port}. Run: powershell -ExecutionPolicy Bypass -File .\\start_chrome.ps1 -Chats {args.chat}")
        return 3

    by_domain = {}
    for c in jar:
        d = (c.get("domain") or "").lstrip(".").lower()
        by_domain.setdefault(d, []).append(c.get("name"))

    if args.dump:
        for d in sorted(by_domain):
            print(f"{d}: {', '.join(sorted(set(by_domain[d])))}")
        return 0

    portals = [args.portal] if args.portal else ["instahyre", "google", "linkedin", "naukri"]
    bad = []
    for p in portals:
        dom = DOMAIN.get(p)
        names = REQUIRED.get(p)
        if not dom or not names:
            print(f"{p}: UNKNOWN_PORTAL - no cookie rule, not checked")
            continue
        have = set()
        for d, ns in by_domain.items():
            if d == dom or d.endswith("." + dom):
                have.update(ns)
        ok = any(n in have for n in names)
        print(f"{p}: {'LOGGED_IN' if ok else 'LOGGED_OUT'}"
              + ("" if ok else f" (no {'/'.join(names)} cookie; cookies seen: {', '.join(sorted(have)) or 'none'})"))
        if not ok:
            bad.append(p)

    if bad:
        print(f"ACTION: log in to {', '.join(bad)} inside the {args.chat} Chrome window "
              f"(powershell -ExecutionPolicy Bypass -File .\\login_browser.ps1 -Chat {args.chat}). "
              f"Do not click Apply until this says LOGGED_IN.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
