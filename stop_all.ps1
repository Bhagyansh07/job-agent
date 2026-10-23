# Stop every run_loop.py process. Chrome/browser profiles are left alone.
#   powershell -ExecutionPolicy Bypass -File .\stop_all.ps1
$n = 0
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*run_loop.py*" } |
    ForEach-Object {
        try { & taskkill.exe /PID $_.ProcessId /T /F | Out-Null; $n++ } catch { }
    }
Write-Host "stopped $n loop(s)"
