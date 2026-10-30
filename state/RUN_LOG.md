# RUN LOG (newest at bottom; agent appends one entry per cycle)
2026-10-27T22:11:29.205160+05:30: chat1 | naukri: skipped 5 | cursor -> 1 | next instahyre
2026-10-28T07:06:35.635266+05:30: chat1 | instahyre: login_blocked_browser_disconnected | cursor stays 0 | next retry
2026-10-28T12:51:50.2317998+05:30: chat1 | instahyre: login_blocked_onboarding | cursor stays 0 | next retry
2026-10-28T13:45:00+05:30: chat1 | instahyre: applied 3 auto, skipped 1 | cursor -> 1 | next hirist
2026-10-30T14:40:00+05:30: audit | no cycles 29-30 Oct (machine off/sleep, no autostart by design) | Instahyre verified: 4 applied on Oct 28 (yellow.ai 85, Aelyx 80, AlgoUniversity 75 unapproved, eShopbox 78 mis-logged as skipped) | root cause of the logged-out browser: port 9222 owned by Antigravity Chrome -> ports now 9332-9334 + session_check | blocker: opencode free usage limit reached, loop cannot run
2026-10-30T14:48:00+05:30: launch test | start_all.ps1 chat1 -> chrome 9332 (our profile), preflight 7/7 green, loop alive, first cycle blocked by big-pickle free usage limit (alert models_failed sent) | loop keeps retrying every 15 min, first successful cycle starts automatically once quota is back
