#!/usr/bin/env bash
set -e
[ -d venv ] || python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
venv/bin/python -m uvicorn app.main:app --reload --port 8000
