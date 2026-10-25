# LinkedIn outreach & referrals (chat2 only, strict human pace)
Daily budget: connection requests 10-15 (`outreach.py count`), DMs only to ACCEPTED connections, 1 follow-up after 5-7 days (`outreach.py due`).

## Mode (auto or draft)
Mode comes from profile.yaml `outreach.mode`. Bhagyansh chose `auto` on 2026-10-17, so send connection requests and DMs directly, within the caps (10-15 connection requests/day, max 2 outreach actions per cycle), and stop the whole outreach for the day on any warning/CAPTCHA/restriction. If outreach.mode is `draft`, then instead write each message into tracker/outreach.csv with status draft_ready and its text in notes, and send one numbered approval message first.

`DRY_RUN=1` beats the mode: send nothing, and `outreach.py update` refuses to mark `requested`/`dm_sent`/`followup_sent` (exit 5, `DRY_RUN_BLOCKED`). Drafts stay `draft_ready`.

Targets (in this priority): 1) engineers/EMs at companies where he just applied (match >= 80), 2) recruiters/HR of those companies, 3) JECRC alumni at product companies, 4) founders/CTOs of hiring startups.
Flow:
1. Read `state/referral_queue.txt` (company | role | job url). For each company search LinkedIn People: "<company> software engineer", "<company> talent acquisition", "<company> JECRC". Prefer people with the company's current role, active profiles, 2nd/3rd degree.
2. Open the profile, read headline + about (30-60 s). `outreach.py exists --url` => skip if known.
3. Send connection request. LinkedIn free accounts have a small monthly quota of personalised notes: if the "Add a note" option is blocked/limited, send WITHOUT a note and put the pitch in the DM after acceptance. Note (<= 280 chars), professional English, e.g.:
   "Hi <Name>, I'm a final-year CS student (B.Tech, JECRC) with Java/SQL and GCP projects. I applied for <Role> at <Company> and would love to connect and learn about the team. Thank you!"
4. Log: `outreach.py add --name .. --title .. --company .. --url .. --type recruiter|engineer|alumni|founder`
5. Each cycle: open "My Network -> Manage/Invitations sent" or profile status; for accepted ones run `outreach.py update --url .. --status accepted`.
6. DM (only if accepted), adapt tone to the person, 4-6 lines, ONE clear ask, mention the exact job link, never pushy, never fake claims:
   - Engineer: "Hi <Name>, thanks for connecting. I applied for <Role> (<link>) at <Company> - my Java/SQL and GCP project <X> is relevant to <their product/stack>. If you feel I'm a fit, would you be open to referring me or pointing me to the right person? Happy to share my resume. Thank you for your time."
   - Recruiter: shorter, role + availability (immediate) + resume offer.
   - Alumni: mention JECRC first, ask for 5 minutes of guidance / referral if suitable.
   Log: `outreach.py update --url .. --status dm_sent`
7. Follow-up ONCE after >= 5-7 days (`outreach.py due` -> FOLLOWUP): 2 polite lines. Then `--status followup_sent`. No more messages ever.
8. Any reply from a person -> `--status replied` + Telegram alert "Reply aaya: <name> @ <company> - khud reply karo". Do NOT answer.
Stop outreach for the day on any LinkedIn warning/CAPTCHA/restriction notice.
