# Unstop (key: unstop | cap 10/day | 24x7)

Off-campus hiring challenges, hackathons with hiring attached, and fresher jobs.
Priority order matters here because most listings are not real jobs.

## What to take (in this order)
1. **Hiring challenge from a real company** with a stated job/PI offer - highest value, take all eligible.
2. **Full-time fresher job** (0-1 yr, 2027 batch eligible, salary shown or product company).
3. **Paid internship** with a PPO line in the description.
4. Skip everything else: pure competitions with no hiring, paid workshops, courses,
   "career guidance" webinars, walk-ins, and anything that asks for a registration fee.

## Eligibility gate
Check the eligibility block before spending time: batch (2027 must be listed),
degree (B.Tech CSE), CGPA (needs <= 9.27), backlogs (0). If the CGPA cut-off is above 9.27,
skip. If it says "2026 batch only", skip.

## Application flow
- Job/internship listings: same as a normal form. Resume upload is allowed here,
  so tailor it per skills/resume_tailoring.md and upload the PDF.
- Hiring challenges: **register, do not attempt the assessment**. The agent registers,
  then logs `needs_input` with the challenge link, deadline and rounds, and alerts Bhagyansh.
  He solves the challenge himself. Never submit an empty or auto-generated solution.
- Team events: register as an individual unless the listing requires a team; if a team is
  mandatory, log `needs_input` and alert (he will arrange teammates).
- Deadlines matter: if registration closes in under 24h, alert with `--urgent`.

## Quirks
- Unstop often requires a complete profile (education, skills, resume) before applying.
  Fill it once from config/answers.yaml + resume/master.json, then reuse.
- Some listings redirect to the company's own ATS. Treat that as a career page apply,
  still log under `unstop` so the daily cap stays correct.
- "Apply with Unstop" vs "Apply on company site" - both are fine, but never apply twice
  to the same role (tracker exists --url first).

## Logging
`python scripts/tracker.py add --chat chat3 --portal unstop --company "<c>" --role "<r>" --location "<l>" --url "<u>" --match <score> --status applied_auto --resume "<pdf or profile>" --notes "hiring challenge / job / internship, deadline ..."`
