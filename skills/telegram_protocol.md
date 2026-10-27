# Telegram protocol
- **Urgent/blocked**: `python scripts/alert.py "..." --key <topic> --urgent`  (blocks work until he acts; deduped; written to `state/needs_you.md`)
- **Resolve**: `python scripts/alert.py --resolve <topic>` after he replies/does it
- Info only (audits, issues): `python scripts/notify.py "..."`  (keep under ~15 lines)
- Question: `python scripts/ask.py "..." --options "A,B" --timeout 90`  -> prints the answer or TIMEOUT.
  **Always pass `--timeout 90`**: the shell tool kills a command after ~120 s, so a 900 s wait gets cut off and you never
  see TIMEOUT. If it prints TIMEOUT, send the matching `alert.py ... --urgent` and move to another job/portal; his later
  reply lands in `state/telegram_inbox.jsonl` and the next cycle picks it up.
- Login needed: `ask.py` "Login chahiye: <portal>. Browser (<pw_chatX>) me login kar do, phir Done dabao." --options "Done,Skip portal today" AND `alert.py` "<portal> login chahiye | pw_<chat> me khud login karke 'Done' bhejo" --key "<portal>_login" --urgent. On Done: reload the portal and verify logged in. On Skip/TIMEOUT: skip that portal this cycle. After resolving, run `alert.py --resolve <portal>_login`.
- CAPTCHA: `ask.py` "CAPTCHA aaya on <portal>, browser me solve karo." --options "Solved,Skip portal today"; also `alert.py` "CAPTCHA on <portal> | solve in browser, then tell me" --key "<portal>_captcha" --urgent
- Unknown form question: `ask.py "<portal> | <company> | <question text>"` (free text). Save reply to state/learned_answers.json as {"question": "...", "answer": "..."}. If blocked > 2 min, alert with --urgent.
- Approval for 60-79 jobs: ONE numbered message via `ask.py ... --timeout 90` (see job_matching.md); if it prints TIMEOUT, send the alert
  and check for his reply in `state/telegram_inbox.jsonl` next cycle. Also `alert.py` "Approve 60-79 jobs for <portal> | reply with numbers/All/None" --key "<portal>_approve" --urgent
- Ban/warning/restriction/CAPTCHA loop/account restricted: `alert.py` "<portal> WARNING: <details> | stop this portal today" --key "<portal>_ban" --urgent
- Missing key/resume/OAuth/credentials: `alert.py` "<need> chahiye | <exact path or action>" --key "<need>_setup" --urgent
- Step failed 3 times: `alert.py` "<portal> blocked at <step> after 3 tries | <what to fix>" --key "<portal>_<step>" --urgent
- Never send secrets (passwords, tokens, OTP) on Telegram.
