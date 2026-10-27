# Job matching & scoring (0-100)
Open the FULL JD first. Extract: title, company, company type (product / startup / service / agency), location + work mode, min experience, salary (if shown), stack, posted age, apply type (easy apply / external), applicant count if shown.

## Step 1 - Hard filters (any fail => skipped, log reason)
- title contains an excluded word (profile.yaml roles_exclude_title) or no included role word
- JD contains blacklist keyword (training fee, bond over 12 months, unpaid, commission only, walk-in, telecalling ...)
- **bond / service agreement**: more than 12 months -> skip, reason "bond > 12 months". Up to 12 months = OK, write "bond N months" in notes. Bond mentioned with NO duration or a vague "long-term commitment" -> treat as unknown: skip if match < 80, otherwise ask on Telegram once (batch it with the 60-79 approvals).
- min experience >= 2 years ("0-2", "freshers", "0-1" are OK)
- posted older than 14 days
- location: tier1 / tier2 / remote are OK. Other cities (south/west) ONLY if salary >= 10 LPA is shown; if not shown -> skip unless match >= 85 and then ask on Telegram
- **salary undisclosed - product / startup**: apply only if match >= 80 (log "salary undisclosed, product co, match N"). If match is 60-79 -> put it in the normal batch approval list, never auto-apply.
- **salary undisclosed - service company / agency / staffing firm**: never auto-apply. Ask on Telegram only if match >= 85, else skip with reason "service co, salary undisclosed".
- **salary undisclosed - other city (south/west)**: skip unless match >= 85, then ask on Telegram. Never assume a number.
- salary shown and below floor: remote < 6 LPA skip; north onsite < 8 LPA skip; other cities < 10 LPA skip; service-based < 8 LPA skip (no 7-8 exception)
- internship: skip if unpaid / no stipend
- already in tracker (url or company+role)

## Step 2 - Score
| Part | Max | How |
|---|---|---|
| role_fit | 30 | title/duties = full stack / SDE / backend / frontend. Exact fit 30, adjacent (web dev, python dev) 20, weak 8 |
| tech_stack | 30 | % of JD's required tech that is in resume/master.json. React/Node/JS/TS/Python/Java/SQL/Mongo etc. Every required tech he lacks removes points |
| experience_fit | 15 | fresher / 0-1 = 15, "0-2" = 12, internship-to-PPO = 12, vague = 8 |
| location_salary | 15 | tier1/remote + salary >= 8 = 15; tier2 = 12; undisclosed salary = 8; other city with >= 10 LPA = 12 |
| freshness_quality | 10 | <=3d 5 / <=7d 3 / <=14d 1, + product co or funded startup up to +5 |

## Step 3 - Freshness gate
- age 4-7 days -> need score >= 80
- age 8-14 days -> need score >= 85 and a sign it is still active (actively hiring tag, low applicant count, reposted)

## Step 4 - Decision
- >= 80 -> auto apply
- 60-79 -> BATCH approval: do NOT ask one-by-one. Collect ALL 60-79 jobs found in this cycle, then send ONE numbered message via ask.py (free text, no --options, --timeout 900):
  `python scripts/ask.py "Approve karne ke numbers bhejo (jaise 1,3,5) ya All/None:\n1) Company - Role | 72% | reason | link\n2) ..."`
  Apply only the approved numbers (`--status applied_approved`); every non-approved job -> `skipped`.
- < 60 -> skip
Write the reason in `--notes`, e.g. "stack 7/9 match, remote, 8-12 LPA, 2d old".
