# Company career pages / ATS (key: career_pages | cap 30/day, 24x7)

Handles queue/new_jobs.jsonl + discovered companies.
ATS notes: Greenhouse (boards.greenhouse.io): form + resume upload, EEO optional (choose "decline"). Lever: resume + links + extra questions. Ashby: similar. Workday: requires account (allowed with his Gmail, store creds in secrets/portal_accounts.csv; Workday asks to re-enter resume fields - fill from master.json). SmartRecruiters, Zoho Recruit, Keka, Freshteam, Recruitee, Breezy, Workable: standard forms.
- Speed matters: new openings must be applied same day (ideally within hours).
- Optional demographic/EEO/disability/veteran questions: choose "Prefer not to say / Decline".
- Work authorisation: India = authorised. Visa sponsorship needed? "No".
- Roles outside India/remote-global requiring location presence -> skip.
- Take-home test/assessment: still submit the application, then log needs_input with the test link and alert Bhagyansh on Telegram. He does these tasks himself. Do not attempt the test.
- Work-from-home/remote roles: never skip for location. Bond up to 12 months is fine.

## General
UI changes often: take a fresh page snapshot, don't rely on fixed selectors. Follow skills/apply_flow.md. Log every decision with tracker.py (portal key shown below).
