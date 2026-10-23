# Start all three job-agent loops (one per chat) in separate minimised windows.
# Safe to run twice: a chat that is already running is skipped.
#   powershell -ExecutionPolicy Bypass -File .\start_all.ps1
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$procs = @()
try {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*run_loop.py*" }
} catch {
    $procs = @()
}

foreach ($chat in @("chat1", "chat2", "chat3")) {
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
Write-Host "done. pause switch: state\PAUSE (create) / remove to resume"
