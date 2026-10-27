"""Career-page watcher (greenhouse / lever / ashby public JSON APIs).
Runs every 30 min via run_loop.py (chat3). New fresh matching jobs are appended to queue/new_jobs.jsonl.

Seen jobs live in state/seen_jobs.jsonl (append-only). The old single JSON array was
rewritten in full every 30 minutes; with 20k+ URLs that is a pointless O(n) write and a
corruption risk if the process dies mid-write. The legacy .json is still read once.
"""
import json, re, time, datetime as dt, urllib.request
from common import ROOT, cfg

SEEN_JSONL = ROOT / "state" / "seen_jobs.jsonl"
SEEN_LEGACY = ROOT / "state" / "seen_jobs.json"
QUEUE = ROOT / "queue" / "new_jobs.jsonl"
DEAD_FILE = ROOT / "state" / "watcher_dead.json"
SEEN_MAX = 30000          # compact above this
SEEN_KEEP = 20000         # keep the newest N on compaction
ACTIVE_EDIT_DAYS = 7      # a 4-14 day old job must have been edited/relisted this recently

# Jobs that name a non-India region are dropped at discovery time. The agent then
# never wastes a cycle opening a US/EU posting. Bare "remote" without a country stays.
FOREIGN = re.compile(
    r"\b(united states|u\.s\.a?|usa|amer|canada|emea|europe|european union|united kingdom|uk|"
    r"london|dublin|berlin|munich|amsterdam|paris|madrid|barcelona|singapore|australia|sydney|"
    r"japan|tokyo|korea|seoul|toronto|vancouver|new york|austin|seattle|san francisco|palo alto|"
    r"chicago|boston|los angeles|denver|atlanta|dallas|washington|poland|warsaw|germany|france|"
    r"spain|netherlands|ireland|sweden|switzerland|portugal|romania|czech|hungary|turkey|brazil|"
    r"mexico|argentina|south africa|uae|dubai|saudi|qatar|israel|taiwan|hong kong|china|malaysia|"
    r"indonesia|philippines|vietnam|thailand|new zealand|remote\s*[-]\s*us|remote\s*us)\b",
    re.I)


def loc_ok(loc: str, p: dict) -> bool:
    if not loc:
        return True
    if re.search(r"\b(US|USA|U\.S\.)\b", loc):      # uppercase country code, "join us" stays safe
        return False
    if FOREIGN.search(loc):
        return False
    allowed = []
    for bucket in ("tier1", "tier2", "other_requires_double_digit_ctc"):
        allowed += [str(x).lower() for x in p["locations"].get(bucket, [])]
    allowed += ["india", "remote", "hybrid", "onsite", "work from home", "wfh"]
    low = loc.lower()
    return any(k in low for k in allowed)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def age_days(iso_or_ms):
    if not iso_or_ms:
        return None
    try:
        if isinstance(iso_or_ms, (int, float)):
            d = dt.datetime.fromtimestamp(iso_or_ms / 1000, dt.timezone.utc)
        else:
            d = dt.datetime.fromisoformat(str(iso_or_ms).replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - d).days
    except Exception:
        return None


def jobs_for(c):
    ats, tok = c["ats"], c["token"]
    out = []
    if ats == "greenhouse":
        for j in get(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs").get("jobs", []):
            loc = (j.get("location") or {}).get("name", "")
            if str(loc).strip().lower() in ("", "hybrid", "remote"):
                for m in j.get("metadata") or []:
                    if str(m.get("name", "")).strip().lower() == "job posting location":
                        v = m.get("value")
                        if isinstance(v, list) and v:
                            loc = "; ".join(str(x) for x in v)
                        elif v:
                            loc = str(v)
            # created_at = real posting date; updated_at = last edit (used as an "still active" signal)
            out.append((j.get("title", ""), loc, j.get("absolute_url", ""),
                        j.get("created_at") or j.get("updated_at"),
                        j.get("updated_at"), True))
    elif ats == "lever":
        for j in get(f"https://api.lever.co/v0/postings/{tok}?mode=json"):
            out.append((j.get("text", ""), (j.get("categories") or {}).get("location", ""),
                        j.get("hostedUrl", ""), j.get("createdAt"),
                        j.get("updatedAt"), True))
    elif ats == "ashby":
        for j in get(f"https://api.ashbyhq.com/posting-api/job-board/{tok}").get("jobs", []):
            # isListed=false means the posting was pulled; never queue it
            out.append((j.get("title", ""), j.get("location", ""), j.get("jobUrl", ""),
                        j.get("publishedAt") or j.get("publishedDate"),
                        j.get("updatedAt"), j.get("isListed", True) is not False))
    return out


def load_seen() -> tuple[set, int]:
    """Return (keys, line_count). Reads the new JSONL plus the legacy JSON once."""
    keys: set[str] = set()
    lines = 0
    if SEEN_JSONL.exists():
        with SEEN_JSONL.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                lines += 1
                try:
                    k = json.loads(line)
                    if isinstance(k, str):
                        keys.add(k)
                except Exception:
                    continue
    if not lines and SEEN_LEGACY.exists():
        try:
            old = json.loads(SEEN_LEGACY.read_text(encoding="utf-8"))
            if isinstance(old, list):
                keys |= {str(x) for x in old}
                lines = len(keys)
        except Exception:
            pass
    return keys, lines


def compact_seen(keep: int = SEEN_KEEP) -> None:
    """Keep a bounded file without growing forever. Reads back only when it is too big."""
    if not SEEN_JSONL.exists():
        return
    with SEEN_JSONL.open(encoding="utf-8", errors="replace") as fh:
        rows = fh.readlines()
    if len(rows) <= keep:
        return
    tmp = SEEN_JSONL.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(rows[-keep:])
    tmp.replace(SEEN_JSONL)


def main():
    p = cfg("profile.yaml")
    inc = [x.lower() for x in p["roles_include"]]
    exc = [x.lower() for x in p["roles_exclude_title"]]
    # Word-boundary regex for exclude list (avoids "hr" matching "chrome"/"threading")
    exc_re = re.compile(r'\b(' + '|'.join(re.escape(x.strip()) for x in exc) + r')\b', re.I)
    # Seniority level detection: SDE/SE 2+, Engineer III+
    _lvl_re = re.compile(r'\b(?:sde|se|sr\.?|software engineer|engineer|level)\s*([ivx\d]+)\b', re.I)
    _roman = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6}
    max_age = p["posting_age"]["stretch_max"]
    fresh_max = p["posting_age"]["normal_max"]
    try:
        wl = cfg("watchlist.yaml").get("companies") or []
    except Exception as e:
        print(f"watcher: bad config/watchlist.yaml: {e}")
        return
    seen, seen_lines = load_seen()
    # A job already waiting in the queue must not be queued again (it would be
    # applied twice if the tracker row is not written yet). Seen-list alone is not
    # enough after a migration or a profile edit.
    queued_urls: set[str] = set()
    try:
        if QUEUE.exists():
            with QUEUE.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        u = json.loads(line).get("url")
                        if u:
                            queued_urls.add(str(u))
                    except Exception:
                        continue
    except OSError:
        pass
    emitted = set()
    new = 0
    skipped_stale = 0
    dead: dict[str, int] = {}
    try:
        dead = json.loads(DEAD_FILE.read_text(encoding="utf-8")) if DEAD_FILE.exists() else {}
    except Exception:
        dead = {}
    failed_now = []
    QUEUE.parent.mkdir(exist_ok=True)
    SEEN_JSONL.parent.mkdir(exist_ok=True)
    with SEEN_JSONL.open("a", encoding="utf-8", newline="\n") as seen_fh:
        for c in wl:
            try:
                for title, loc, url, posted, updated, listed in jobs_for(c):
                    key = url or f"{c['name']}|{title}|{loc}"
                    if key in seen:
                        continue
                    seen.add(key)
                    seen_lines += 1
                    seen_fh.write(json.dumps(key, ensure_ascii=False) + "\n")
                    seen_fh.flush()
                    tl = title.lower()
                    # Include: substring match is fine (e.g. "sde 2" matches "sde")
                    if not any(i in tl for i in inc):
                        continue
                    # Exclude: word boundary match (avoids "hr" in "chrome" / "threading")
                    if exc_re.search(tl):
                        continue
                    # Exclude senior levels: SDE 2+, SE 2+, Engineer III+
                    m = _lvl_re.search(title)
                    if m:
                        lvl = m.group(1).lower()
                        if (lvl in _roman and _roman[lvl] >= 2) or (lvl.isdigit() and int(lvl) >= 2):
                            continue
                    if re.search(r'\bIII\b|\bIV\b|\bV\b|\bVI\b', title):
                        continue
                    if not loc_ok(loc, p):
                        continue
                    ck = (c["name"].lower(), tl)
                    if ck in emitted:          # rule 11: same company + same role once
                        continue
                    if url and str(url) in queued_urls:
                        continue               # already waiting in queue/new_jobs.jsonl
                    emitted.add(ck)
                    a = age_days(posted)
                    if a is not None and a > max_age:
                        continue
                    upd = age_days(updated)
                    # 4-14 day old postings need an "still active" signal: edited/relisted recently.
                    # Without this the queue filled with dead 10-day-old posts that fail freshness anyway.
                    if a is not None and a > fresh_max:
                        if not listed:
                            skipped_stale += 1
                            continue
                        if upd is None or upd > ACTIVE_EDIT_DAYS:
                            skipped_stale += 1
                            continue
                    with QUEUE.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({"company": c["name"], "title": title, "location": loc, "url": url,
                                            "age_days": a, "updated_days": upd, "source": c["ats"],
                                            # absolute stamp: age_days alone goes stale while the job waits
                                            "queued_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")},
                                           ensure_ascii=False) + "\n")
                    new += 1
            except Exception as e:
                print(f"watcher: {c.get('name')} failed: {e}")
                failed_now.append(c.get("name", "?"))
                dead[c.get("name", "?")] = dead.get(c.get("name", "?"), 0) + 1
            else:
                dead.pop(c.get("name", "?"), None)
            time.sleep(1)
    if seen_lines > SEEN_MAX:
        compact_seen()
    # One-time migration. The legacy array is imported into memory only, so its keys
    # must be written to the JSONL FIRST - deleting it first loses every remembered job
    # and the whole queue comes back as "new" (happened on 2026-10-27: 3085 -> 30 keys).
    if SEEN_LEGACY.exists():
        try:
            old = json.loads(SEEN_LEGACY.read_text(encoding="utf-8"))
            old_keys = {str(x) for x in old} if isinstance(old, list) else set()
            missing_keys = old_keys - seen
            if missing_keys and SEEN_JSONL.exists():
                with SEEN_JSONL.open("a", encoding="utf-8", newline="\n") as fh:
                    for k in sorted(missing_keys):
                        fh.write(json.dumps(k, ensure_ascii=False) + "\n")
            SEEN_LEGACY.unlink()
            print(f"watcher: migrated {len(missing_keys)} legacy seen keys into seen_jobs.jsonl")
        except Exception as e:
            print(f"watcher: legacy seen_jobs.json left in place: {e}")
    # A dead board (404 / moved ATS) used to fail silently forever. After 3 consecutive
    # cycles, tell Bhagyansh once every 12h so the watchlist can be repaired.
    try:
        DEAD_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEAD_FILE.write_text(json.dumps({k: v for k, v in dead.items() if v}, indent=1),
                             encoding="utf-8")
    except Exception:
        pass
    chronic = sorted(k for k, v in dead.items() if v >= 3)
    if chronic:
        try:
            guard = ROOT / "state" / ".watcher_dead_alert"
            stale = (not guard.exists()) or (time.time() - guard.stat().st_mtime > 12 * 3600)
        except OSError:
            stale = True
        if stale:
            try:
                import subprocess, sys
                subprocess.run([sys.executable, str(ROOT / "scripts" / "alert.py"),
                                "Watchlist boards are dead (3+ failed cycles): "
                                + ", ".join(chronic)
                                + " | run python scripts/probe_ats.py --check and fix config/watchlist.yaml",
                                "--key", "watcher_dead", "--cooldown", "720"],
                               cwd=ROOT, timeout=60)
                guard.write_text(dt.datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
            except Exception as e:
                print(f"watcher: dead-board alert failed: {e}")
    print(f"watcher: {new} new matching jobs queued ({len(wl)} companies, {skipped_stale} stale skipped"
          + (f", {len(failed_now)} board errors" if failed_now else "") + ")")


if __name__ == "__main__":
    main()
