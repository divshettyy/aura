# Removes Aura. Your notes (Documents\Aura Notes) and screenshots are kept.
$ErrorActionPreference = "SilentlyContinue"
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like "*-m aura*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Remove-Item (Join-Path ([Environment]::GetFolderPath("Startup")) "Aura.lnk")
$bin = Join-Path $env:LOCALAPPDATA "Aura\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", (($userPath -split ";" | Where-Object { $_ -and $_ -ne $bin }) -join ";"), "User")
Remove-Item -Recurse -Force (Join-Path $env:LOCALAPPDATA "Aura")
# Offline speech model downloaded by install.ps1 (~150 MB), orphaned once the venv is gone.
Remove-Item -Recurse -Force (Join-Path $env:USERPROFILE ".cache\huggingface\hub\models--Systran--faster-whisper-base.en")
if ((Read-Host "Also delete settings, reminders and the action log in $env:APPDATA\Aura? (y/n)") -eq "y") {
    Remove-Item -Recurse -Force (Join-Path $env:APPDATA "Aura")
}
Write-Host "Aura removed."
