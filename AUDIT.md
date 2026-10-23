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

## 10. Re-audit round 3 (same day, deeper pass)

This pass looked at the parts round 1 and 2 did not touch: the OpenCode permission layer, the resume renderer, the tracker reader, the cold-email state machine, the Gmail OTP reader, and the runner's failure path.

### New findings and fixes

| # | Severity | Finding | Fix | Proof |
|---|---|---|---|---|
| 1 | HIGH | shell commands could still read `secrets/` even though the read tool was denied. The read deny only protected one tool | added shell deny rules for `*secrets*`, `*.env`, `*.env.*`, `*browser-profiles*`, plus `Remove-Item`/`erase` | before: canary printed; after: `Permission denied: shell` |
| 2 | HIGH | `opencode.json` used the deprecated V1 `permission` object. V2 documents a `permissions` array with action/resource/effect | migrated the whole block to the V2 array, rules ordered so the last match wins | config validates; read deny, shell deny and a normal shell command all behave correctly in one run |
| 3 | MEDIUM | `render_resume.py` wrote a fixed `state/tmp/_resume.html`. Three chats rendering at the same moment could overwrite each other and save the wrong PDF | unique `mkstemp` file per render, deleted in `finally` | two concurrent renders, both 63,949 bytes, both valid |
| 4 | MEDIUM | `render_resume.py` accepted any `--out` path and deleted the target first, so `--out state/tmp/evil.txt` was possible | output must end in `.pdf` and stay inside the project | `OUTPUT_MUST_BE_PDF` |
| 5 | MEDIUM | the resume contact loop rendered phone/email/LinkedIn/location but silently dropped `github` and `portfolio` | both added to the contact tuple | PDF now carries them when present |
| 6 | MEDIUM | `tracker.rows()` trusted every CSV column; a legacy file missing a column could crash `exists`/`summary` | rows are normalised to the canonical `COLS` | legacy 6-column CSV: `exists` exit 0, `summary` no crash |
| 7 | MEDIUM | cold-email `mark` allowed `sent -> queued`, and the two-step `sent -> failed -> queued`, so the same address could be emailed twice. `queue` also allowed a bounced address back in | `sent_at` is now a permanent block; queue dedupes on `sent_at` too | `BAD_TRANSITION` on both direct and two-step; queue returns `DUPLICATE` |
| 8 | MEDIUM | `never_email` blocked only info/support/noreply, so `hr@`, `careers@`, `jobs@`, `talent@` could be queued by hand | full generic-mailbox list added | config check |
| 9 | MEDIUM | the Gmail OTP reader fell back to any bare 6-digit number in any email, which could type an order number into a portal | bare 6-digit fallback is allowed only when `--sender` is set | code path reviewed, compile OK |
| 10 | LOW | if all four models failed, the 24x7 runner retried silently forever | one Telegram alert per 6h with the log filename | code path added, compile OK |
| 11 | LOW | `AGENTS.md` still said model "Big Pickle" and "run with bash" | corrected to the Kilo per-chat layer and the `shell` tool | grep clean |
| 12 | INFO | stale test scripts and old `_resume*.html` files were sitting in `state/tmp` | removed | directory clean |

### Residual risks (not changed on purpose)

| Risk | Why it is still there | Suggested fix |
|---|---|---|
| shell deny is pattern-based, not a sandbox | OpenCode docs warn that shell runs with the host user's authority; a command that avoids the blocked words can still reach a secret | move `secrets/` outside the project root, or tighten NTFS ACLs on `secrets/` and `.env` |
| fabrication guard checks skills, numbers and names, not free-text claims | a non-numeric invented claim in a bullet could pass | add a token-overlap warning against `resume/master.json`; keep it a warning to avoid false blocks |
| `max_per_cycle`, `apollo.reveal_emails`, `targeting.require_personalization`, `one_ask_only` | present in config but not enforced in code | wire them into `cold_email.py` or remove them so config does not promise more than it does |
| watcher marks a job seen before the location filter | changing criteria later will not re-open old filtered jobs | store `seen` only for queued jobs, or add a `--rescan` flag |
| tracker limit check is not atomic | two chats can both pass the last slot and exceed a cap by 1-2 | reserve a row at check time, or accept the small overrun |
| `.env` values are not stripped of inline comments | `DRY_RUN=1  # note` would read as a non-1 value | strip ` #` in `load_env` (safe now, current file has no inline comments) |

### Round 3 verification summary

- read canary: `Permission denied: read`
- shell canary containing `secrets`: `Permission denied: shell`
- normal shell command in the same run: executed correctly
- concurrent resume renders: both correct
- bad resume output path: refused
- legacy tracker CSV: no crash
- cold-email double-send paths: both blocked
- all scripts compile

### Still blocked on you (unchanged)

| Need | Why |
|---|---|
| Apollo API key | people search + verified emails |
| Gmail send OAuth (`google_auth.py --send`) | actually sending cold email |
| Resume PDF | portal profile setup on all 11 portals |
| CGPA: 9.25 or 9.27 | three files disagree by 0.02 |
| Portfolio URL | empty in profile + answers |
| Email templates | locked until you send your own |



## 11. Re-audit round 4 (same day, full-project pass)

This pass went after the gaps the earlier rounds created or missed: tool-level secret access, the password exception that round 3 accidentally closed, unattended Gmail startup, Telegram answer replay, cold-email limit accounting, and doc/code contradictions.

### New findings and fixes

| # | Severity | Finding | Fix | Proof |
|---|---|---|---|---|
| 1 | HIGH | `grep` could read `secrets/` contents even though the `read` tool was denied. The permission table names the grep resource as the regex, not the path, so no path rule protected it | added `{action:"grep", resource:"*", effect:"deny"}`; grep is fully unavailable to the job agent | `GREP_UNAVAILABLE`; shell fallback `Permission denied: shell`; no canary content returned |
| 2 | HIGH | round 3 deny rules made rule 4's one allowed write impossible: the agent could not append a new career-page password to `secrets/portal_accounts.csv` via shell or edit | new `scripts/portal_account.py new` helper generates, stores and prints the password once; AGENTS/apply_flow point to it | create exit 0, 20 chars, 4 columns; duplicate exit 2; test CSV removed |
| 3 | HIGH (data) | CGPA conflict is real, not cosmetic: base PDF and `resume/master.json` say **9.25**, while `profile.yaml`, `answers.yaml`, `AGENTS.md` and the cold-email draft header use **9.27** | not changed silently; flagged for a one-number decision. The rendered PDF is the strongest evidence | base PDF text: `CGPA: 9.25 / 10.0`; GreyOrange draft subject uses 9.25 |
| 4 | MEDIUM | `gmail_reader.py` called `service("gmail","v1")` with the interactive default, so every chat2 cycle without OAuth raised a raw `FileNotFoundError` and tried the browser path | `interactive=False`; missing token/credentials returns `GMAIL_NOT_CONFIGURED` with exit 0 so the cycle continues | both `recent` and `otp` exit 0 with the clean message |
| 5 | MEDIUM | `ask.py` never confirmed the answer update. The next ask re-read the same Telegram update and appended it to `telegram_inbox.jsonl`, creating a stale/duplicate answer | `consume(offset)` confirms the answer before exit; callback taps are saved to the inbox too; callback data is truncated by bytes, not characters | compiles; live Telegram path intentionally not spammed |
| 6 | MEDIUM | `outreach.py update` allowed marking `requested`/`dm_sent` while `DRY_RUN=1`, and printed `updated` even when the URL did not exist | sent-like statuses exit 5 `DRY_RUN_BLOCKED`; unknown URL exits 2 `NOT_FOUND`; `accepted` still allowed | both sent-like statuses exit 5; unknown URL exit 2; valid accepted exit 0 |
| 7 | MEDIUM | cold-email daily count, warm-up day index and gap only looked at rows whose status was exactly `sent`. Marking a send `replied` reset the warm-up and could allow extra sends | all three now use `sent_at` regardless of current status | code review + queue/count tests; replied rows stay counted |
| 8 | MEDIUM | `recruiter_sheet.py` per-domain cap and duplicate set ignored `failed`/`skipped` rows that had already been sent, so a bounced address could come back | active row = queued/draft/sent/replied **or** non-empty `sent_at` | queued 2 live rows, both unique domains; restored CSV |
| 9 | MEDIUM | `cold_email.py queue` had no per-domain cap even though the playbook says one contact per company | `targeting.max_per_domain: 1`; queue returns `DOMAIN_LIMIT` | first contact queued; second at same domain exit 4 |
| 10 | MEDIUM | `cold_email.py draft` accepted em/en dashes and bodies with no name/company, despite hard rule 20 and `require_personalization: true` | `STYLE_DASH` and `PERSONALIZATION_MISSING` reject before writing a draft | dash exit 2; no-name exit 2; valid draft `DRAFT_READY` 41 words |
| 11 | MEDIUM | `job_matching.md` salary floors contradicted `profile.yaml`: remote 8 vs 6, service 7 vs 8, other-city approval 90 vs 85 | doc now matches profile exactly | diff reviewed |
| 12 | MEDIUM | `apply_flow.md` omitted `--chat chatN` on `tracker check` and `tracker add`, so per-chat budgets would not attribute applications | both commands now include `--chat chatN` | diff reviewed |
| 13 | LOW | `resolve` still advertised pattern guesses, but `never_email` now blocks every one of them | no pattern fallback; `NO_VERIFIED_EMAIL` exit 2 and a named-contact instruction; skill updated | code + skill diff |
| 14 | LOW | watcher `seen_jobs.json`, recruiter MX cache and recruiter RAW file were written in place. A crash could corrupt them and break the next run | atomic `tmp.replace(target)`; corrupt JSON/SEEN recovers as empty; bad watchlist YAML prints one error and stops cleanly | live watcher: 14 companies, 0 new, queue stays 12 |
| 15 | LOW | Gmail `seen_mail.json` had the same corruption risk | atomic replace + recovery | compile + code path |
| 16 | LOW | `stop_all.ps1` killed the parent Python only, leaving an `opencode run`/Chrome child alive to finish a cycle after "stop" | `taskkill /PID <pid> /T /F` kills the process tree | PowerShell syntax review; no loops running during test |
| 17 | LOW | `load_env` did not strip inline comments; `safe_cell` checked the first character before leading whitespace | inline ` #` stripping for unquoted values; formula check on `lstrip()` | compile + code review |
| 18 | LOW | `resume_tailoring.md` told the agent to set a `headline` the renderer never reads, and told it never to use a `--no-guard` flag that does not exist | doc now says summary is the only headline and the guard has no bypass | diff reviewed |
| 19 | INFO | tracked `AGENTS_FULL_BACKUP.md` was a stale copy with the old model, `bash`, and no cold-email rules | untracked with `git rm --cached` (local backup kept), `.gitignore`d so it is not shipped or read | `git status` shows deletion from index only; local file still present |
| 20 | INFO | README still said Gmail is read-only, 3 terminals only, and V1 `permission` | updated for send token, startup scripts, V2 deny rules, cold email/recruiter sheet/portal helper | diff reviewed |

### Round 4 verification summary

- `grep` tool: unavailable; `read`/`shell`/`glob` canaries denied; control file readable.
- Portal password helper: create, duplicate guard, CSV shape, cleanup.
- Gmail without OAuth: clean `GMAIL_NOT_CONFIGURED`, exit 0, no browser attempt.
- Outreach: DRY_RUN sent-like block, NOT_FOUND, accepted allowed.
- Cold email: duplicate, domain cap, generic mailbox block, dash block, personalization block, valid draft, draft-mode send held.
- Recruiter sheet: 1838 usable / 1449 domains, MX verify 5 (4 ok, 1 no MX), queue 2, restored.
- Watcher: 14 boards live, 0 new, 12 queued rows unchanged.
- Tracker: dry add, `exists=YES`, `check 0/10`, summary shows `dry_applied_auto`, dry rows not counted, test CSV removed.
- Daily report dry: exit 0 with no tracker file.
- All `scripts/*.py` compile; all YAML/JSON parse.

### Residual risks (still not a sandbox)

| Risk | Why it remains | Suggested fix |
|---|---|---|
| Playwright MCP can navigate to `file:///...` and read local files | MCP tool permissions are all-or-nothing per tool, not per URL/path | check the MCP server for a URL allowlist/blocklist flag; otherwise accept and keep prompt-injection rule 5 |
| `webfetch` can reach localhost/internal services | needed for research; no host allowlist | restrict to https + known domains if the harness supports it |
| shell deny is still pattern-based | docs say shell runs with the user's authority; a command that avoids the blocked words may reach a secret | move `secrets/` and `.env` outside the project root, or apply NTFS ACLs |
| cold-email send is at-least-once on an ambiguous network failure | Gmail may accept the message and the response may still fail; retry can duplicate | add a deterministic `Message-ID`, search Sent before retry, or accept manual review |
| `max_per_cycle`, `apollo.reveal_emails`, `one_ask_only` | still config-only | wire into code or remove from config |
| tracker limit check is not atomic | two chats can exceed a cap by 1-2 | reserve a slot at check time or accept |
| watcher marks a job seen before filtering | criteria changes will not re-open old filtered jobs | add `--rescan` or only persist queued URLs |
| no resume page-count check | a 2-page tailored PDF can pass the fabrication guard | add a pypdf page-count warning |
| CGPA mismatch | needs Bhagyansh's decision | set one number in profile, answers, AGENTS and master, then re-render |
| Gmail OTP and Telegram ask paths are not live-tested | avoid spamming the phone / no OAuth yet | test once during first supervised cycle |

### Current live state after round 4

- `state/PAUSE` still exists on purpose; loops are installed at logon but idle.
- Career-page queue: 12 fresh India/remote jobs.
- Cold email: 1 real GreyOrange draft (`draft_ready`), nothing sent; mode `draft`.
- LinkedIn outreach: 2 draft rows, 0 requests sent.
- No live agent cycle has run yet.
- Test artifacts (canaries, temp CSVs, temp PDFs, test rows) removed/restored.

### Still blocked on you

| Need | Why |
|---|---|
| Apollo API key | people search + verified emails |
| Gmail read OAuth (`python scripts/google_auth.py`) | OTP reading for portal logins |
| Gmail send OAuth (`python scripts/google_auth.py --send`) | actually sending cold email |
| Resume PDF | portal profile setup on all 11 portals |
| CGPA: 9.25 or 9.27 | four files disagree; pick one |
| Portfolio URL | empty in profile + answers |
| Email/connection templates | locked until you send your own |
