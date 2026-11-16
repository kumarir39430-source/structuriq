@echo off
REM Run from the project root. Works without activating the venv (avoids PowerShell policy issues).
if not exist venv (
  python -m venv venv
)
venv\Scripts\python -m pip install -r requirements.txt
if not exist .env copy .env.example .env
venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
