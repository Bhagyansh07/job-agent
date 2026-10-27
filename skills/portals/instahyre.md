# Instahyre (key: instahyre | cap 10/day | strict hours 08:00-23:30 IST)

Instahyre is opportunity-based: companies send "opportunities" to matching profiles, and there is
also a normal job search. For a fresher the inbound opportunities are the valuable part because
the company already decided the profile fits.

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
`python scripts/tracker.py add --chat chat1 --portal instahyre --company "<c>" --role "<r>" --location "<l>" --url "<u>" --match <score> --status applied_auto --resume "profile" --notes "opportunity card / search, exp 0-1"`

## General
UI changes often: take a fresh page snapshot, don't rely on fixed selectors. Follow skills/apply_flow.md.
