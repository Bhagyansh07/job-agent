# Start the agent's Chrome once, and leave it running. The agent attaches to it over CDP.
#
# Why: a normal Playwright launch closes Chrome at the end of every cycle, which is why the
# window kept vanishing and logins felt lost. This Chrome stays open, so a portal login done
# once is still there in the next cycle, and you can log in yourself at any time.
#
#   powershell -ExecutionPolicy Bypass -File .\start_chrome.ps1            # all three chats
#   powershell -ExecutionPolicy Bypass -File .\start_chrome.ps1 -Chats chat1
#   powershell -ExecutionPolicy Bypass -File .\start_chrome.ps1 -Close     # close them
param(
    [string[]]$Chats = @("chat1", "chat2", "chat3"),
    [switch]$Close
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
# 9222 is Chrome's default debugging port, so other tools grab it first (Antigravity's browser
# had it on 30 Oct). If that happens the MCP "attaches" to the wrong profile: every portal looks
# logged out and applications go nowhere. 9332-9334 are ours alone.
$ports = @{ chat1 = 9332; chat2 = 9333; chat3 = 9334 }

$chrome = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $chrome) { Write-Host "chrome.exe not found"; exit 1 }

$wanted = @()
foreach ($c in $Chats) { foreach ($one in ($c -split ",")) { $one = $one.Trim(); if ($one) { $wanted += $one } } }

if ($Close) {
    foreach ($chat in $wanted) {
        $profile = Join-Path $root "browser-profiles\$chat"
        Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
            Where-Object { $_.CommandLine -and $_.CommandLine -like "*$profile*" } |
            ForEach-Object { & taskkill.exe /F /T /PID $_.ProcessId 2>&1 | Out-Null }
        Write-Host "closed $chat"
    }
    exit 0
}

foreach ($chat in $wanted) {
    if (-not $ports.ContainsKey($chat)) { Write-Host "unknown chat $chat"; continue }
    $profile = Join-Path $root "browser-profiles\$chat"
    $port = $ports[$chat]
    if (-not (Test-Path $profile)) { New-Item -ItemType Directory -Path $profile -Force | Out-Null }

    $running = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$profile*" }
    if ($running) { Write-Host "$chat already open (port $port)"; continue }

    $owner = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($owner) {
        $ownerCmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($owner.OwningProcess)" -ErrorAction SilentlyContinue).CommandLine
        Write-Host "PORT BLOCKED: $port is already used by another program."
        Write-Host "  $ownerCmd"
        Write-Host "  Not starting $chat. The agent would attach to that browser instead of $profile,"
        Write-Host "  which makes every portal look logged out. Close that program or change the port."
        $script:portBlocked = $true
        continue
    }

    $chromeArgs = @(
        "--user-data-dir=$profile",
        "--profile-directory=Default",
        "--remote-debugging-port=$port",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate",
        "about:blank"
    )
    Start-Process -FilePath $chrome -ArgumentList $chromeArgs -WindowStyle Minimized
    Write-Host "$chat browser: port $port, profile $profile"
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "Leave these windows open. The agent attaches to them over CDP and never closes them."
Write-Host "Log in to any portal in these windows (not your normal Chrome) and it stays logged in."
if ($script:portBlocked) { exit 1 }
