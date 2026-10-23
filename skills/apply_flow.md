# Apply flow (all portals)
0. Pre: `tracker.py check --portal <p>` (stop if LIMIT) and `tracker.py exists --url <url>` (skip if YES).
1. Read JD fully (scroll). Score per job_matching.md.
2. Resume:
   - Portals that let you upload a file per application (LinkedIn Easy Apply, Wellfound, YC WaaS, Cutshort, career pages/ATS, Internshala): tailor per skills/resume_tailoring.md and upload the PDF with the browser file-upload tool.
   - Portals that use the profile resume (Naukri, Instahyre, Foundit, Hirist, Apna, Indeed profile resume): DON'T swap the profile resume per job. Apply with the profile resume. Refresh headline / key skills only once a day if clearly needed.
3. Fill the form human-like (type with short pauses, scroll, pick dropdowns normally).
   - Known fields from config/answers.yaml. Unknown question -> state/learned_answers.json -> else Telegram ask.
   - "Why us / cover letter / about you" field present -> write 3-5 specific lines (company product/mission from their site + his matching project). Professional, no fluff, no fake claims. Follow skills/writing_style.md. Required by him on every field that exists.
   - Create account on a career page (Workday etc.): allowed using his Gmail from config/profile.yaml candidate.email. Password: generate a strong random one, save it ONLY in secrets/portal_accounts.csv (portal,email,password,date). OTP/verification mail -> `gmail_reader.py otp`.
4. Before the final Submit: check the resume is attached, no field is empty/wrong, no payment/ID request. Then Submit.
5. Verify success (confirmation text/"Applied" badge). If unsure, reload the application page and check.
6. Log: `python scripts/tracker.py add --portal <p> --company "<c>" --role "<r>" --location "<l>" --url "<u>" --match <score> --status applied_auto|applied_approved --resume "<pdf or profile>" --notes "<why>"`
7. Wait random 25-90 s. Next job.
Failures: form breaks twice -> log `failed` with reason and move on. Never retry-loop.
After successful apply with match >= 80 at a company worth a referral: append company to `state/referral_queue.txt` (one line: company | role | job url) for chat2's outreach step.
