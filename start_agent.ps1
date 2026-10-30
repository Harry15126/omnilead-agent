# OmniLead 24/7 Watchdog Runner
# Automatically restarts if interrupted or after Windows network reconnects

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  OmniLead 24/7 Autonomous Sales Closer Watchdog Daemon" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

$PythonExe = Join-Path $ScriptDir "venv\Scripts\python.exe"
if (-Not (Test-Path $PythonExe)) {
    Write-Host "[!] Initializing virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    & ".\venv\Scripts\pip.exe" install -r requirements.txt
}

Write-Host "[*] Agent starting on http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "[*] Auto-restart watchdog enabled for continuous 24/7 execution." -ForegroundColor Yellow

while ($true) {
    try {
        & $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    } catch {
        Write-Host "[!] Process exited with notice: $_" -ForegroundColor Red
    }
    Write-Host "[*] Restarting agent in 5 seconds..." -ForegroundColor DarkYellow
    Start-Sleep -Seconds 5
}
