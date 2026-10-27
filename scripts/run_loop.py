"""24x7 runner. One terminal per chat:
  python scripts/run_loop.py chat1
  python scripts/run_loop.py chat2
  python scripts/run_loop.py chat3
Each loop starts a fresh `opencode run` work cycle (state lives in files, so nothing is lost between cycles).
PAUSE switch: put a file state/PAUSE (all chats) or state/PAUSE_chat1 (one chat) and the loop waits."""
import datetime as dt, os, re, shutil, subprocess, sys, time
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

# Removed "overloaded" - appears in backend JD content and causes false failures
RATE_MARKERS = ("too many requests", "rate limit", "ratelimit", "freeusagelimiterror",
                "sign up for free to continue", "quota exceeded", "insufficient credits",
                "no available model", "model not found")
# bare "429" is a job id as often as it is an HTTP status, so require context
RATE_RE = re.compile(r"(?:status|code|error|http)[^\n]{0,16}\b429\b|\b429\b[^\n]{0,16}(?:too many|rate limit)")


def _is_error_line(line: str) -> bool:
    """Check if a log line looks like a system error, not JD content."""
    low = line.lower().strip()
    indicators = ("error:", "error ", "exception:", "traceback", "fatal:", "failed:",
                  "denied", "blocked", "banned", "unavailable", "sign up", "quota",
                  "rate limit", "too many", "overloaded", "insufficient", "no available")
    return any(ind in low for ind in indicators)


def rate_limited(content: str) -> bool:
    """Only check the last 40 lines for rate limit markers in error context.
    JD content mentioning 'rate limiting' or 'overloaded' no longer causes false failures."""
    lines = content.splitlines()[-40:]
    for line in lines:
        if not _is_error_line(line):
            continue
        low = line.lower()
        if any(m in low for m in RATE_MARKERS):
            return True
        if RATE_RE.search(low):
            return True
    return False


def looks_failed(rc: int, content: str) -> bool:
    if rc != 0:
        return True
    return rate_limited(content)


def _run_model(model, prompt, logfile, timeout):
    """Run opencode with timeout. Returns (rc, content).
    On timeout, kills the entire process tree (opencode + Chrome/MCP children)."""
    f = logfile.open("w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [exe, "run", "-m", model, prompt],
            cwd=ROOT,
            stdout=f,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    except Exception as e:
        f.close()
        return -1, str(e)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Kill entire process tree - opencode + Chrome + MCP children
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                          capture_output=True, timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
    f.close()
    content = logfile.read_text(encoding="utf-8", errors="replace") if logfile.exists() else ""
    return proc.returncode, content


# Kill only THIS chat's browser leftovers whose parent process is already gone.
# The Playwright MCP servers are shared per project location and are owned by the
# background opencode service, so touching a live server would break the other chats.
ORPHAN_PS = r"""
$chat = '__CHAT__'
$procs = @(Get-CimInstance Win32_Process -Filter "Name='chrome.exe' OR Name='node.exe'" |
    Where-Object { $_.CommandLine -and ($_.CommandLine -match ('browser-profiles[/\\]' + $chat + '(\s|$|")')) })
if ($procs.Count -eq 0) { return }
$alive = @{}
Get-CimInstance Win32_Process | ForEach-Object { $alive[[string]$_.ProcessId] = $true }
foreach ($p in $procs) {
    $ppid = [string]$p.ParentProcessId
    if ($ppid -eq '0' -or -not $alive.ContainsKey($ppid)) {
        Write-Output ("orphan " + $p.ProcessId + " " + $p.Name)
        & taskkill.exe /F /T /PID $p.ProcessId 2>&1 | Out-Null
    }
}
"""


def reap_orphans():
    """Clean up a crashed cycle's Chrome before starting a new one.

    A killed/timed-out cycle can leave Chrome holding browser-profiles/<chat>, and the
    next launch then fails silently. Only processes with a dead parent are reaped."""
    if os.name != "nt":
        return
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            ORPHAN_PS.replace("__CHAT__", chat)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        killed = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.startswith("orphan ")]
        if killed:
            print(f"[{chat}] reaped {len(killed)} orphan browser process(es): " + "; ".join(killed[:6]))
    except Exception as e:
        print(f"[{chat}] orphan cleanup skipped: {e}")


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


def run_health_check():
    """Pre-flight: catch a dead Telegram token / missing resume before a cycle burns an hour.
    Throttled to once an hour; a FAIL alerts once per 6h but never blocks the cycle."""
    report = ROOT / "state" / "health.json"
    try:
        fresh = report.exists() and (time.time() - report.stat().st_mtime < 3600)
    except OSError:
        fresh = False
    if fresh:
        return
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "health_check.py"), "--quiet"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=90)
        out = (r.stdout or "").strip()
        if out:
            print(f"[{chat}] health:\n{out}")
        if r.returncode == 1:
            fails = [ln for ln in out.splitlines() if ln.startswith("FAIL")]
            msg = "; ".join(ln[5:].strip() for ln in fails)[:600] or "health check failed"
            subprocess.run([sys.executable, str(ROOT / "scripts" / "alert.py"),
                            f"Health check FAIL: {msg} | fix these, agent is running degraded",
                            "--key", "health_fail", "--urgent", "--cooldown", "360"],
                           cwd=ROOT, timeout=60)
    except Exception as e:
        print(f"[{chat}] health check could not run: {e}")


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
        try:
            subprocess.run([sys.executable, str(ROOT / "scripts" / "watcher.py")], timeout=300)
        except Exception as e:
            print("watcher failed:", e)
    run_health_check()
    reap_orphans()
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
        print(f"[{chat}] trying model: {model}")
        try:
            rc, content = _run_model(model, prompt, logfile, MODEL_TIMEOUT)
        except Exception as e:
            print(f"[{chat}] run failed with {model}: {e}")
            if idx < len(chain) - 1:
                time.sleep(1.5)
                continue
            break
        try:
            lines = content.splitlines() if content else []
            print("\n".join(lines[-30:]))
            if not looks_failed(rc, content):
                success = True
                break
            # Retry same model once if rate-limited on first attempt
            if rate_limited(content) and idx == 0:
                print(f"[{chat}] rate limit detected, retrying same model after 1.5s")
                time.sleep(1.5)
                rc, content = _run_model(model, prompt, logfile, MODEL_TIMEOUT)
                lines = content.splitlines() if content else []
                print("\n".join(lines[-30:]))
                if not looks_failed(rc, content):
                    success = True
                    break
            if looks_failed(rc, content) and idx < len(chain) - 1:
                print(f"[{chat}] switching to fallback: {chain[idx+1]} after 1.5s")
                time.sleep(1.5)
                continue
        except Exception as e:
            print(f"[{chat}] post-run error: {e}")
            if idx < len(chain) - 1:
                time.sleep(1.5)
                continue
            break
    if not success:
        # one alert per 6h across all chats, so a dead gateway never goes unnoticed
        guard = ROOT / "state" / ".last_fail_alert"
        try:
            stale = (not guard.exists()) or (time.time() - guard.stat().st_mtime > 6 * 3600)
        except OSError:
            stale = True
        if stale:
            try:
                subprocess.run([sys.executable, str(ROOT / "scripts" / "alert.py"),
                                f"{chat}: all 4 models failed this cycle. Quota or gateway problem. "
                                f"Log: state/logs/{logfile.name}",
                                "--key", "models_failed", "--urgent", "--cooldown", "360"],
                               cwd=ROOT, timeout=60)
                guard.write_text(dt.datetime.now(IST).isoformat(timespec="seconds"), encoding="utf-8")
            except Exception as e:
                print(f"[{chat}] failure alert could not be sent: {e}")
    else:
        # recovery notice: only if a failure was alerted and is still unresolved
        guard = ROOT / "state" / ".last_fail_alert"
        if guard.exists():
            try:
                subprocess.run([sys.executable, str(ROOT / "scripts" / "alert.py"),
                                f"{chat}: models are working again, cycle completed. Resuming normally.",
                                "--key", "models_recovered", "--no-dedupe"],
                               cwd=ROOT, timeout=60)
                guard.unlink(missing_ok=True)
            except Exception as e:
                print(f"[{chat}] recovery alert could not be sent: {e}")
    time.sleep(max(60, min_cycle - (time.time() - start)))
