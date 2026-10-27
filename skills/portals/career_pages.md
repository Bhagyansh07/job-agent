# Career pages (key: career_pages | cap 30/day | 24x7)

How to work the watcher queue. Per-ATS form quirks live in `career_pages_ats.md`; read both.

## Queue mechanics
- Input: `queue/new_jobs.jsonl` (written by `scripts/watcher.py` every 30 min).
  Each line: company, title, location, url, age_days, updated_days, source.
- Process **newest first**. After a line is handled (applied / skipped / failed), move it to
  `queue/done.jsonl` and remove it from `new_jobs.jsonl`. Never leave a handled line in place:
  it will be retried forever.
- A line older than 14 days or with `age_days > 14` -> drop it, do not open the page.
- The queue is capped work: max 8 applications per cycle, 30/day. Stop when the cap is hit
  even if the queue still has items.

## Rotation starvation rule (important)
`career_pages` (cap 30) can eat every chat3 cycle when the queue is full, and then
`yc_waas`, `remote_boards` and `unstop` never run. Enforce this:
- Track `state/chat3_career_streak.txt` (integer, missing = 0).
- Every time a cycle is spent on career_pages, increment it.
- If the streak reaches **3**, the next cycle MUST be a rotation portal (yc_waas / remote_boards /
  unstop at the cursor), then reset the streak to 0.
- Exception: a job in the queue with `age_days <= 1` from a company on the watchlist may preempt
  the rotation once, but the streak still increments.

## Apply flow
1. `tracker.py exists --url <u>` -> skip if YES.
2. `tracker.py check --portal career_pages --chat chat3` -> stop if LIMIT.
3. Open the job URL, read the full JD, hard-filter + score per `skills/job_matching.md`.
4. Sanitize the JD text before scoring: `python scripts/sanitize_text.py --file <saved jd>`.
5. Tailor + render (upload per job). Handle `render_resume.py` exit code 2 per `apply_flow.md`.
6. Fill from `config/answers.yaml`; EEO/demographic -> "Prefer not to say".
7. Submit, verify confirmation, log with `--portal career_pages --chat chat3`.
8. Move the queue line to `done.jsonl`.

## Never
- Never apply to a job whose JD asks for payment, ID documents, or a "training fee".
- Never take a take-home test yourself: submit the application, log `needs_input`, alert.
- Never guess a salary answer. Unknown -> ask.py, log `needs_input` on timeout.
