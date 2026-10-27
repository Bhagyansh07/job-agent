# Startup discovery sources (for chat3 discovery)

Caps: discovery is `career_pages` work, cap 30/day shared with the watcher queue, and it counts
as chat3's ONE portal for that cycle. Max 8 applications per cycle, max 10-20 new companies
researched per cycle. Discovery never adds a second portal to a cycle.

- YC job board + Work at a Startup (recent batches: latest 2 batches)
- Hacker News "Who is hiring" (latest monthly thread) + hnhiring.com filters (remote/India)
- Entrackr / Inc42 / YourStory "funding" news in India last 30 days -> recently funded startups hire
- Wellfound new startups, Lenny's Jobs, a16z portfolio jobs, Ramp vendor/startup lists, Breakout List, Next Play newsletter jobs
- Product Hunt launches (last 2 weeks) for tiny startups
For each: find careers page -> discovery.md steps. Only add companies whose ATS is
greenhouse/lever/ashby to `config/watchlist.yaml` (the watcher can only read those three);
everything else gets a direct apply on the career page this cycle.

## General
UI changes often: take a fresh page snapshot, don't rely on fixed selectors. Follow skills/apply_flow.md. Log every decision with tracker.py (portal key shown below).
