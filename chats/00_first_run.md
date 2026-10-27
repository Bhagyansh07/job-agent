# FIRST RUN CHECKLIST (do once, in a normal opencode chat: "Read chats/00_first_run.md and do it")
0. If `resume/master.json` already exists and is valid, skip step 1 (it is the source of truth, already
   filled). Rebuild it only when Bhagyansh gives you a new PDF. Check with:
   `python -c "import json; json.load(open('resume/master.json', encoding='utf-8')); print('MASTER_OK')"`
1. Find his resume PDF in resume/ (any *.pdf). Extract text with pypdf:
   `python -c "from pypdf import PdfReader; print('\n'.join(p.extract_text() or '' for p in PdfReader('resume/resume.pdf').pages))"`
   (pdftotext is an optional fallback if pypdf fails.) Build `resume/master.json` following resume/master.example.json.
   - Use ONLY facts in the PDF. Do not invent anything. Keep original bullets verbatim; keep all numbers exact.
   - Fill config/profile.yaml `candidate:` contact fields from the PDF (email/phone/linkedin/github) if empty.
2. Run `python scripts/render_resume.py --tailored resume/master.json --out output/resumes/base_test.pdf` and confirm it renders.
3. Print the final skills list and projects list and send them to Telegram via notify.py so he can verify.
4. Ask on Telegram (ask.py) for every EMPTY value in config/answers.yaml (expected CTC, current CTC, etc.) and write his answers into the file.
5. Login session: for each chat browser (pw_chat1, pw_chat2, pw_chat3) open the portal login pages from chats/chat1.md, chat2.md, chat3.md one by one; he logs in himself in the visible window; wait for "Done" on Telegram each time. Never type his password.
6. Send "Setup complete" on Telegram.
