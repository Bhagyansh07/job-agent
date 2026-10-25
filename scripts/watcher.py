"""Career-page watcher (greenhouse / lever / ashby public JSON APIs).
Runs every 30 min via run_loop.py (chat3). New fresh matching jobs are appended to queue/new_jobs.jsonl."""
import json, re, time, datetime as dt, urllib.request
from common import ROOT, cfg

SEEN = ROOT / "state" / "seen_jobs.json"
QUEUE = ROOT / "queue" / "new_jobs.jsonl"

# Jobs that name a non-India region are dropped at discovery time. The agent then
# never wastes a cycle opening a US/EU posting. Bare "remote" without a country stays.
FOREIGN = re.compile(
    r"\b(united states|u\.s\.a?|usa|amer|canada|emea|europe|european union|united kingdom|uk|"
    r"london|dublin|berlin|munich|amsterdam|paris|madrid|barcelona|singapore|australia|sydney|"
    r"japan|tokyo|korea|seoul|toronto|vancouver|new york|austin|seattle|san francisco|palo alto|"
    r"chicago|boston|los angeles|denver|atlanta|dallas|washington|poland|warsaw|germany|france|"
    r"spain|netherlands|ireland|sweden|switzerland|portugal|romania|czech|hungary|turkey|brazil|"
    r"mexico|argentina|south africa|uae|dubai|saudi|qatar|israel|taiwan|hong kong|china|malaysia|"
    r"indonesia|philippines|vietnam|thailand|new zealand|remote\s*[-–]\s*us|remote\s*us)\b",
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
            # Use created_at (posting date) instead of updated_at (last-edit) for accurate age
            out.append((j.get("title", ""), loc, j.get("absolute_url", ""), j.get("created_at") or j.get("updated_at")))
    elif ats == "lever":
        for j in get(f"https://api.lever.co/v0/postings/{tok}?mode=json"):
            out.append((j.get("text", ""), (j.get("categories") or {}).get("location", ""), j.get("hostedUrl", ""), j.get("createdAt")))
    elif ats == "ashby":
        for j in get(f"https://api.ashbyhq.com/posting-api/job-board/{tok}").get("jobs", []):
            out.append((j.get("title", ""), j.get("location", ""), j.get("jobUrl", ""), j.get("publishedAt") or j.get("publishedDate")))
    return out


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
    try:
        wl = cfg("watchlist.yaml").get("companies") or []
    except Exception as e:
        print(f"watcher: bad config/watchlist.yaml: {e}")
        return
    try:
        seen_list = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else []
    except Exception:
        seen_list = []
    seen = set(seen_list)
    emitted = set()
    new = 0
    QUEUE.parent.mkdir(exist_ok=True)
    for c in wl:
        try:
            for title, loc, url, posted in jobs_for(c):
                key = url or f"{c['name']}|{title}|{loc}"
                if key in seen:
                    continue
                seen.add(key)
                seen_list.append(key)
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
                emitted.add(ck)
                a = age_days(posted)
                if a is not None and a > max_age:
                    continue
                with QUEUE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"company": c["name"], "title": title, "location": loc, "url": url,
                                        "age_days": a, "source": c["ats"]}, ensure_ascii=False) + "\n")
                new += 1
        except Exception as e:
            print(f"watcher: {c.get('name')} failed: {e}")
        time.sleep(1)
    SEEN.parent.mkdir(exist_ok=True)
    tmp = SEEN.with_suffix(".tmp")
    tmp.write_text(json.dumps(seen_list[-20000:]), encoding="utf-8")
    tmp.replace(SEEN)
    print(f"watcher: {new} new matching jobs queued ({len(wl)} companies)")


if __name__ == "__main__":
    main()
