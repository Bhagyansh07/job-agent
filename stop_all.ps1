# Stop every run_loop.py process. Chrome/browser profiles are left alone by default.
#   powershell -ExecutionPolicy Bypass -File .\stop_all.ps1
#   powershell -ExecutionPolicy Bypass -File .\stop_all.ps1 -Browsers   # also close this project's Chrome + MCP servers
param(
    [switch]$Browsers
)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$n = 0
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*run_loop.py*" } |
    ForEach-Object {
        try { & taskkill.exe /PID $_.ProcessId /T /F | Out-Null; $n++ } catch { }
    }
Write-Host "stopped $n loop(s)"

if ($Browsers) {
    # Only this project's browser profiles and Playwright MCP servers, never your own Chrome.
    $b = 0
    Get-CimInstance Win32_Process -Filter "Name='chrome.exe' OR Name='node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and ($_.CommandLine -like "*browser-profiles*" -or $_.CommandLine -like "*playwright*mcp*") } |
        ForEach-Object {
            try { & taskkill.exe /PID $_.ProcessId /T /F | Out-Null; $b++ } catch { }
        }
    Write-Host "closed $b browser process(es) (profiles and logins are kept on disk)"
} else {
    Write-Host "browsers left open. They close on their own 10 min after the last tool call,"
    Write-Host "or run with -Browsers to close them now."
}
