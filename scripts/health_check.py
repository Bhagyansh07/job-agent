"""Health check / heartbeat. Run at the start of every cycle (run_loop.py does it).

    python scripts/health_check.py            # full report, exit 1 if any FAIL
    python scripts/health_check.py --quiet    # print only WARN/FAIL lines
    python scripts/health_check.py --json     # machine-readable, nothing else

Why: a 24x7 agent that loses its Telegram token or its resume can keep "working"
for days while nothing reaches Bhagyansh. This catches that in seconds.

Never prints secret VALUES, only whether a key is present.
Writes state/health.json so the dashboard / next cycle can see the last result.
Exit codes: 0 all good, 1 at least one FAIL, 2 could not write the report.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from common import ROOT as _ROOT, load_env  # noqa: E402  (loads .env)

HEALTH = ROOT / "state" / "health.json"
FAILS: list[str] = []
WARNS: list[str] = []
OKS: list[str] = []


def ok(name: str, detail: str = "") -> None:
    OKS.append(f"OK   {name}" + (f" - {detail}" if detail else ""))


def warn(name: str, detail: str = "") -> None:
    WARNS.append(f"WARN {name}" + (f" - {detail}" if detail else ""))


def fail(name: str, detail: str = "") -> None:
    FAILS.append(f"FAIL {name}" + (f" - {detail}" if detail else ""))


def check_python() -> None:
    v = sys.version_info
    if (v.major, v.minor) >= (3, 10):
        ok("python", f"{v.major}.{v.minor}.{v.micro}")
    else:
        fail("python", f"{v.major}.{v.minor} found, need 3.10+ (zoneinfo/tzdata)")


def check_modules() -> None:
    missing = []
    for mod, pkg in [("yaml", "pyyaml"), ("reportlab", "reportlab"),
                     ("googleapiclient", "google-api-python-client"),
                     ("google_auth_oauthlib", "google-auth-oauthlib"),
                     ("pypdf", "pypdf")]:
        try:
            __import__(mod)
        except Exception:
            missing.append(pkg)
    if missing:
        fail("pip packages", "missing: " + ", ".join(missing) + " -> pip install -r requirements.txt")
    else:
        ok("pip packages", "all present")


def check_env() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if token and ":" in token and len(token) > 20:
        ok("TELEGRAM_BOT_TOKEN", "present")
    else:
        fail("TELEGRAM_BOT_TOKEN", "missing/short in .env -> BotFather /newbot")
    if chat.lstrip("-").isdigit():
        ok("TELEGRAM_CHAT_ID", "present")
    else:
        fail("TELEGRAM_CHAT_ID", "missing/not numeric in .env -> @userinfobot")
    if not os.environ.get("GOOGLE_SHEET_ID", "").strip():
        warn("GOOGLE_SHEET_ID", "empty: tracker works, Sheet sync off")
    if not os.environ.get("APOLLO_API_KEY", "").strip():
        warn("APOLLO_API_KEY", "empty: Apollo lead search off")
    if not os.environ.get("HUNTER_API_KEY", "").strip():
        warn("HUNTER_API_KEY", "empty: email resolve uses no fallback")


def check_telegram() -> None:
    try:
        from common import tg_api
        r = tg_api("getMe", {}, timeout=15)
        if r.get("ok"):
            ok("telegram", "bot reachable as @" + str((r.get("result") or {}).get("username", "?")))
        else:
            fail("telegram", "getMe returned not ok")
    except SystemExit as exc:
        fail("telegram", str(exc))
    except Exception as exc:  # noqa: BLE001
        fail("telegram", f"cannot reach API: {type(exc).__name__} (token revoked or no internet)")


def check_google() -> None:
    cred = ROOT / "secrets" / "credentials.json"
    tok = ROOT / "secrets" / "token.json"
    tok_send = ROOT / "secrets" / "token_send.json"
    if cred.exists():
        try:
            d = json.loads(cred.read_text(encoding="utf-8-sig"))
            if "installed" in d or "web" in d:
                ok("credentials.json", "OAuth client present")
            else:
                fail("credentials.json", "no 'installed'/'web' block - wrong file downloaded")
        except Exception:
            fail("credentials.json", "not valid JSON")
    else:
        warn("credentials.json", "missing -> Gmail/Sheets off (run scripts/google_auth.py after adding it)")
    if tok.exists():
        ok("token.json", "read scope token present")
    else:
        warn("token.json", "missing -> run python scripts/google_auth.py")
    if tok_send.exists():
        ok("token_send.json", "gmail.send token present")
    else:
        warn("token_send.json", "missing -> run python scripts/google_auth.py --send (cold email send only)")


def check_resume() -> None:
    p = ROOT / "resume" / "master.json"
    if not p.exists():
        fail("resume/master.json", "missing -> rebuild from your PDF (chats/00_first_run.md)")
        return
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        fail("resume/master.json", f"invalid JSON: {type(exc).__name__}")
        return
    need = ["name", "contact", "summary", "skills", "projects", "education"]
    missing = [k for k in need if not d.get(k)]
    if missing:
        fail("resume/master.json", "empty/missing: " + ", ".join(missing))
    else:
        ok("resume/master.json", f"{len(d.get('projects') or [])} projects, "
                                 f"{len(d.get('skills') or {})} skill groups")
    if d.get("name") and "example" in str(d.get("name", "")).lower():
        fail("resume/master.json", "still the example/sample content")


def check_configs() -> None:
    try:
        import yaml
    except Exception:
        return
    required = {
        "profile.yaml": ["candidate", "roles_include", "roles_exclude_title", "limits",
                         "match", "salary_lpa", "locations", "posting_age", "experience"],
        "answers.yaml": ["expected_ctc_lpa", "notice_period", "graduation_year", "cgpa"],
        "cold_email.yaml": ["mode", "daily_cap", "warmup_week1", "warmup_week2"],
        "watchlist.yaml": ["companies"],
    }
    for name, keys in required.items():
        p = ROOT / "config" / name
        if not p.exists():
            fail("config/" + name, "missing")
            continue
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8-sig")) or {}
        except Exception as exc:  # noqa: BLE001
            fail("config/" + name, f"YAML error: {type(exc).__name__}")
            continue
        miss = [k for k in keys if k not in d]
        if miss:
            fail("config/" + name, "missing keys: " + ", ".join(miss))
        else:
            extra = ""
            if name == "watchlist.yaml":
                extra = f" ({len(d.get('companies') or [])} companies)"
            if name == "cold_email.yaml":
                extra = f" (mode={d.get('mode')})"
            ok("config/" + name, "valid" + extra)


def check_disk() -> None:
    try:
        u = shutil.disk_usage(ROOT)
        free_gb = u.free / (1024 ** 3)
        if free_gb < 1:
            fail("disk", f"{free_gb:.1f} GB free - PDFs/logs will start failing")
        elif free_gb < 3:
            warn("disk", f"{free_gb:.1f} GB free")
        else:
            ok("disk", f"{free_gb:.0f} GB free")
    except Exception as exc:  # noqa: BLE001
        warn("disk", f"cannot measure: {type(exc).__name__}")


def check_writable() -> None:
    probe = ROOT / "state" / ".write_probe"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        ok("state writable", "yes")
    except Exception as exc:  # noqa: BLE001
        fail("state writable", f"{type(exc).__name__}: cannot write state/")


def check_browser_profiles() -> None:
    base = ROOT / "browser-profiles"
    for chat in ("chat1", "chat2", "chat3"):
        d = base / chat
        if not d.exists():
            warn(f"browser-profiles/{chat}", "missing - will be created on first manual login")
        elif not any(d.iterdir()):
            warn(f"browser-profiles/{chat}", "empty - log in once on first run")
        else:
            ok(f"browser-profiles/{chat}", "profile present")


def check_pause() -> None:
    paused = [p.name for p in (ROOT / "state").glob("PAUSE*")]
    if paused:
        warn("pause", "PAUSE file(s) present: " + ", ".join(paused) + " - cycles will wait")
    else:
        ok("pause", "none")


def check_mcp_servers() -> None:
    """The browser lives in the MCP config, so a wrong shape there = agent cannot browse.

    Three things bit us for real (see AUDIT.md):
      - V2 reads `mcp.servers`, not `mcp.<name>` (legacy keys still load but are ignored by
        `opencode mcp list` style tooling and are easy to mis-edit).
      - with Code Mode on, MCP tools never reached the model in `opencode run`, so the agent
        silently fell back to webfetch. `codemode: false` is what makes browser tools usable.
      - a headed Chrome never closes on its own. `--idle-timeout` closes it when a cycle is
        idle, which is the actual fix for the fan/CPU noise.
    """
    cfg_path = ROOT / "opencode.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        fail("opencode.json", f"{type(exc).__name__} -> run_loop cannot start chats")
        return
    mcp = cfg.get("mcp") or {}
    servers = mcp.get("servers") if isinstance(mcp.get("servers"), dict) else {
        k: v for k, v in mcp.items() if isinstance(v, dict) and "command" in v}
    if not servers:
        fail("opencode.json", "no mcp servers -> no browser, agent cannot apply")
        return
    ok("mcp servers", f"{len(servers)}: " + ", ".join(sorted(servers)))

    no_idle, codemode_on, dirs, broken = [], [], {}, []
    for name, srv in sorted(servers.items()):
        cmd = srv.get("command") or []
        cmd = [str(c) for c in cmd]
        if not cmd:
            broken.append(name)
            continue
        if "--idle-timeout" not in cmd:
            no_idle.append(name)
        if srv.get("codemode") is not False:
            codemode_on.append(name)
        if "--user-data-dir" in cmd:
            i = cmd.index("--user-data-dir")
            if i + 1 < len(cmd):
                dirs.setdefault(cmd[i + 1].replace("\\", "/"), []).append(name)

    if broken:
        fail("mcp command", "empty command for: " + ", ".join(broken))
    if codemode_on:
        fail("mcp codemode", "not false for: " + ", ".join(codemode_on)
             + " -> browser tools stay hidden from the model, agent falls back to webfetch")
    else:
        ok("mcp codemode", "off everywhere (browser tools reach the model directly)")
    if no_idle:
        warn("mcp idle-timeout", "missing on: " + ", ".join(no_idle)
             + " -> headed Chrome stays open after a cycle and eats CPU/RAM")
    else:
        ok("mcp idle-timeout", "set on every server (Chrome closes when idle)")
    shared = {d: names for d, names in dirs.items() if len(names) > 1}
    if shared:
        fail("mcp profiles", "same --user-data-dir for multiple chats: " + str(shared))
    if len(dirs) != len(servers):
        warn("mcp profiles", f"{len(dirs)} user-data-dir(s) for {len(servers)} servers")
    elif not shared:
        ok("mcp profiles", "separate profile per chat (" + ", ".join(sorted(dirs)) + ")")


def check_runner() -> None:
    """run_loop.py needs the opencode CLI and the Playwright MCP servers. Neither was checked."""
    exe = shutil.which("opencode")
    if not exe:
        fail("opencode CLI", "not on PATH -> npm install -g opencode-ai (run_loop.py cannot start a cycle)")
    else:
        try:
            r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=25)
            v = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
            ok("opencode CLI", v[0] if v else "present")
        except Exception as exc:  # noqa: BLE001
            warn("opencode CLI", f"present but --version failed: {type(exc).__name__}")
    check_mcp_servers()



def check_pipeline() -> None:
    """A watcher that queues nothing looks healthy. Show the actual numbers."""
    seen = ROOT / "state" / "seen_jobs.jsonl"
    queue = ROOT / "queue" / "new_jobs.jsonl"
    try:
        seen_n = sum(1 for _ in seen.open(encoding="utf-8", errors="replace")) if seen.exists() else 0
    except OSError:
        seen_n = 0
    try:
        queue_n = sum(1 for line in queue.open(encoding="utf-8", errors="replace") if line.strip()) if queue.exists() else 0
    except OSError:
        queue_n = 0
    if seen_n == 0:
        warn("watcher memory", "state/seen_jobs.jsonl empty -> run python scripts/watcher.py once")
    else:
        ok("watcher memory", f"{seen_n} job urls remembered")
    if queue_n == 0:
        warn("queue", "empty -> no jobs to apply to (run scripts/watcher.py)")
    else:
        ok("queue", f"{queue_n} pending job(s)")


def check_watchlist_live() -> None:
    """Probe every board token. 19 dead tokens stayed invisible until this check existed."""
    try:
        import urllib.request
        from concurrent.futures import ThreadPoolExecutor
        import yaml
        companies = (yaml.safe_load((ROOT / "config" / "watchlist.yaml").read_text(encoding="utf-8-sig")) or {}).get("companies") or []
    except Exception:
        return
    if not companies:
        return
    urls = {
        "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{}/jobs",
        "lever": "https://api.lever.co/v0/postings/{}?mode=json",
        "ashby": "https://api.ashbyhq.com/posting-api/job-board/{}",
    }

    def probe(c: dict) -> tuple[str, bool]:
        tpl = urls.get(str(c.get("ats", "")).lower())
        if not tpl:
            return str(c.get("name", "?")), False
        req = urllib.request.Request(tpl.format(c.get("token", "")),
                                     headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as r:   # 6s gave false "dead board" warnings
                return str(c.get("name", "?")), 200 <= r.status < 300
        except Exception:
            return str(c.get("name", "?")), False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, companies))
    dead = [name for name, alive in results if not alive]
    if not dead:
        ok("watchlist live", f"all {len(results)} boards return jobs")
    elif len(dead) == len(results):
        fail("watchlist live", f"all {len(results)} boards dead -> check internet or config/watchlist.yaml")
    else:
        shown = ", ".join(dead[:6]) + (" ..." if len(dead) > 6 else "")
        warn("watchlist live", f"{len(results) - len(dead)}/{len(results)} alive, dead: {shown}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-flight health check")
    ap.add_argument("--quiet", action="store_true", help="only WARN/FAIL lines")
    ap.add_argument("--json", action="store_true", help="JSON output only")
    ap.add_argument("--no-net", action="store_true", help="skip live watchlist probe")
    a = ap.parse_args()

    check_python()
    check_modules()
    check_env()
    check_telegram()
    check_google()
    check_resume()
    check_configs()
    check_disk()
    check_writable()
    check_browser_profiles()
    check_pause()
    check_runner()
    check_pipeline()
    if not a.no_net:
        check_watchlist_live()

    status = "FAIL" if FAILS else ("WARN" if WARNS else "OK")
    report = {
        "ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "fails": FAILS,
        "warns": WARNS,
        "oks": OKS,
        "dry_run": os.environ.get("DRY_RUN", "1"),
    }
    try:
        HEALTH.parent.mkdir(parents=True, exist_ok=True)
        tmp = HEALTH.with_suffix(".tmp")
        tmp.write_text(json.dumps(report, indent=1), encoding="utf-8")
        tmp.replace(HEALTH)
    except Exception as exc:  # noqa: BLE001
        if not a.json:
            print(f"HEALTH_REPORT_WRITE_FAILED: {type(exc).__name__}")
        return 2

    if a.json:
        print(json.dumps(report, indent=1))
        return 1 if FAILS else 0

    if not a.quiet:
        for line in OKS:
            print(line)
    for line in WARNS + FAILS:
        print(line)
    print(f"HEALTH {status} | ok={len(OKS)} warn={len(WARNS)} fail={len(FAILS)} | DRY_RUN={report['dry_run']}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
