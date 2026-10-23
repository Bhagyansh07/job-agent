# Company discovery (chat3)
Goal: find recently-hiring companies (fresh postings, not months old), as many as possible, and watch/apply on their career pages.
Per cycle find 10-20 new companies from skills/portals/hn_and_startup_sources.md sources.
For each company:
1. Identify ATS from the careers URL: boards.greenhouse.io/<token> | jobs.lever.co/<token> | jobs.ashbyhq.com/<token>.
2. If supported -> append to config/watchlist.yaml (`- {name: X, ats: lever, token: x}`) so the watcher checks it every 30 min.
3. If not supported (Workday, SmartRecruiters, custom page, Zoho Recruit, Keka, etc.) -> open the careers page now, look for fresh matching roles and apply directly (cap `career_pages`).
4. Prefer: product companies, funded startups (recent funding news), Delhi NCR/Gurgaon/Noida/Jaipur/remote India. Skip service-body-shop spam.
Keep a small log in state/discovered_companies.txt (name | url | date) to avoid repeats.
