"""Probe and repair the career-page watchlist against the real ATS APIs.

    python scripts/probe_ats.py --check                 # verify every entry in config/watchlist.yaml
    python scripts/probe_ats.py --discover "Razorpay"   # find the working greenhouse/lever/ashby slug
    python scripts/probe_ats.py --discover-file state/import/companies.txt --json

Why: a wrong slug returns 404 and the watcher prints "company failed" forever. The queue then
looks empty and chat3 quietly starves. This tool tells you which entries are actually alive.

Exit codes: 0 all good / discovery done, 1 some watchlist entry is dead, 2 usage error.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UA = {"User-Agent": "Mozilla/5.0 (compatible; job-agent-watchlist-probe)"}
API = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{tok}/jobs",
    "lever": "https://api.lever.co/v0/postings/{tok}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{tok}",
}
INDIA = re.compile(r"india|bengaluru|bangalore|hyderabad|pune|gurgaon|gurugram|noida|delhi|"
                   r"mumbai|jaipur|chennai|kolkata|ahmedabad|remote", re.I)


def fetch(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def jobs_of(ats: str, payload: str):
    try:
        d = json.loads(payload)
    except Exception:
        return []
    if ats == "greenhouse":
        return d.get("jobs") or []
    if ats == "lever":
        return d if isinstance(d, list) else []
    if ats == "ashby":
        return d.get("jobs") or []
    return []


def probe(ats: str, token: str) -> dict:
    url = API[ats].format(tok=token)
    status, body = fetch(url)
    jobs = jobs_of(ats, body) if status == 200 else []
    titles = [str(j.get("title") or j.get("text") or "") for j in jobs]
    locs = []
    for j in jobs:
        loc = j.get("location") or (j.get("categories") or {}).get("location") or ""
        if isinstance(loc, dict):
            loc = loc.get("name", "")
        locs.append(str(loc))
    india = sum(1 for x in locs + titles if INDIA.search(x))
    return {"ats": ats, "token": token, "status": status, "jobs": len(jobs),
            "india": india, "url": url,
            "sample": titles[:3]}


def candidates(name: str) -> list[str]:
    base = re.sub(r"[^a-z0-9]", "", name.lower())
    raw = re.sub(r"\s+", "", name.lower())
    out = [raw, base, base + "hq", base + "inc", base + "india", base + "careers",
           base + "software", base + "technologies", base + "labs", base + "global",
           raw.replace(" ", "-"), base + "1", base + "app"]
    seen, uniq = set(), []
    for c in out:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def discover(name: str) -> list[dict]:
    work = [(ats, tok) for tok in candidates(name) for ats in API]
    hits = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for res in ex.map(lambda p: probe(*p), work):
            if res["status"] == 200 and res["jobs"] > 0:
                hits.append(res)
    hits.sort(key=lambda r: (r["india"], r["jobs"]), reverse=True)
    return hits


def load_watchlist() -> list[dict]:
    import yaml
    p = ROOT / "config" / "watchlist.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("companies") or []


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify / discover ATS board slugs")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--discover", default="")
    g.add_argument("--discover-file", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.check:
        rows = load_watchlist()
        dead, alive = [], []
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(probe, c["ats"], c["token"]): c for c in rows}
            for f in cf.as_completed(futs):
                c = futs[f]
                r = f.result()
                (alive if r["status"] == 200 and r["jobs"] else dead).append((c, r))
        alive.sort(key=lambda x: (x[1]["india"], x[1]["jobs"]), reverse=True)
        if a.json:
            print(json.dumps({"alive": [{"name": c["name"], **r} for c, r in alive],
                              "dead": [{"name": c["name"], **r} for c, r in dead]}, indent=1))
        else:
            print(f"ALIVE {len(alive)}/{len(rows)}")
            for c, r in alive:
                print(f"  OK   {c['name']:<16} {c['ats']:<10} {c['token']:<24} "
                      f"jobs={r['jobs']:<3} india={r['india']}")
            if dead:
                print(f"DEAD {len(dead)}/{len(rows)} (wrong slug, company moved ATS, or no public board)")
                for c, r in dead:
                    print(f"  DEAD {c['name']:<16} {c['ats']:<10} {c['token']:<24} http={r['status']}")
        return 1 if dead else 0

    names = []
    if a.discover:
        names = [a.discover]
    else:
        names = [ln.strip() for ln in Path(a.discover_file).read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
    out = {}
    for n in names:
        hits = discover(n)
        out[n] = hits
        if not a.json:
            print(f"\n{n}: {len(hits)} board(s)")
            for h in hits[:5]:
                print(f"  {h['ats']:<10} {h['token']:<24} jobs={h['jobs']:<4} india={h['india']:<3} "
                      f"| {h['sample']}")
    if a.json:
        print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
