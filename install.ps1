# Aura installer for Windows 10/11. No administrator rights needed.
# Run by double-clicking install.cmd, or:  powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"
$src  = Split-Path -Parent $MyInvocation.MyCommand.Path
$home_dir = Join-Path $env:LOCALAPPDATA "Aura"
$venv = Join-Path $home_dir "venv"
$bin  = Join-Path $home_dir "bin"

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }

Step "Looking for Python 3.10 - 3.12"
$py = $null
foreach ($v in "3.12", "3.11", "3.10") {
    try {
        $found = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $found) { $py = $found.Trim(); break }
    } catch { }
}
if (-not $py) {
    Write-Host "Python 3.10 - 3.12 was not found." -ForegroundColor Yellow
    $answer = Read-Host "Install Python 3.12 now with winget? (y/n)"
    if ($answer -ne "y") { Write-Host "Install Python 3.12 from python.org, then run this again."; exit 1 }
    winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    $py = (& py "-3.12" -c "import sys; print(sys.executable)").Trim()
}
Write-Host "Using $py"

Step "Creating a private Python environment in $venv"
New-Item -ItemType Directory -Force -Path $home_dir, $bin | Out-Null
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) { & $py -m venv $venv }
$vpy = Join-Path $venv "Scripts\python.exe"
& $vpy -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }

Step "Installing Aura and its libraries (a few minutes)"
& $vpy -m pip install --upgrade $src
if ($LASTEXITCODE -ne 0) { throw "Installation failed. Scroll up for the reason." }

Step "Downloading the offline speech models (about 150 MB, once)"
& $vpy -c "import openwakeword.utils as u; u.download_models(model_names=['hey_jarvis']); from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8'); print('models ready')"
if ($LASTEXITCODE -ne 0) { throw "Model download failed. Check the internet connection and run this again." }

Step "Adding the 'aura' command"
$shim = Join-Path $bin "aura.cmd"
Set-Content -Path $shim -Encoding ASCII -Value "@echo off`r`n`"$venv\Scripts\python.exe`" -m aura %*"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $bin) {
    [Environment]::SetEnvironmentVariable("Path", (("$userPath".TrimEnd(";") + ";" + $bin).TrimStart(";")), "User")
    Write-Host "Added $bin to your PATH (open a new terminal to use 'aura')."
}

Step "Start Aura automatically when you sign in?"
$startup = Join-Path ([Environment]::GetFolderPath("Startup")) "Aura.lnk"
if ((Read-Host "Start Aura at sign-in? (y/n)") -eq "y") {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($startup)
    $link.TargetPath = Join-Path $venv "Scripts\pythonw.exe"
    $link.Arguments = "-m aura run"
    $link.WorkingDirectory = $home_dir
    $link.Description = "Aura voice assistant"
    $link.Save()
    Write-Host "Aura will start silently at sign-in. Remove it any time by deleting: $startup"
} elseif (Test-Path $startup) { Remove-Item $startup }

Step "Checking the installation"
& $vpy -m aura doctor
Write-Host "`nDone. Try:   aura text     (type commands)" -ForegroundColor Green
Write-Host "Then:        aura run      (voice: say 'hey jarvis')" -ForegroundColor Green
