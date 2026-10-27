# Internshala (key: internshala | cap 10/day | strict portal, 08:00-23:30 IST)

Fresher internships and fresher jobs. For a 2027 batch student this is the highest-conversion
source for paid internships with a PPO path, so quality of the cover note matters more than volume.

## Before applying
- `tracker.py check --portal internshala --chat chat1` first. Cap 10/day, counts toward the global 100.
- Filters to set: Category = Web Development / Software Development / Python / Java;
  Location = Work from home + Jaipur + Delhi NCR; Stipend = "10000 and above";
  Duration = 2-6 months (skip 1 month); "Job offer on conversion" preferred.
- Skip: unpaid, "training fee", "registration fee", "security deposit", commission-only,
  walk-in, and any posting that asks for money or ID documents.

## Application flow
1. Open the internship page and read the full description (scroll to the bottom).
2. Check the "who can apply" block: batch 2027 is fine. If it says "2026 passout only" or
   "experience required 2+ years", skip it.
3. Cover letter field is mandatory and per-application. Write 3-4 specific lines:
   the exact role, one real project from resume/master.json that maps to their stack,
   and one line on availability (immediate, full-time during semester break /
   part-time during term). No template filler, no em dashes, follow skills/writing_style.md.
4. Answer availability questions honestly from config/answers.yaml. Unknown -> ask.py.
5. Submit, confirm the "Applied" state, log with `tracker.py add ... --portal internshala --chat chat1`.
6. The profile resume is used. Do not swap the resume per internship.

## Quirks
- Internshala throttles rapid applies and shows "Too many requests" - that is a ban signal.
  Stop the portal for the day, log it, alert with `--key internshala_limit`.
- The "Apply" button sometimes opens a modal with a second "Submit" step. Verify the confirmation
  text, not just the button click.
- "Internship with job offer" postings often have a separate screening question ("Why should you
  be hired?"). Treat it as a cover letter, keep it under 900 characters.
- Never accept an offer letter or pay a deposit on the platform. Alert Bhagyansh instead.

## Logging
`python scripts/tracker.py add --chat chat1 --portal internshala --company "<c>" --role "<r>" --location "<l>" --url "<u>" --match <score> --status applied_auto --resume "profile" --notes "stipend N, PPO, N months"`
