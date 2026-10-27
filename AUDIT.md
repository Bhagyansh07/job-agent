# AUDIT - 2026-10-27 (final pre-run audit)

Scope: the live project at `C:\Users\bhagy\Downloads\job-agent`: scripts, configs, docs, resume,
watcher throughput, tracker state, renderer, health check, and the GitHub copy.

Verdict: the infrastructure works (compile clean, renderer produces a 1-page ATS-readable PDF,
Telegram reachable, 20/20 watchlist boards live). It was **not** applying anything: 5 rows ever,
all `dry_skipped`, because `DRY_RUN=1` and because 19 of 27 watchlist boards returned 404.

## Fixed on 2026-10-27

| # | Severity | Problem | Fix |
|---|---|---|---|
| 1 | HIGH | `config/watchlist.yaml` had 27 companies, 19 returned 404 (Razorpay, PhonePe, Swiggy, Zomato, Zepto, Blinkit, UrbanCompany, Dunzo, Jupiter, Fi, Niyo, Open, Jar, PostHog, Linear, Railway, Cal.com, Trigger.dev, Plane). The watcher skipped them silently. | Replaced with 20 boards probed live the same day. 6 companies moved to their real token: Zomato -> `lever:eternal`, Fi -> `lever:fi`, PostHog/Linear/Railway/Plane -> ashby. |
| 2 | HIGH | `watcher.py` deleted `state/seen_jobs.json` (3085 keys) after importing it into memory only, so 3085 remembered jobs became "new" again (the JSONL had 30 rows). | Legacy keys are appended to `seen_jobs.jsonl` before the old file is removed. |
| 3 | HIGH | The queue re-added jobs that were already waiting in it (the seen-list is per URL, the queue is append-only). Duplicate rows meant duplicate applications. | Watcher now loads `queue/new_jobs.jsonl` URLs and skips them. Existing duplicate rows were merged (22 -> 9). |
| 4 | HIGH | `resume/master.json` ended with "Seeking to bring ... to **Amazon's ML data operations**". That line rendered into every PDF. | Neutral, software-engineering summary. Per-job targeting belongs in the tailored JSON. |
| 5 | HIGH | `skills/apply_flow.md` documented exit `3` for a missing `master.json` and `other` for render errors. `render_resume.py` only ever exits `0`, `2` (guard) or `1` (everything else). | Table corrected, with a `master.json` JSON check command. |
| 6 | MEDIUM | `tracker.py add` prefixed `dry_` unconditionally, so an agent following HARD RULE 16 (`dry_skipped`) wrote `dry_dry_skipped`. | Prefix is only added when the status is not already `dry_`. |
| 7 | MEDIUM | Queue rows stored `age_days` at queue time and no timestamp, so a job queued 2 days ago still read "1 day old" and skipped the freshness rule. | `queued_at` (UTC ISO) added to every queue row. |
| 8 | MEDIUM | `health_check.py` did not check the things that had broken: opencode CLI, MCP servers, watchlist liveness, seen/queue counts. | Four checks added. Watchlist probe is warn-only and can be skipped with `--no-net`. |
| 9 | MEDIUM | README told you to run `start_all.ps1`, `stop_all.ps1`, `register_startup.ps1`, but the files were missing from this copy. | Restored from the GitHub copy (they were never deleted upstream). |
| 10 | LOW | `.env.example` defaulted to `DRY_RUN=0`, so a fresh clone starts submitting immediately. | Default is now `DRY_RUN=1`. |
| 11 | LOW | `scripts/run_loop.py.bak_fix_doubleload` and one-off audit scripts sat in the repo root. | Removed / moved to the local-only `tools/local/` folder (gitignored). |

## Still open (by design, needs you)

- **`DRY_RUN=1` in `.env`.** Nothing is submitted. Flip to `0` when you have watched 5-10 applications.
- **Google not configured.** `secrets/` has no `credentials.json` / `token.json`, `GOOGLE_SHEET_ID` is empty.
  Gmail OTP reading and Sheet sync stay off, so any portal that needs an email OTP will block. Fix: README step 5.
- **Apollo / Hunter keys empty.** Cold-email lead search and email resolution are off. Draft mode still works.
- **`outreach.mode: auto`** in `config/profile.yaml`. It is gated by `DRY_RUN` today. The moment you set
  `DRY_RUN=0`, the agent starts sending LinkedIn connection requests and DMs (12/day). Set `mode: draft` if that is not wanted.
- **No git history before 2026-10-27.** The repo was re-initialised; earlier local changes were not committed.
- **Portal ToS.** Naukri / LinkedIn / Indeed / Instahyre do not allow automation. Caps, human delays and
  the 08:00-23:30 window reduce the risk; they do not remove it. `opencode.json` permissions are a
  best-effort guard, not a sandbox.
- **Throughput.** The pipeline can queue jobs but the filters are tight: Bengaluru/Hyderabad/Pune/Mumbai
  require double-digit CTC in `config/profile.yaml`, and senior/2+ year roles are dropped. Expect far
  fewer than 100 applications/day; tune `locations` and `posting_age` if that is not acceptable.
- **Two agents on one folder.** During this audit another session edited 14 files in 30 minutes
  (10:38-11:07). Run one copy of the project at a time, or use a separate worktree per chat.
