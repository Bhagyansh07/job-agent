# Start the job-agent loops (one process per chat) in separate minimised windows.
# Safe to run twice: a chat that is already running is skipped.
#   powershell -ExecutionPolicy Bypass -File .\start_all.ps1                  # all three
#   powershell -ExecutionPolicy Bypass -File .\start_all.ps1 -Chats chat1     # only chat1
#   powershell -ExecutionPolicy Bypass -File .\start_all.ps1 -Chats chat1,chat2
# Fewer chats = fewer Chrome windows + less CPU. One chat is perfectly usable.
param(
    [string[]]$Chats = @("chat1", "chat2", "chat3")
)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$valid = @("chat1", "chat2", "chat3")
$wanted = @()
foreach ($c in $Chats) {
    foreach ($one in ($c -split ",")) {
        $one = $one.Trim()
        if (-not $one) { continue }
        if ($valid -notcontains $one) {
            Write-Host "unknown chat '$one' (allowed: $($valid -join ', '))"
            exit 1
        }
        if ($wanted -notcontains $one) { $wanted += $one }
    }
}
if (-not $wanted) { Write-Host "no chats selected"; exit 1 }

$procs = @()
try {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*run_loop.py*" }
} catch {
    $procs = @()
}

foreach ($chat in $wanted) {
    $already = $procs | Where-Object { $_.CommandLine -like "*run_loop.py $chat*" }
    if ($already) {
        Write-Host "$chat already running (pid $($already.ProcessId))"
        continue
    }
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location '$root'; python scripts/run_loop.py $chat" `
        -WindowStyle Minimized
    Write-Host "$chat started"
    Start-Sleep -Seconds 3
}
# One long-lived Chrome per chat, so logins survive every cycle (agent attaches over CDP).
& powershell -ExecutionPolicy Bypass -File (Join-Path $root "start_chrome.ps1") -Chats $wanted

Write-Host "done. running: $($wanted -join ', ')"
Write-Host "pause switch: state\PAUSE (create) / remove to resume ; state\PAUSE_chat1 = one chat only"
