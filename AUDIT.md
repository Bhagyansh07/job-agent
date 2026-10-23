# Super audit - 2026-10-23

Scope: the whole live project (`C:\Users\bhagy\job-agent`), the v4 zip, the recruiter sheet,
the 24x7 runner, model routing, cold email, outreach, and every script.

Severity: CRITICAL = can lose data, send something you did not approve, or leak secrets.
HIGH = will break the 24x7 run or a cap. MEDIUM = wrong numbers or a real but limited risk.
LOW = cosmetic or accepted risk.

## 1. What was audited

| Item | Result |
|---|---|
| `scripts/*.py` (11 files) | read line by line, compiled, key paths executed |
| `config/*.yaml`, `opencode.json`, `.env` keys | checked, no secrets printed |
| Chat playbooks (3), AGENTS.md (20 rules) | cross-checked against code |
| v4 zip (`E:\Downloads\job-agent-v4.zip`) | has cold email, no Apollo |
| `job-agent-updated-kilo-perchat-retry-fallback.zip` | NOT on disk, cannot audit |
| Recruiter Google Sheet | fetched publicly, 1842 rows |
| Model aliases on Kilo | verified live, all $0 |
| Browser profiles | 950 MB, logged in, gitignored |

## 2. Fixed in this pass

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | CRITICAL | `opencode.json` used `bash` key; current OpenCode uses `shell`, so the whole bash permission map was ignored | renamed to `shell`, kept the deny rules |
| 2 | CRITICAL | No read/edit deny for `.env`, `secrets/`, `browser-profiles/`; a prompt-injected job page could ask the agent to read the token or cookies | added `read` and `edit` deny rules |
| 3 | CRITICAL | `DRY_RUN=1` blocked application submits but NOT LinkedIn connection requests. With `outreach.mode: auto` a test cycle could send real requests | rule 16 + chat2 now force outreach to draft when `DRY_RUN=1` |
| 4 | HIGH | `run_loop.py` had no subprocess timeout; one hung model call stopped that chat forever | `timeout=1800`, configurable via `OPENCODE_CYCLE_TIMEOUT` |
| 5 | HIGH | `min_cycle` was 300s for chat1/chat2; 3 chats could burn the 200 requests/hour limit in minutes | 900s default, plus 0/25/50s staggered starts |
| 6 | HIGH | `tracker.py` and `outreach.py` appended/wrote CSV with no lock; two chats writing at once could corrupt the tracker | shared `FileLock` from `common.py`, atomic replace on outreach |
| 7 | HIGH | Rate-limit detection was a raw `"429" in text` check, so a job description containing 429 was treated as a failure | explicit marker list, separate retry-vs-fallback logic |
| 8 | MEDIUM | Google Sheets sync used `USER_ENTERED`, so a company name starting with `=` became a formula | `RAW` |
| 9 | MEDIUM | CSV formula injection in tracker, outreach and cold email files | `safe_cell()` escapes `= + - @` |
| 10 | MEDIUM | Cold email subject accepted `\r\n` (header injection) | rejected with `SUBJECT_HAS_NEWLINE` |
| 11 | MEDIUM | Apollo request followed redirects, which could forward the API key to another host | redirect handler now blocks |
| 12 | MEDIUM | `outreach.py count` counted `draft_ready` rows as sent connection requests | only sent statuses count |
| 13 | MEDIUM | UTF-8 BOM in a body file crashed `review` on Windows | read with `utf-8-sig`, stdout forced to UTF-8 |
| 14 | MEDIUM | MX check cached a transient DNS failure as a dead domain | retry once, only cache a definite answer |
| 15 | LOW | `recruiter_sheet.py` had no timeout on the sheet download | 40s timeout, User-Agent set |

## 3. Still open (needs you or a decision)

| # | Severity | Item | Why it is open |
|---|---|---|---|
| 1 | CRITICAL | The named zip does not exist | I can only audit what is on disk. Its run_loop changes are already live, and a fresh zip is built from the audited tree |
| 2 | HIGH | Gmail send is not authorised | `secrets/credentials.json` missing; run `python scripts/google_auth.py --send` once |
| 3 | HIGH | Apollo key missing | `APOLLO_API_KEY` empty in `.env` |
| 4 | MEDIUM | `GOOGLE_SHEET_ID` empty | application sync silently skips; set it or ignore |
| 5 | MEDIUM | CGPA mismatch: `profile.yaml` 9.27 vs `master.json` 9.25 | must be one true number |
| 6 | MEDIUM | No bounce or reply parsing for cold email | Gmail read scope exists; add a bounce scan later |
| 7 | LOW | `webfetch` is unrestricted | needed for research; rule 5 is the guard |
| 8 | LOW | `watcher.py` writes `seen_jobs.json` non-atomically | worst case a few duplicate queue rows |
| 9 | LOW | `resume/master.json` and `profile.yaml` contain PII and are committed to the private repo | acceptable for a private repo, do not make it public |
| 10 | LOW | `notify.py` splits at 3800 chars | an all-emoji message could still exceed Telegram's 4096 UTF-16 limit |

## 4. Model routing audit

Verified on the gateway (all free, $0):

| Alias | Real model | Status |
|---|---|---|
| `kilo/laguna-s` | poolside laguna-s 2.1 | works, used for chat1 |
| `kilo/laguna-xs` | poolside laguna-xs 2.1 | exists, tool-calling weaker, chat2 starts here |
| `kilo/flint` | recursive flint v1.0 | exists, chat3 starts here |
| `kilo/dots3` | dots 3 note preview | exists, last fallback |

Limit: 200 requests/hour per IP, 4800/day. At 900s cycles and 3 chats, average load is about
85-110 requests/hour, inside the limit. Burst protection comes from the 0/25/50s stagger.

Known weakness: `laguna-xs` and `flint` sometimes emit malformed shell calls. The runner recovers,
but it costs 1-3 extra requests. If chat2 fails twice in a row, move `kilo/flint` to the front of
the chat2 chain in `run_loop.py`.

## 5. Recruiter sheet audit

| Metric | Value |
|---|---|
| Rows | 1842 |
| Valid unique emails | 1842 |
| Unique domains | 1453 |
| Usable after generic-mailbox filter | 1838 |
| Generic mailboxes | 4 |
| Service/BPO-heavy contacts | 83 |
| Duplicate emails | 0 |
| Top titles | Head HR, Head TA, CHRO, VP HR, Director HR |

Risk: this is a scraped HR list, likely one to three years old. Bounce rate can be high. That is why
`recruiter_sheet.py queue` uses one contact per domain, optional MX verification, and the cold email
warm-up (5/day in week one). Never queue all 1838.

## 6. Cold email audit

Rules enforced in `scripts/cold_email.py`, not in the prompt:

- `mode: draft` default, `send` exits 3 with `MODE_DRAFT`
- one email per address, ever
- warm-up 5/day, then 15/day, then 25/day
- 4 hour minimum gap, 08:00-23:30 IST
- `DRY_RUN=1` prints `DRY_RUN_HELD` and exits 5
- generic mailboxes blocked
- subject 60 chars, body 120 words
- subject CRLF rejected
- dedupe across queued/draft_ready/sent/replied

Not implemented on purpose: auto-reply to responses. Replies are alert-only, per AGENTS.md rule 2.

## 7. What a real cycle does now

1. chat1/chat2/chat3 each run one `opencode run` cycle, staggered.
2. A cycle reads its chat file, state, and the last RUN_LOG entries.
3. Applications go through `tracker.py check` (advisory) and, where policy permits, a reservation.
4. Outreach runs from `outreach.mode` (forced to draft under DRY_RUN).
5. Cold email runs from `config/cold_email.yaml` (draft by default).
6. Every cycle appends one RUN_LOG line.

## 8. Verification commands

```powershell
python -m py_compile (Get-ChildItem scripts\*.py).FullName
python scripts\cold_email.py count
python scripts\recruiter_sheet.py stats
python scripts\outreach.py count
python scripts\tracker.py check --portal naukri --chat chat1
```

## 9. Re-audit round 2 (same day, after the fixes above)

### New findings and fixes

| # | Severity | Finding | Fix | Proof |
|---|---|---|---|---|
| 1 | HIGH | `watcher.py` had **no location filter**. First live run queued 121 jobs including MongoDB AMER, Dublin, Cloudflare US, Stripe Poland | added `FOREIGN` region blocklist + allowed-location list | 121 -> 12, zero foreign rows |
| 2 | HIGH | Greenhouse reports many jobs as `Hybrid`; the real city was hidden inside `metadata["Job Posting Location"]`, so a US job could look location-less and pass | watcher now reads that metadata | Cloudflare `Hybrid` -> `Bengaluru, India` |
| 3 | MEDIUM | watcher queued the same company + role many times (4x MongoDB SDE 3) | dedupe on (company, lower title) per run | 4 -> 1 |
| 4 | MEDIUM | `recruiter_sheet.py` domain cap only counted the current batch, so a second contact at an already-queued company slipped through | existing queued/draft/sent domains now count | GreyOrange retest: `queued=0` |
| 5 | MEDIUM | `google_auth.py --send` crashed with a raw traceback when credentials were missing | clean `REAUTH_NEEDED` + exit 2 | verified |
| 6 | MEDIUM | `safe_cell` ran on the cold-email `subject`; a subject starting with `-` would gain an apostrophe and be sent that way | escape only display-only fields | round-trip test: subject unchanged |
| 7 | HIGH | the DRY_RUN guard for LinkedIn outreach lived only in AGENTS.md, not in code | `outreach.py add` now forces `draft_ready` for outbound statuses when DRY_RUN=1 | verified |
| 8 | HIGH | `config/watchlist.yaml` was empty, so the career-page watcher ran and did nothing | seeded 14 ATS boards that were probed live | watcher: 12 matching India/remote jobs |
| 9 | MEDIUM | `answers.yaml` had github/linkedin empty even though profile.yaml has them (forms would ask on Telegram) | filled | verified |
| 10 | HIGH | nothing started the agent after a reboot, so "24x7" was not true | `start_all.ps1`, `stop_all.ps1`, `register_startup.ps1` + Startup-folder VBS | launched and stopped 3 loops, task survives reboot |
| 11 | INFO | permission layer needed proof, not faith | canary test: model asked to read `browser-profiles/.gitkeep` got `Permission denied: read` | denied |
| 12 | INFO | `state/RUN_LOG.md` empty: the agent has never completed a live cycle | expected; first cycle is pending keys/resume | - |
| 13 | MEDIUM | after round 1, a bare `"429"` marker still matched job IDs and salaries, so a successful cycle could be logged as a rate-limit failure | context regex (`status/code/error/http ... 429`, or `429 ... too many/rate limit`) | 4 unit cases pass |

### Current live state

- `state/PAUSE` exists on purpose. Loops start with Windows (hidden) but stay idle until it is deleted.
- Cold email queue: 1 real draft (GreyOrange) in `draft_ready`, nothing sent.
- Outreach tracker: 2 draft rows from the LinkedIn test, 0 requests sent today.
- Career-page queue: 12 fresh India/remote jobs.
- Model quota: average ~100 req/hour with 900s cycles, under the 200/hour cap.

### Still blocked on you

| Need | Why |
|---|---|
| Apollo API key | people search + verified emails |
| Gmail send OAuth (`google_auth.py --send`) | actually sending cold email |
| Resume PDF | portal profile setup on all 11 portals |
| CGPA: 9.25 or 9.27 | three files disagree by 0.02 |
| Portfolio URL | empty in profile + answers |
| Email templates | locked until you send your own |

