# CHAT 2 - LinkedIn + startup/global boards   (browser: pw_chat2)
Portals in order: wellfound(10) -> linkedin(10 applies + outreach) -> cutshort(10) -> indeed(10) -> glassdoor(5, mostly find company + apply link)
Playbooks: skills/portals/linkedin.md, wellfound.md, cutshort.md, indeed.md, glassdoor.md + skills/linkedin_outreach.md + skills/outreach/cold_email.md + skills/outreach/templates.md + apply_flow.md, job_matching.md, resume_tailoring.md

Remote/WFH jobs are always welcome - never skip a job just because it is work-from-home or fully remote.

## Portal rotation (ONE portal per cycle)
- Read the cursor from `state/chat2_cursor.txt` (single integer; missing file = start 0).
- Order by index: 0=wellfound, 1=linkedin, 2=cutshort, 3=indeed, 4=glassdoor.
- Work ONLY the portal at the cursor this cycle. A portal can span multiple cycles.
- Do NOT advance the cursor to the next portal until the current portal's per-portal cap is hit
  OR no fresh eligible jobs remain on it. Only then write ((cursor+1) % 5) back to `state/chat2_cursor.txt`.
- If its check says LIMIT (cap hit), that counts as its cap being reached, so you may advance.

## Context saving (keep the session small)
- Read job descriptions with TEXT EXTRACTION, not full snapshots: use browser evaluate on
  `document.body.innerText`, or the Playwright MCP text/read tool.
- Only take an accessibility snapshot when you must click or select a specific element by ref.

## One work cycle
0. Follow the cycle protocol in AGENTS.md (read BLOCKED/LEARNINGS/RUN_LOG first; append RUN_LOG at the end).
1. Clock check (strict portals 08:00-23:30 IST; wellfound/cutshort any time).
2. `python scripts/gmail_reader.py recent --hours 24 --notify` -> sends recruiter mails to Telegram (read only).
3. Outreach (skills/linkedin_outreach.md), runs every cycle, max 2 outreach ACTIONS per cycle:
   - Mode comes from profile.yaml `outreach.mode`. If `auto`, send connection requests/DMs directly within caps
     (10-15/day). If `draft`, log each message as draft_ready and send ONE numbered approval message first.
     DRY_RUN=1 always forces draft, even when mode says auto.
   - `outreach.py due` first -> pending DMs/follow-ups, accepted requests; then new connection requests
     up to `outreach.py count` limit (10-15/day) for companies where you applied with match >= 80.
3b. Cold email (skills/outreach/cold_email.md), runs every cycle, max `max_per_cycle` (3) per cycle:
   - Mode comes from config/cold_email.yaml `mode` (default `draft`: prepare only, send NOTHING).
   - `python scripts/cold_email.py count` -> if at today's limit, skip this step.
   - `python scripts/cold_email.py review` -> if drafts are waiting, send ONE numbered approval message
     on Telegram and do not add new drafts this cycle.
   - `python scripts/cold_email.py apollo --role "<role>" --limit 20` -> shortlist 3-5 people.
     Priority: companies already applied to with match >= 80, then JECRC alumni, then product
     startups size 1-200. Never email info@/support@/noreply@ (blocked in code).
   - `python scripts/cold_email.py queue ...` -> write body to `state/tmp/email_<id>.txt` ->
     `python scripts/cold_email.py draft --id <id> --subject "..." --body-file <path>`.
   - Only when mode is `auto` AND the user approved the draft: `send --id <id>`, one at a time.
   - Never answer replies. Alert Bhagyansh with a draft and log `mark --status replied`.
4. The one portal at the cursor (job applications):
   a. `tracker.py check --portal <p> --chat chat2` -> if LIMIT, per-portal cap is hit (advance cursor per rule above) and end cycle.
   b. Open portal in pw_chat2. If logged out -> Telegram login protocol (skills/telegram_protocol.md).
   c. Collect fresh candidates (LinkedIn: Easy Apply + external links, filter "Past 24 hours"/"Past week").
   d. Evaluate + apply following skills/apply_flow.md (text-extract each JD, then apply).
      (check/add with `--chat chat2` on every tracker.py call.)
   e. Stop the cycle after at most `max_applications_per_cycle` (8) applications, even if the portal has more.
      Aim for at least `min_applications_per_portal` (8) applications when that many fresh eligible jobs exist.
   f. Send AUDIT report on Telegram (applies + outreach counts + the `Sheet: synced N rows` line,
      N = rows in tracker/applications.csv).
5. Cursor only (the runner owns pacing; do NOT write an idle file):
   - Per-portal cap hit OR no fresh eligible jobs left -> advance the cursor to ((cursor+1) % 5).
   - Still more fresh eligible jobs but you hit the 8-application cycle cap -> keep the cursor on the SAME portal,
     so the next cycle continues this portal.
   - Nothing reads chat2_idle_until.txt. Remove it if it exists; never create it.
6. End the cycle with a 3-line status.
