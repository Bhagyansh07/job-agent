# Open the AGENT's own Chrome profile, so you can log in to a portal yourself.
#
# Why this exists: the agent does NOT use your normal Chrome. It uses one dedicated profile
# per chat (browser-profiles\chat1 and so on). If you log in inside your normal Chrome window,
# the agent still sees "logged out" and keeps asking you. Use this script instead.
#
#   powershell -ExecutionPolicy Bypass -File .\login_browser.ps1            # chat1
#   powershell -ExecutionPolicy Bypass -File .\login_browser.ps1 -Chat chat2
#   powershell -ExecutionPolicy Bypass -File .\login_browser.ps1 -Chat chat1 -Url https://www.naukri.com/
#
param(
    [ValidateSet("chat1", "chat2", "chat3")]
    [string]$Chat = "chat1",
    [string]$Url = ""
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$profile = Join-Path $root "browser-profiles\$Chat"

if (-not (Test-Path $profile)) {
    New-Item -ItemType Directory -Path $profile -Force | Out-Null
    Write-Host "created profile folder: $profile"
}

$chrome = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $chrome) {
    Write-Host "chrome.exe not found. Install Chrome, or edit the path in this script."
    exit 1
}

# Same absolute profile path the Playwright MCP server uses. If the agent's browser is
# already open, Chrome reuses it and just opens a new tab, so logins land in the same profile.
$chromeArgs = @("--user-data-dir=$profile", "--profile-directory=Default", "--no-first-run", "--no-default-browser-check")
if ($Url) { $chromeArgs += $Url } else { $chromeArgs += "about:blank" }

Start-Process -FilePath $chrome -ArgumentList $chromeArgs
Write-Host "opened $Chat profile: $profile"
Write-Host "log in here (not in your normal Chrome), then send Done on Telegram."

