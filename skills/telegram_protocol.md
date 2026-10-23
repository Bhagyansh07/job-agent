# Telegram protocol
- Info only (audits, issues): `python scripts/notify.py "..."`  (keep under ~15 lines)
- Question: `python scripts/ask.py "..." --options "A,B"`  -> prints the answer or TIMEOUT. Default timeout 900 s.
- Login needed: ask.py "Login chahiye: <portal>. Browser (<pw_chatX>) me login kar do, phir Done dabao." --options "Done,Skip portal today"
  On Done: reload the portal and verify logged in. On Skip/TIMEOUT: skip that portal this cycle.
- CAPTCHA: ask.py "CAPTCHA aaya on <portal>, browser me solve karo." --options "Solved,Skip portal today"
- Unknown form question: ask.py "<portal> | <company> | <question text>" (free text reply). Save reply to state/learned_answers.json as {"question": "...", "answer": "..."}.
- Approval for 60-79 jobs: see job_matching.md. Put company, role, match %, 2-line reason and the link in ONE message.
- Never send secrets (passwords, tokens, OTP) on Telegram.
