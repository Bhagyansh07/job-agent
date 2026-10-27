# AUDIT - 2026-10-27 (final pre-run audit)

Scope: the live project at `C:\Users\bhagy\Downloads\job-agent`: scripts, configs, docs, resume,
watcher throughput, tracker state, renderer, health check.

Verdict: the infrastructure works. All 18 scripts compile, the 51-check regression suite passes,
the renderer produces a 1-page ATS-readable PDF, Telegram is reachable, and 16/16 watchlist boards
answer live with at least one junior engineering role in India. Nothing has been auto-submitted yet
because `DRY_RUN=1` (by design).

## Fixed on 2026-10-27

| # | Severity | Problem | Fix |
|---|---|---|---|
| 1 | HIGH | `config/watchlist.yaml` had 27 companies, 19 returned 404 (Razorpay, PhonePe, Swiggy, Zomato, Zepto, Blinkit, UrbanCompany, Dunzo, Jupiter, Fi, Niyo, Open, Jar, Cal.com...). The watcher skipped them silently, so chat3 slowly starved. | Every board is now probed before it is added. Final list = 16 companies, all live, all with junior roles in India. `scripts/probe_ats.py --check` is the gate; `--discover "<Company>"` finds a working token. |
| 2 | HIGH | The list was also full of senior-only boards (MongoDB, Cloudflare, Stripe, Datadog, Elastic, GitLab, Linear, Railway). They returned hundreds of 3+ year jobs, which is why "MongoDB" kept showing up in a fresher's log. | Removed from the fresher watchlist; documented in the file so they are not re-added by accident. |
| 3 | HIGH | `watcher.py` applied the 8-14 day "is it still active" rule to 4-7 day jobs as well (`fresh_max` instead of `extended_max`). Every legitimately fresh job from day 4 onwards was dropped. | Gate now starts at `posting_age.extended_max` (7). 4-7 day jobs pass and are score-gated later, exactly as `AGENTS.md` rule 10 says. |
| 4 | HIGH | Role matching was naive substring: `intern` was missing from the include list, and adding it would have queued "Internal Audit" and "International Sales". Trailing seniority (`Software Development Engineer in Test II`) was not caught either. | Includes and excludes both use word boundaries now. Added intern/internship, SDET, product/platform/cloud/data/QA engineer, graduate trainee, junior. Seniority regex catches `Engineer in Test II`, `Level 3`, `Developer 2`. |
| 5 | HIGH | `watcher.py` deleted `state/seen_jobs.json` (3085 keys) after importing it into memory only, so remembered jobs became "new" again. | Legacy keys are written to `seen_jobs.jsonl` before the old file is removed. |
| 6 | HIGH | The queue re-added jobs already waiting in it, which meant duplicate applications. | Watcher loads `queue/new_jobs.jsonl` URLs and skips them. |
| 7 | HIGH | `resume/master.json` ended with "Seeking to bring ... to Amazon's ML data operations" and claimed a full certification that was only foundations. | Neutral software-engineering summary; certification wording matches the certificate. Render smoke test: PAGES 1, ATS_TEXT_OK. |
| 8 | HIGH | `skills/apply_flow.md` documented exit `3` for a missing `master.json`; `render_resume.py` only ever exits `0`, `2` or `1`. | Table corrected, plus browser-crash and prompt-injection steps. |
| 9 | MEDIUM | `tracker.py add` prefixed `dry_` unconditionally, producing `dry_dry_skipped`. | Prefix only added when the status is not already `dry_`. |
| 10 | MEDIUM | Queue rows stored `age_days` at queue time with no timestamp, so a job queued 2 days ago still read "1 day old". | `queued_at` (UTC ISO) on every row. |
| 11 | MEDIUM | `health_check.py` did not check the things that actually broke (opencode CLI, MCP servers, watchlist liveness, queue/seen counts, disk, profiles). | Added; `--no-net` skips the network probe. |
| 12 | MEDIUM | A board that 404s failed silently forever. | `state/watcher_dead.json` counts consecutive failures; after 3 cycles a Telegram alert fires (max once per 12h). |
| 13 | MEDIUM | LinkedIn and cold-email templates sold React/Node, but the resume is Java/JSP/SQL + GCP. | Templates rewritten to the real stack. CGPA is 9.27 everywhere (two templates still said 9.25). |
| 14 | MEDIUM | Em/en dashes had replaced `|` separators during an earlier edit, corrupting resumes and messages. | All text files normalised to plain hyphens; `tools/verify_fixes.py` fails the build if one comes back. |
| 15 | LOW | `.env.example` defaulted to `DRY_RUN=0`, so a fresh copy would submit immediately. | Default is `DRY_RUN=1`. |
| 16 | LOW | `chat1.md` and `chat3.md` referenced a combined `internshala_unstop.md` that contradicted the newer per-portal playbooks (it still listed Node/React filters). | Chats now point at `internshala.md` and `unstop.md`; the old file is a pointer only. |
| 17 | LOW | README told you to `git clone` a repo that returns 404. | Replaced with zip-based setup for a second laptop. |
| 18 | LOW | One-off audit scripts sat in the project root and in `tools/local/`. | Removed before packaging; only `tools/verify_fixes.py` ships. |

## Still open (by design, needs you)

- **`DRY_RUN=1` in `.env`.** Nothing is submitted. Flip to `0` after watching 5-10 applications.
- **Google not configured.** `secrets/` has no `credentials.json` / `token.json`, `GOOGLE_SHEET_ID` is empty.
  Gmail OTP reading and Sheet sync stay off, so portals that need an email OTP will block. Fix: README step 5.
- **Apollo / Hunter keys empty.** Cold-email lead search and email resolution are off. Draft mode still works.
- **`outreach.mode: auto`** in `config/profile.yaml`. It is gated by `DRY_RUN` today. The moment you set
  `DRY_RUN=0`, the agent starts sending LinkedIn connection requests and DMs (12/day). Set `mode: draft` if that is not wanted.
- **Career pages are a thin channel.** On 2026-10-27 the 16 boards held 692 live listings, but only 3 passed
  role + seniority + location + freshness. That is the market, not a bug: most Indian product boards are
  hiring senior right now. Volume has to come from Naukri, LinkedIn, Internshala, Unstop, Instahyre.
  To widen it, raise `posting_age.hard_skip_over` (14) and `stretch_max` (14) in `config/profile.yaml`.
- **No git history.** The project is local-only; there is no remote repository.
- **Portal ToS.** Naukri / LinkedIn / Indeed / Instahyre do not allow automation. Caps, human delays and
  the 08:00-23:30 window reduce the risk; they do not remove it. `opencode.json` permissions are a
  best-effort guard, not a sandbox.
- **Two agents on one folder.** During this audit another session edited 14 files in 30 minutes. Run one
  copy of the project at a time, or use a separate worktree per chat.
