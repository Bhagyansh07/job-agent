"""Career-page watcher (greenhouse / lever / ashby public JSON APIs).
Runs every 30 min via run_loop.py (chat3). New fresh matching jobs are appended to queue/new_jobs.jsonl."""
import json, re, time, datetime as dt, urllib.request
from common import ROOT, cfg

SEEN = ROOT / "state" / "seen_jobs.json"
QUEUE = ROOT / "queue" / "new_jobs.jsonl"


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
            out.append((j.get("title", ""), (j.get("location") or {}).get("name", ""), j.get("absolute_url", ""), j.get("updated_at")))
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
