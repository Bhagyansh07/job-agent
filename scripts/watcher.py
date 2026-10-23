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
            out.append((j.get("title", ""), loc, j.get("absolute_url", ""), j.get("updated_at")))
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
    max_age = p["posting_age"]["stretch_max"]
    wl = cfg("watchlist.yaml").get("companies") or []
    seen_list = json.loads(SEEN.read_text()) if SEEN.exists() else []   # keep insertion order
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
                if not any(i in tl for i in inc) or any(x in tl for x in exc):
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
    SEEN.write_text(json.dumps(seen_list[-20000:]))
    print(f"watcher: {new} new matching jobs queued ({len(wl)} companies)")


if __name__ == "__main__":
    main()
