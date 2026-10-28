# Instahyre (key: instahyre | cap 10/day | strict hours 08:00-23:30 IST)

Instahyre is opportunity-based: companies send "opportunities" to matching profiles, and there is
also a normal job search. For a fresher the inbound opportunities are the valuable part because
the company already decided the profile fits.

## Logged-in check (do this first, it saves a whole cycle)
`https://www.instahyre.com/candidate/onboard/` with a name in the tab title ("Bhagyansh Chandel - Instahyre")
means he **is logged in** - it is the onboarding wizard, not a login wall. NEVER send a login alert for this URL.
What to do instead:
- If the wizard has a Skip / "I'll do it later" / close control, click it.
- Otherwise navigate straight to `https://www.instahyre.com/candidate/opportunities/` (or `/jobs/`) and work from there.
- Only if the URL is `login` / `signup`, or the page asks for a password, is a login alert correct.
Landing on the home page (`/`) while logged in also just redirects; go straight to the opportunities URL.

## Two surfaces
1. **Opportunities / "Jobs for you"** (the main surface)
   - For each card: open it, read the full JD, hard-filter + score per `skills/job_matching.md`.
   - `>= 80` -> click "Interested" / "Apply".
   - `60-79` -> add to this cycle's batch approval list, do not click yet.
   - `< 60` -> dismiss / ignore, log `skipped` only when you actually opened it.
   - Clicking "Interested" is a real signal to the recruiter; do not spam it on borderline roles.
2. **Search** (use when Opportunities are empty)
   - Filters: experience 0-1 years, location Delhi NCR / Gurgaon / Noida / Jaipur / Remote,
     role keywords from profile.yaml. Sort by newest.
   - External redirects ("Apply on company site") are allowed; log under `instahyre`.

## Profile hygiene (do once per week, not per application)
- Skills, current/expected CTC, notice period and preferred locations come from
  `config/answers.yaml`. Expected CTC: 8 LPA onsite, 6 LPA remote.
- Keep "Total experience" at 0 and graduation year 2027. Wrong values here silently kill matches.
- Do not change the profile resume per job. Instahyre uses the profile resume.

## Quirks
- Instahyre shows "Your profile is X% complete" - below ~80% you stop receiving good opportunities.
  If it drops, complete missing fields from master.json, then log one line in LEARNINGS.md.
- The "Interested" button can show a confirmation modal with an optional message. Leave it empty;
  the platform forwards the profile, and a generic note reads worse than none.
- Employer chat messages are inbound: **never reply**. Alert Bhagyansh with the company + role.
- Rapid clicking triggers a temporary block. Keep the 25-90s pacing from profile.yaml.
- Same company can appear under several roles; apply to at most 2 roles per company per week.

## Logging
**Log the specific job URL**, e.g. `https://www.instahyre.com/candidate/opportunities/<id>/`, never the list page
`.../opportunities/?matching=true`. A list URL makes duplicates undetectable and the audit link useless.
If the card opens a modal with no URL, use the share/copy-link control; if there is none, append the company and
role to the notes and say `url unavailable (modal)` - but never paste the list URL.

Status rule: `applied_auto` is only for match >= 80. The tracker now refuses a lower score outright
(`BLOCKED: applied_auto needs match >= 80`), so a 60-79 job goes to batch approval and is logged as
`applied_approved` only after he sends the numbers.

`python scripts/tracker.py add --chat chat1 --portal instahyre --company "<c>" --role "<r>" --location "<l>" --url "<u>" --match <score> --status applied_auto --resume "profile" --notes "opportunity card / search, exp 0-1"`

## General
UI changes often: take a fresh page snapshot, don't rely on fixed selectors. Follow skills/apply_flow.md.
A click with an old snapshot ref fails with `Ref <id> not found in the current page snapshot` - that is not a
login problem. Take a new snapshot and click again; do not escalate it to Telegram.
