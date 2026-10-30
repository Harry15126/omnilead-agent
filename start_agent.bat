@echo off
title OmniLead 24/7 Autonomous Sales Closer
echo ========================================================
echo   OmniLead 24/7 Autonomous Lead Hunter & Closer Agent
echo ========================================================
echo.

cd /d "%~dp0"

IF NOT EXIST "venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found. Creating venv...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [*] Installing dependencies...
    pip install -r requirements.txt
) ELSE (
    call venv\Scripts\activate.bat
)

echo [*] Starting OmniLead Agent on http://127.0.0.1:8000 ...
echo [*] Press Ctrl+C to stop.
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
