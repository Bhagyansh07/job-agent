# LEARNINGS (agent appends one line per reliable trick: portal | trick)
instahyre | /candidate/onboard/ with your name in the title = logged in (onboarding wizard). Go to /candidate/opportunities/ directly; never alert for login here.
all portals | 'Ref <id> not found in the current page snapshot' after a navigation = stale snapshot, take a new one. Not a login or ban signal.
all portals | a CDP port answering HTTP 200 is not proof it is our Chrome: on 30 Oct 9222 belonged to Antigravity's profile, so every portal looked logged out. Check the listener's --user-data-dir (now ports 9332-9334, scripts/session_check.py).
instahyre | the real applied list is https://www.instahyre.com/candidate/opportunities/?matching=true&status=1 (the 'Applied jobs' tab). Use it to prove a submission happened; /candidate/opportunities/applied/ is a 404.
