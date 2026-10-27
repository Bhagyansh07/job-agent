# Job Agent (OpenCode + Playwright + Telegram) - Bhagyansh

Kya karta hai: 3 OpenCode chats alag-alag portals pe insaan ki tarah scroll/click karke apply karte hain
(~100/day cap), har JD ke hisab se ATS resume banate hain (fake kuch nahi), LinkedIn pe connection + referral DM bhejte hain,
har portal ke baad Telegram pe audit report dete hain, recruiter mails/messages ka sirf alert dete hain (reply tum karoge).

## Setup (ek baar)
1. Install: Node.js, Python 3.10+, Google Chrome, OpenCode (`npm i -g opencode-ai`).
2. Windows timezone set karo: (UTC+05:30) India Standard Time (Settings -> Time & Language -> Time zone).
3. Is folder me terminal: `pip install -r requirements.txt`
4. Telegram setup (bot banane se lekar .env bharne tak):
   - @BotFather pe `/newbot` chalao -> token milega (yahi TELEGRAM_BOT_TOKEN hai).
   - Us bot ko apne account se ek message bhejo (warna bot reply nahi kar payega).
   - Browser me `https://api.telegram.org/bot<TOKEN>/getUpdates` kholo -> `result[0].message.chat.id` = TELEGRAM_CHAT_ID.
   - `.env.example` ko `.env` banao aur TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID bharo.
  (`copy` sirf pehli baar. Agar `.env` already hai to usko overwrite mat karo, usme tumhari keys hain.)
   - Setup ke baad BotFather se `/revoke` karke naya token bana lena (purana token kabhi kisi ko mat dena).
5. Google (Gmail OTP + Sheet tracker): console.cloud.google.com -> naya project -> Gmail API + Google Sheets API enable ->
   OAuth client (Desktop app) -> `credentials.json` download -> `secrets/credentials.json`.
   Naya Google Sheet banao, pehle tab ka naam `Applications` rakho, URL se Sheet ID `.env` me GOOGLE_SHEET_ID.
   Phir: `python scripts/google_auth.py` (browser me allow karo) aur `python scripts/tracker.py init-sheet`.
   (Gmail read-only grant OTP/mail padhne ke liye hai. Cold email bhejne ke liye alag `python scripts/google_auth.py --send`
   chalao jo `secrets/token_send.json` banata hai, taaki read-only grant chalta rahe. Token missing ho to
   sheet sync skip ho jayega aur woh message console/log me dikhega.)
6. Apna resume PDF `resume/` me daalo.
7. `config/profile.yaml` me email/phone/links bharo. Criteria wahin se badal sakte ho.
8. First run: `opencode` kholo is folder me, bolo: **Read chats/00_first_run.md and do it**.
   Ye resume se master.json banayega, tumse answers.yaml ke khali sawal Telegram pe puchhega, aur
   tumhe har portal me khud login karwayega (password agent ko nahi dena hai, tum browser me khud login karoge).
9. Sanity check (kuch bhi apply karne se pehle):
   ```
   python scripts/health_check.py        # 0 fail hona chahiye, warn padh lo
   python scripts/watcher.py             # queue/new_jobs.jsonl me jobs aani chahiye
   python scripts/probe_ats.py --check   # watchlist ke saare boards live hain?
   python tools/verify_fixes.py          # 61-check regression suite (sab PASS hone chahiye)
   ```

## Naye laptop pe setup (GitHub ya zip se)
Private repo: `https://github.com/Bhagyansh07/job-agent` (personal data hai isliye private).
Backup/share ke liye zip: `job-agent-v5-FINAL.zip` (usme `.env`, `secrets/`, `browser-profiles/`, tracker rows, queue nahi hote).

```powershell
git clone https://github.com/Bhagyansh07/job-agent.git   # ya zip extract karo
cd job-agent
pip install -r requirements.txt
copy .env.example .env        # sirf tab jab .env pehle se na ho, warna keys overwrite ho jayengi
```
`.env`, `secrets/`, `browser-profiles/`, `tracker/*.csv`, `queue/`, `output/` repo aur zip dono me nahi aate, isliye
naye laptop pe unhe dobara banana padega:
- Telegram keys: README step 4.
- Google (optional): README step 5. Iske bina Gmail OTP aur Sheet sync off rahenge, baaki sab chalega.
- Resume PDF: `resume/` me daalo (master.json already bana hua hai, isliye PDF ke bina bhi render hoga).
- Portals me login: pehli baar agent khud browser kholke rukega, tum login karo.
Agar purani machine ka state chahiye (seen jobs, tracker rows) to `.env`, `secrets/`, `tracker/*.csv`,
`queue/new_jobs.jsonl`, `state/seen_jobs.jsonl` alag se copy karo.

## Roz chalane ka tareeka (3 terminals, 24x7)
```
python scripts/run_loop.py chat1     # Naukri, Instahyre, Foundit, Hirist, Apna, Internshala
python scripts/run_loop.py chat2     # LinkedIn(+outreach), Wellfound, Cutshort, Indeed, Glassdoor
python scripts/run_loop.py chat3     # Career pages/ATS, YC, remote boards, Unstop, discovery (+30 min watcher)
```
Har loop naya `opencode run` cycle chalata hai, state files me rehti hai. Laptop sleep na ho (power settings: never sleep),
charger laga rehne do.

Logon pe khud start karne ke liye:
```
powershell -ExecutionPolicy Bypass -File .\register_startup.ps1   # once
powershell -ExecutionPolicy Bypass -File .\start_all.ps1           # abhi start (teeno)
powershell -ExecutionPolicy Bypass -File .\start_all.ps1 -Chats chat1        # sirf ek chat
powershell -ExecutionPolicy Bypass -File .\start_all.ps1 -Chats chat1,chat2  # do chats
powershell -ExecutionPolicy Bypass -File .\stop_all.ps1            # sab band (child processes bhi)
powershell -ExecutionPolicy Bypass -File .\stop_all.ps1 -Browsers # loops + is project ke Chrome/MCP bhi band
```

## Fan / CPU (laptop garam hone ka asli reason)
Pehle lagta tha ki 3 chats = 9 browser stacks. Aisa nahi hai. MCP servers project folder ke saath share hote hain,
isliye teeno chat milkar **3 Chrome** use karte hain, 9 nahi (Chrome khud ek profile ke liye 8 processes banata hai,
isliye Task Manager me count zyada dikhta hai). Asli problem ye thi ki headed Chrome cycle khatam hone ke baad bhi
kabhi band nahi hota tha, to teen browser 24x7 chalte rehte the.

Ab fix hai (`opencode.json`):
- `--idle-timeout 600000`: 10 minute tak koi browser tool call na aaye to Chrome band, next tool call pe wapas khul
  jati hai. Profile disk pe rehta hai, isliye logins/CAPTCHA session nahi jaate. 10 min isliye ki cycle ke beech me
  (resume tailor karte waqt) Chrome galti se band na ho; cycles ke beech ka gap 15-30 min hai, to Chrome phir bhi
  har cycle ke baad band ho jati hai. Form bharte waqt agar kabhi page reset dikhe to value badha do (`1800000` = 30 min).
- `codemode: false`: isse browser tools model ko directly milte hain. Iske bina `opencode run` me MCP tools model tak
  pahunchte hi nahi the aur agent chupchaap webfetch pe fall back ho jata tha.
- `scripts/run_loop.py` har cycle start pe sirf **apne chat ke dead** Chrome/node processes reap karta hai (jinka
  parent mar chuka hai). Live MCP server ko haath nahi lagta, warna baaki chats toot jayengi.

Kam machine chahiye to `-Chats chat1` se ek hi loop chalao (coverage kam hoga, par kaam chalta rahega), ya
Windows power plan `Balanced` kar do (`powercfg /setactive SCHEME_BALANCED`). Abhi `Turbo` active hai.

## Control switches (state/ folder)
- **Pause**: `state/PAUSE` file banao -> teeno chats ruk jayenge (300s me check karte hain, file hatao to chalu).
  Sirf ek chat rokni ho to `state/PAUSE_chat1` (ya chat2/chat3) banao.
- **DRY_RUN**: `.env` me `DRY_RUN=1` -> agent final Submit kabhi nahi dabayega; decision `dry_` prefixed status se
  log hoga aur dry_ rows daily limits me count nahi hote. Sheet sync bhi skip hota hai. Outreach draft_ready pe rukta hai,
  cold email `draft` mode me rehta hai. Normal chalane ke liye `DRY_RUN=0` (pehle din 5-10 applications khud dekh lo).
- **Outreach**: `config/profile.yaml` me `outreach.mode: auto` hai. `DRY_RUN=1` tak safe hai; `DRY_RUN=0` karte hi agent
  LinkedIn pe connection requests/DMs khud bhejna shuru kar dega (12/day cap). Ye band chahiye to `mode: draft` kar do.
- **Per-chat daily budgets** (config/profile.yaml `limits.per_chat`): chat1 = 30, chat2 = 25, chat3 = 45 applications/day.
  Iske alawa per-portal caps aur global 100/day cap bhi lagti hai.
- **Cycle logs**: har cycle ka full opencode output `state/logs/<chat>_YYYYMMDD_HHMM.log` me jata hai (console pe last 30 lines).
  14 din purane .log apne aap delete ho jate hain.
- **Portal rotation**: har cycle me sirf 1 portal (teeno chats), aur ek cycle me max 8 applications. Cursor
  `state/chat1_cursor.txt` etc. me rehta hai; jab tak current portal ka per-portal cap hit na ho ya uspe fresh
  eligible jobs khatam na ho jayein, cursor aage nahi badhta (ek portal kai cycles chal sakta hai). Har portal pe
  jab itni fresh jobs hon, to kam se kam 8 applications ka target (config/profile.yaml `session`).

## Context saving (session chhota rakhne ke liye)
- Agent job description ko **text extraction** se padhta hai (`document.body.innerText` browser evaluate, ya Playwright MCP text/read tool).
- Full accessibility snapshot sirf tab leta hai jab koi specific element ref pe click/select karna ho. Isse session chhota rehta hai.

## Naya (v3)
- **Late replies**: `state/telegram_inbox.jsonl` me woh replies aate hain jo Bhagyansh ne kisi ask() ke timeout ke baad bheje. Cycle start pe agent inhe padhkar matching question ka answer `state/learned_answers.json` me save karta hai, phir consumed lines inbox se hata deta hai.
- **Daily summary**: `scripts/daily_report.py` aaj ki counts (status + portal wise), average match aur total rows ka chhota Telegram message banata hai; `GOOGLE_SHEET_ID` set ho to Sheet ka link bhi jodta hai. `run_loop.py` ise din me ek baar chalata hai (guard file `state/.daily_report_date`). Test ke liye `python scripts/daily_report.py --dry` (sirf print, send nahi).
- **Writing style**: `skills/writing_style.md` - cover letter, "why us", founder note aur LinkedIn DM ke liye anti-AI style guide (no em/en dash, banned words, length limits, pre-submit checklist). HARD RULE 20 isko follow karne ko kehta hai.
- **Outreach mode**: `config/profile.yaml` me `outreach.mode` = `auto` (abhi) ya `draft`. `auto` me connection requests/DMs direct jaate hain (caps ke andar); `draft` me messages `tracker/outreach.csv` me `draft_ready` status se likhe jaate hain aur pehle ek numbered approval message jaata hai.
- **Cold email**: `scripts/cold_email.py` + `config/cold_email.yaml`. Default `mode: draft` (kuch bhi send nahi hota). Apollo se named contacts, Hunter fallback, `never_email` generic inboxes block, one contact per domain, warm-up 5 -> 15 -> 25/day, 4h gap, `DRY_RUN=1` par send held.
- **Recruiter sheet**: `scripts/recruiter_sheet.py fetch/stats/verify/queue` public sheet se contacts laata hai, MX check karta hai, per-domain cap lagata hai; RAW data `state/import/` me gitignored rehta hai.
- **New account password**: `python scripts/portal_account.py new --portal <name> --email <email>` sirf naye career-page account ke liye; password `secrets/portal_accounts.csv` me store hota hai aur ek baar print hota hai.
- **Remote/WFH**: remote ya WFH job kabhi sirf location ki wajah se skip nahi hota (HARD RULE 18). Bond/service agreement 12 months tak theek hai (HARD RULE 19).

## Important
- Naukri/LinkedIn/Indeed/Instahyre ki ToS automation allow nahi karti: ban ka risk hai. Isliye per-portal caps (mostly 10/day), raat me band (08:00-23:30),
  human delays rakhe hain. Main account ka backup/alternate account mat bhoolna; warning dikhe to agent us portal ko rok dega.
- Resume tailoring ke guard se agent koi skill/number add nahi kar sakta jo master.json me nahi hai.
- `opencode.json` me V2 `permissions` array hai (unattended chalne ke liye allow, phir `.env`/`secrets/`/`browser-profiles/`
  par read/edit/shell deny, aur `grep` poora block taaki secrets search na ho sake). Ye best-effort guard hai, sandbox nahi;
  residual risk `AUDIT.md` me likha hai.
- Playwright MCP pehli baar `npx -y` se download hota hai; Chrome windows visible rehti hain (login/CAPTCHA ke liye) aur
  idle 5 min baad apne aap band ho jati hain (logins profile me safe rehte hain).
- `config/watchlist.yaml` me nayi company add karne se pehle `python scripts/probe_ats.py --discover "<Company>"` chalao.
  Galat token 404 deta hai aur watcher use chupchaap skip karta hai (2026-10-27 se health_check aur watcher dead boards alert karte hain).
- Files: tracker/applications.csv (+Sheet), tracker/outreach.csv, tracker/cold_emails.csv, output/resumes/*.pdf, queue/, state/.
- Secrets (.env, secrets/, browser-profiles/) kisi ko mat bhejna, zip share mat karna.

## Folder map
AGENTS.md (rules) | chats/ (3 chat playbooks + first run) | skills/ (matching, apply flow, tailoring, writing_style, outreach, portals/*) |
scripts/ (tracker, telegram, gmail, resume PDF, watcher, runner, daily_report, cold_email, recruiter_sheet, portal_account, health_check, probe_ats) |
tools/verify_fixes.py (regression suite) | config/ (profile, answers, watchlist, cold_email) |
powershell: start_all.ps1 / stop_all.ps1 / register_startup.ps1 (24x7 auto-start)
