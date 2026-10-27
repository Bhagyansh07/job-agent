# CHAT 3 - Career pages (ATS), YC, remote boards, drives, discovery   (browser: pw_chat3)
Start of cycle: follow the cycle protocol in AGENTS.md (read BLOCKED/LEARNINGS/RUN_LOG; at end append RUN_LOG).
Runs 24x7 (these sources have weak bot-detection). The runner executes scripts/watcher.py before each cycle (every ~30 min).
Playbooks: skills/portals/career_pages.md + career_pages_ats.md, yc_waas.md, remote_boards.md, internshala_unstop.md, unstop.md, hn_and_startup_sources.md + skills/discovery.md, apply_flow.md, job_matching.md, resume_tailoring.md

Remote/WFH jobs are always welcome - never skip a job just because it is work-from-home or fully remote.

## ONE portal per cycle
- This cycle's single portal is career_pages when the watcher queue has fresh items, otherwise the next rotation portal.
- Rotation order (cursor `state/chat3_cursor.txt`, single integer; missing file = start 0): 0=yc_waas(10), 1=remote_boards(12), 2=unstop(10).
- Work ONLY that one portal this cycle. A portal can span multiple cycles.
- Do NOT advance the cursor to the next rotation portal until the current portal's per-portal cap is hit
  OR no fresh eligible jobs remain on it. Only then write ((cursor+1) % 3) back to `state/chat3_cursor.txt`.
- If its check says LIMIT (cap hit), that counts as its cap being reached, so you may advance.
- **Anti-starvation (mandatory):** keep `state/chat3_career_streak.txt` (integer, missing = 0).
  Increment it on every cycle spent on career_pages (including discovery). When it reaches 3,
  the NEXT cycle must be a rotation portal (yc_waas / remote_boards / unstop) even if the queue
  still has items, then reset the streak to 0. Without this, a full queue starves the other three
  sources forever.

## Context saving (keep the session small)
- Read job descriptions with TEXT EXTRACTION, not full snapshots: use browser evaluate on
  `document.body.innerText`, or the Playwright MCP text/read tool.
- Only take an accessibility snapshot when you must click or select a specific element by ref.

## One work cycle
1. Queue (career_pages): read `queue/new_jobs.jsonl` (new jobs from the watcher). Process newest first, mark processed lines
   by moving them to `queue/done.jsonl`. Apply with the `career_pages` cap (check/add with `--chat chat3`).
   New openings must be handled FAST. If the queue has fresh items, career_pages is this cycle's ONE portal.
2. If the queue is empty, do discovery (skills/discovery.md) OR the one rotation portal, not both:
   - Discovery: find 10-20 NEW recently-hiring companies per cycle from the startup sources, add them to
     config/watchlist.yaml if they use greenhouse/lever/ashby, otherwise apply directly on their career page
     (cap shared in `career_pages`, `--chat chat3`). Discovery counts as career_pages work, not a second portal.
   - Otherwise work the ONE rotation portal (yc_waas / remote_boards / unstop) at the cursor.
3. Apply rule for the cycle's portal: stop after at most `max_applications_per_cycle` (8) applications, even if the
   portal has more. Aim for at least `min_applications_per_portal` (8) when that many fresh eligible jobs exist.
   After the portal, run `tracker.py check/ summary` and send the AUDIT report on Telegram (include the
   `Sheet: synced N rows` line, N = rows in tracker/applications.csv).
4. Cursor + idle:
   - Per-portal cap hit OR no fresh eligible jobs left -> advance the rotation cursor to ((cursor+1) % 3),
     then write `state/chat3_idle_until.txt`.
   - Still more fresh eligible jobs but you hit the 8-application cycle cap -> keep the cursor on the SAME portal,
     then write `state/chat3_idle_until.txt` so the next cycle continues this portal.
   - Idle times (ISO format WITH +05:30 offset). If nothing new, idle only 30 min.
5. End the cycle with a 3-line status.
