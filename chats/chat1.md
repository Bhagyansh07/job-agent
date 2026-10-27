# CHAT 1 - Indian job boards   (browser: pw_chat1)
Portals in order: naukri(10) -> instahyre(10) -> foundit(10) -> hirist(10) -> apna(8) -> internshala(10)
Playbooks: skills/portals/naukri.md, instahyre.md, foundit.md, hirist.md, apna.md, internshala.md  + skills/apply_flow.md, job_matching.md, resume_tailoring.md

Remote/WFH jobs are always welcome - never skip a job just because it is work-from-home or fully remote.

## Portal rotation (ONE portal per cycle)
- Read the cursor from `state/chat1_cursor.txt` (a single integer; if the file is missing, start = 0).
- Portal order by index: 0=naukri, 1=instahyre, 2=foundit, 3=hirist, 4=apna, 5=internshala.
- Work ONLY the portal at the cursor this cycle. A portal may span multiple cycles.
- Do NOT advance the cursor to the next portal until the current portal's per-portal cap is hit
  OR no fresh eligible jobs remain on it. Only then write ((cursor+1) % 6) back to `state/chat1_cursor.txt`.
- If a portal's check says LIMIT (cap hit), that counts as its cap being reached, so you may advance.

## Context saving (keep the session small)
- Read job descriptions with TEXT EXTRACTION, not full snapshots: use browser evaluate on
  `document.body.innerText`, or the Playwright MCP text/read tool.
- Only take an accessibility snapshot when you must click or select a specific element by ref.

## One work cycle
0. Follow the cycle protocol in AGENTS.md (read BLOCKED/LEARNINGS/RUN_LOG first; append RUN_LOG at the end).
1. Check clock. Strict portals only 08:00-23:30 IST. Outside it do internshala only (or finish cycle).
2. The one portal at the cursor:
   a. `tracker.py check --portal <p> --chat chat1` -> if LIMIT, the per-portal cap is hit (advance cursor per rule above) and end cycle.
   b. Open portal in pw_chat1. If logged out -> Telegram login protocol (skills/telegram_protocol.md).
   c. Run the portal's saved searches (queries from skills/portals/<p>.md), sorted by latest. Collect candidates posted within 14 days.
   d. Evaluate + apply following skills/apply_flow.md (text-extract each JD, then apply).
      (Every add: `tracker.py add ... --chat chat1`.)
   e. Stop the cycle after at most `max_applications_per_cycle` (8) applications, even if the portal has more.
      Aim for at least `min_applications_per_portal` (8) applications when that many fresh eligible jobs exist.
   f. Send AUDIT report on Telegram (include the `Sheet: synced N rows` line, N = rows in tracker/applications.csv).
3. Cursor + idle:
   - Per-portal cap hit OR no fresh eligible jobs left -> advance the cursor to ((cursor+1) % 6),
     then write `state/chat1_idle_until.txt`.
   - Still more fresh eligible jobs but you hit the 8-application cycle cap -> keep the cursor on the SAME portal,
     then write `state/chat1_idle_until.txt` so the next cycle continues this portal.
   - Idle times (ISO format WITH offset, e.g. 2026-10-18T00:05:00+05:30):
     cap reached for today -> tomorrow 00:05 IST; nothing new -> now + 45 minutes (e.g. 2026-10-17T21:45:00+05:30).
4. End the cycle with a 3-line status. (The runner starts the next cycle.)
