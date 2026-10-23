# Cold email (recruiter / founder outreach)

Goal: get replies from real humans at companies worth working for. Volume is small on purpose.
A cold email that is obviously mass-sent gets ignored and damages the domain. Quality beats count.

Read `skills/writing_style.md` before writing any subject or body. Ready-made structures live in
`skills/outreach/templates.md` (founder, HR head, alumnus, follow-ups, referral DMs).

## Mode gate (check every cycle)
`config/cold_email.yaml` -> `mode`

- `draft` (default): prepare drafts only. Run `cold_email.py draft`, then alert on Telegram. Nothing is sent.
- `auto`: you may send drafts, but only inside every cap below and only after the draft was reviewed.

Never flip `mode` yourself. Never send while `DRY_RUN=1` (the script refuses and prints `DRY_RUN_HELD`).

## Caps (enforced in code, trust the script not your own count)
| Limit | Value |
|---|---|
| `warmup_week1` days 1-7 | 5/day |
| `warmup_week2` days 8-14 | 15/day |
| `daily_cap` after warm-up | 25/day |
| `min_gap_hours` between sends | 4h |
| sending hours | `active_hours_ist` from profile.yaml (08:00-23:30) |
| `max_per_cycle` | 3 emails drafted or sent per cycle |
| one address | exactly one email, ever |

Run `python scripts/cold_email.py count` before touching anything in a cycle.

## Commands
```
python scripts/cold_email.py count
python scripts/cold_email.py apollo --role "software engineer" --limit 20
python scripts/cold_email.py apollo --company "Acme" --limit 10 --reveal --queue
python scripts/cold_email.py queued --limit 20
python scripts/cold_email.py queue --company "Acme" --email rahul@acme.com --name "Rahul" --title "CTO" --source linkedin
python scripts/cold_email.py draft --id 2026-11-01-001 --subject "..." --body-file state/tmp/email_<id>.txt
python scripts/cold_email.py review
python scripts/cold_email.py send --id 2026-11-01-001
python scripts/cold_email.py resolve --domain acme.com
python scripts/cold_email.py mark --id 2026-11-01-001 --status replied
```
Statuses: `queued` -> `draft_ready` -> `sent` -> `replied` / `failed` / `skipped`.
Tracker: `tracker/cold_emails.csv`. Bodies: `tracker/email_drafts/<id>.txt`.

## Where emails come from
1. **Apollo.io API** (primary). Free plan has API access, but the account must be registered with a
   work or college email; plain Gmail blocks people search on the free plan.
   - Search costs 0 credits. Revealing one work email costs 1 credit.
   - Free allowance is about 900 credits/year, roughly 75 reveals/month. Never burn reveals on
     low-fit companies.
   - Key goes in `.env` as `APOLLO_API_KEY`. You never read `.env`; the script does.
2. **Hunter.io** (fallback). `resolve --domain` uses it when `HUNTER_API_KEY` is set. Free tier is
   about 25 searches/month.
3. **Pattern guess** (last resort). `resolve` prints `hello@`, `careers@`, `jobs@`, `contact@` marked
   `UNVERIFIED`. Only use a generic inbox when the company has no named contact AND the address is
   clearly monitored for hiring. Log `source=pattern_guess` in notes.
4. **LinkedIn** already gives you the person and company; then resolve the domain here.

Never send to `info@`, `support@`, `noreply@` (blocked in code).

## Which companies
Priority order:
1. Companies already in `tracker/applications.csv` with match >= 80. You applied, now you push.
2. Companies where a JECRC alumnus works (LinkedIn check).
3. Product startups with a real product, not service/body-shop IT.
4. Recently funded (YC, Inc42, Entrackr) - they hire fast.
5. Fresher friendly: "entry level", "graduate", "trainee", "associate" in the JD.
6. Size 1-200. Founders at this size actually read email.

Skip: companies you already emailed, companies that rejected you in the last 60 days, anything on the
hard skip list in AGENTS.md.

## Which person
1. Founder / co-founder / CTO for size 1-30.
2. Engineering manager / hiring manager for size 31-150.
3. Recruiter / talent acquisition for size 150+, only if they hire freshers.
4. JECRC alumnus anywhere = jump the queue.

One person per company per week. Never two contacts at the same company in the same day.

## Email copy rules
- Subject: under 60 chars, specific, no clickbait, no "Opportunity", no emoji.
- Body: under 120 words, 3 short paragraphs maximum.
- Paragraph 1: who you are in one line (final-year CSE, JECRC, what you build).
- Paragraph 2: one concrete proof. A shipped project with its stack, or a number from
  `resume/master.json`. Never invent.
- Paragraph 3: one ask only. "Would you be open to a 10 minute call?" or "Is there a fresher opening
  on your team?" Never both.
- Mention the company product or a recent update. One line minimum, or it is spam.
- No em dashes, no en dashes, no "I hope this email finds you well", no "I came across your profile".
- Plain text only. No attachments on the first email. No tracking pixels.
- Sign off: name, phone, LinkedIn, GitHub. Use the values from `config/profile.yaml`.

## Cycle flow (chat that owns outreach)
1. `cold_email.py count` -> if at limit, stop.
2. `cold_email.py review` -> if drafts are waiting, alert them on Telegram and stop (draft mode).
3. `cold_email.py apollo ...` -> shortlist 3 to 5 people from target companies.
4. `cold_email.py queue ...` for the best ones (skip duplicates).
5. Write the body to `state/tmp/email_<id>.txt`, then `cold_email.py draft`.
6. In `auto` mode only: `cold_email.py send --id <id>`, one at a time, respecting the 4h gap.
7. Update statuses with `mark` when a reply or bounce shows up. Replies are never answered by you;
   alert Bhagyansh with a draft.

## First time setup (once)
1. Free Apollo account with a work or college email -> Settings -> API key -> `.env` as `APOLLO_API_KEY`.
2. Google Cloud OAuth desktop client -> `secrets/credentials.json` (if not already there).
3. `python scripts/google_auth.py --send` -> browser grant -> `secrets/token_send.json`.
4. Send the first email to yourself, confirm it arrives in inbox not spam.
5. Keep `mode: draft` for the first week, then switch to `auto` only if the drafts read well.

## Hard stops
- Bounce rate over 5 percent: stop all sending, tell Bhagyansh.
- Any "this looks like spam" reply: stop that company, log it.
- Domain reputation warning, or Gmail asks for verification: stop, alert.
- Same step fails 3 times: stop, write to `state/BLOCKED.md`, alert.
