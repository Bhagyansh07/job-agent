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
$ports = @{ chat1 = 9222; chat2 = 9223; chat3 = 9224 }

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
