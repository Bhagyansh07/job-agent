"""One command that answers: can the agent actually run right now?

    python scripts/preflight.py            # checks everything, prints PASS/FAIL per item
    python scripts/preflight.py --no-model # skip the 1-call model probe (saves quota)

Checks, in the order that costs the agent the least time:
  1. .env + DRY_RUN (live or dry)
  2. model: opencode/big-pickle answers, and what the exact error is if it does not
  3. Chrome on the chat's CDP port, and that the listener is OUR profile, not another app
  4. real logins: Google (Gmail/OTP) and the chat's main portal
  5. tracker limits for today
  6. Telegram token (alerts must arrive)
  7. no Windows autostart entries (Bhagyansh does not want anything to run at logon)

Exit code: 0 if the agent can start, 1 if something blocks it.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTS = {"chat1": 9332, "chat2": 9333, "chat3": 9334}
MAIN_PORTAL = {"chat1": "instahyre", "chat2": "linkedin", "chat3": "naukri"}
results = []


def add(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def env():
    f = ROOT / ".env"
    if not f.exists():
        add("env", False, ".env missing")
        return
    txt = f.read_text(encoding="utf-8", errors="replace")
    dry = re.search(r"^DRY_RUN\s*=\s*(\S+)", txt, re.M)
    val = dry.group(1) if dry else "?"
    add("env", True, f"DRY_RUN={val}" + (" (nothing will be submitted)" if val.strip() in ("1", "true") else " (live)"))
    add("telegram token", "TELEGRAM_BOT_TOKEN=" in txt and "TELEGRAM_CHAT_ID=" in txt,
        "alerts will arrive" if "TELEGRAM_BOT_TOKEN=" in txt else "no token, alerts are lost")


def model(probe=True):
    mdl = os.environ.get("JOB_AGENT_MODEL", "opencode/big-pickle")
    if not probe:
        add("model", True, f"{mdl} (probe skipped)")
        return
    start = time.time()
    try:
        r = subprocess.run([shutil.which("opencode") or "opencode", "run", "-m", mdl, "Reply exactly: PREFLIGHT_OK"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=240)
        out = (r.stdout or "") + (r.stderr or "")
        out = re.sub(r"\x1b\[[0-9;]*m", "", out)
        err = next((ln.strip() for ln in out.splitlines()
                    if re.search(r"error|limit|invalid|denied", ln, re.I)), "")
        ok = "PREFLIGHT_OK" in out
        add("model", ok, f"{mdl} answered in {time.time()-start:.0f}s" if ok
            else f"{mdl} blocked: {err[:160] or 'no answer'}")
    except Exception as e:
        add("model", False, f"{mdl} probe failed: {e}")


def chrome(chat):
    port = PORTS.get(chat, 9332)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=4) as r:
            alive = r.status == 200
    except Exception:
        alive = False
    if not alive:
        add("chrome", False, f"nothing on {port} - run: powershell -ExecutionPolicy Bypass -File .\\start_chrome.ps1 -Chats {chat}")
        return
    ps = ("$p = (Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue | "
          "Select-Object -First 1).OwningProcess; if ($p) { "
          "(Get-CimInstance Win32_Process -Filter \"ProcessId=$p\").CommandLine }" % port)
    try:
        owner = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=30).stdout or ""
    except Exception:
        owner = ""
    ours = str(ROOT / "browser-profiles" / chat).lower() in owner.lower()
    add("chrome", ours, f"port {port} -> " + ("our profile" if ours else
        "ANOTHER program (agent would attach to the wrong browser)"))


def sessions(chat):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "session_check.py"),
                        "--chat", chat, "--portal", "google"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    add("gmail login", r.returncode == 0, (r.stdout or "").strip().splitlines()[0] if r.stdout.strip() else "no answer")
    portal = MAIN_PORTAL.get(chat)
    if portal:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "session_check.py"),
                            "--chat", chat, "--portal", portal],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        add(f"{portal} login", r.returncode == 0,
            (r.stdout or "").strip().splitlines()[0] if r.stdout.strip() else "no answer")


def limits(chat):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "tracker.py"), "check",
                        "--portal", MAIN_PORTAL.get(chat, "instahyre"), "--chat", chat],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    add("tracker limits", r.returncode == 0, out[0] if out else "no answer")


def autostart():
    startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
    entries = [p.name for p in startup.glob("*") if p.name.lower() != "desktop.ini"] if startup.exists() else []
    add("no autostart", not entries, ", ".join(entries) if entries else "nothing runs when Windows starts")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", default="chat1")
    ap.add_argument("--no-model", action="store_true")
    args = ap.parse_args()
    print(f"preflight for {args.chat}  ({time.strftime('%Y-%m-%d %H:%M')})\n")
    env()
    chrome(args.chat)
    sessions(args.chat)
    limits(args.chat)
    autostart()
    model(probe=not args.no_model)
    bad = [name for name, ok, _ in results if not ok]
    print()
    if bad:
        print(f"BLOCKED on: {', '.join(bad)}")
        print(f"Do not start the loop yet. Fix the FAIL lines above, then rerun: python scripts\\preflight.py --chat {args.chat}")
        return 1
    print(f"READY. Launch with: powershell -ExecutionPolicy Bypass -File .\\start_all.ps1 -Chats {args.chat}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
