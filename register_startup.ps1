# Start the job agent at every Windows logon, hidden, current user only, no admin needed.
# Run ONCE:            powershell -ExecutionPolicy Bypass -File .\register_startup.ps1
# Remove later:        powershell -ExecutionPolicy Bypass -File .\register_startup.ps1 -Remove
param([switch]$Remove)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$startup = [Environment]::GetFolderPath("Startup")
$target = Join-Path $startup "JobAgent24x7.vbs"

if ($Remove) {
    if (Test-Path $target) { Remove-Item $target -Force; Write-Host "Removed $target" }
    else { Write-Host "Nothing to remove" }
    exit 0
}

$vbs = @"
' Auto-generated: starts the job agent hidden at logon.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "$root"
sh.Run "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File ""$root\start_all.ps1""", 0, False
"@
Set-Content -Path $target -Value $vbs -Encoding ascii
Write-Host "Installed: $target"
Write-Host "It will start at your next logon. Create state\PAUSE to keep it idle."
Write-Host "Start now without logging out: powershell -ExecutionPolicy Bypass -File .\start_all.ps1"
