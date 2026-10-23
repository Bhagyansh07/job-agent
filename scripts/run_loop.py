"""24x7 runner. One terminal per chat:
  python scripts/run_loop.py chat1
  python scripts/run_loop.py chat2
  python scripts/run_loop.py chat3
Each loop starts a fresh `opencode run` work cycle (state lives in files, so nothing is lost between cycles).
PAUSE switch: put a file state/PAUSE (all chats) or state/PAUSE_chat1 (one chat) and the loop waits."""
import datetime as dt, os, shutil, subprocess, sys, time
from zoneinfo import ZoneInfo
from common import ROOT

IST = ZoneInfo("Asia/Kolkata")
chat = sys.argv[1] if len(sys.argv) > 1 else "chat1"
min_cycle = int(sys.argv[2]) if len(sys.argv) > 2 else (1800 if chat == "chat3" else 900)
MODEL_TIMEOUT = int(os.environ.get("OPENCODE_CYCLE_TIMEOUT", "1800"))
exe = shutil.which("opencode") or "opencode"
idle_file = ROOT / "state" / f"{chat}_idle_until.txt"
pauses = [ROOT / "state" / "PAUSE", ROOT / "state" / f"PAUSE_{chat}"]
log_dir = ROOT / "state" / "logs"
pw = f"pw_{chat}"

RATE_MARKERS = ("429", "too many requests", "rate limit", "ratelimit", "freeusagelimiterror",
                "sign up for free to continue", "quota exceeded", "insufficient credits",
                "no available model", "model not found", "overloaded")


def looks_failed(rc: int, content: str) -> bool:
    low = content.lower()
    return rc != 0 or any(m in low for m in RATE_MARKERS)


def rate_limited(content: str) -> bool:
    low = content.lower()
    return any(m in low for m in RATE_MARKERS)


def clean_old_logs():
    if not log_dir.exists():
        return
    cutoff = time.time() - 14 * 86400
    for p in log_dir.glob("*.log"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


# Stagger chat starts so three cycles never hit the gateway in the same second.
time.sleep({"chat1": 0, "chat2": 25, "chat3": 50}.get(chat, 0))

while True:
    if any(p.exists() for p in pauses):
        print(f"[{chat}] PAUSE file present - waiting")
        time.sleep(300)
        continue
    start = time.time()
    if idle_file.exists():
        try:
            until = dt.datetime.fromisoformat(idle_file.read_text().strip())
            if until.tzinfo is None:          # naive timestamps = Asia/Kolkata
                until = until.replace(tzinfo=IST)
            wait = (until - dt.datetime.now(IST)).total_seconds()
            if wait > 0:
                print(f"[{chat}] idle until {until.isoformat()} ({int(wait)}s)")
                time.sleep(min(wait, 1800))
                continue
        except Exception:
            pass
        idle_file.unlink(missing_ok=True)
    if any(p.exists() for p in pauses):       # re-check after idle sleep
        print(f"[{chat}] PAUSE file present - waiting")
        time.sleep(300)
        continue
    # Once-per-day Telegram summary (guard file holds the last date it ran successfully)
    guard = ROOT / "state" / ".daily_report_date"
    today_ist = dt.datetime.now(IST).date().isoformat()
    try:
        last = guard.read_text(encoding="utf-8").strip() if guard.exists() else ""
    except Exception:
        last = ""
    if last != today_ist:
        try:
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "daily_report.py")], cwd=ROOT)
            if r.returncode == 0:
                guard.parent.mkdir(parents=True, exist_ok=True)
                guard.write_text(today_ist, encoding="utf-8")
        except Exception as e:
            print("daily_report failed:", e)
    if chat == "chat3":
        subprocess.run([sys.executable, str(ROOT / "scripts" / "watcher.py")])
    now = dt.datetime.now(IST)
    if chat == "chat1":
        chain = ["kilo/laguna-s", "kilo/laguna-xs", "kilo/flint", "kilo/dots3"]
    elif chat == "chat2":
        chain = ["kilo/laguna-xs", "kilo/laguna-s", "kilo/flint", "kilo/dots3"]
    elif chat == "chat3":
        chain = ["kilo/flint", "kilo/laguna-s", "kilo/laguna-xs", "kilo/dots3"]
    else:
        chain = ["kilo/laguna-s", "kilo/laguna-xs", "kilo/flint", "kilo/dots3"]
    prompt = (f"Read chats/{chat}.md fully, then run ONE work cycle exactly as described there. "
              f"Use ONLY the browser tools of the MCP server named {pw}. Today is {now.date().isoformat()}, "
              f"time now {now.strftime('%H:%M')} IST.")
    log_dir.mkdir(parents=True, exist_ok=True)
    clean_old_logs()
    logfile = log_dir / f"{chat}_{now.strftime('%Y%m%d_%H%M')}.log"
    success = False
    for idx, model in enumerate(chain):
        if success:
            break
        try:
            print(f"[{chat}] trying model: {model}")
            with logfile.open("w", encoding="utf-8") as f:
                res = subprocess.run([exe, "run", "-m", model, prompt], cwd=ROOT,
                                     stdout=f, stderr=subprocess.STDOUT, timeout=MODEL_TIMEOUT)
            try:
                content = logfile.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                print("\n".join(lines[-30:]))
                if not looks_failed(res.returncode, content):
                    success = True
                    break
                if rate_limited(content) and idx == 0:
                    print(f"[{chat}] rate limit detected, retrying same model after 1.5s")
                    time.sleep(1.5)
                    with logfile.open("w", encoding="utf-8") as f:
                        res = subprocess.run([exe, "run", "-m", model, prompt], cwd=ROOT,
                                             stdout=f, stderr=subprocess.STDOUT, timeout=MODEL_TIMEOUT)
                    content = logfile.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    print("\n".join(lines[-30:]))
                    if not looks_failed(res.returncode, content):
                        success = True
                        break
                if looks_failed(res.returncode, content):
                    if idx < len(chain) - 1:
                        print(f"[{chat}] switching to fallback: {chain[idx+1]} after 1.5s")
                        time.sleep(1.5)
                    continue
                success = True
                break
            except Exception as e:
                print(f"[{chat}] log read failed: {e}")
                if idx < len(chain) - 1:
                    time.sleep(1.5)
                    continue
                break
        except Exception as e:
            print(f"[{chat}] run failed with {model}: {e}")
            if idx < len(chain) - 1:
                time.sleep(1.5)
                continue
            break
    time.sleep(max(60, min_cycle - (time.time() - start)))
