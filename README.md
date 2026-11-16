# StructurIQ

Turn **messy, unstructured text** (emails, invoices, meeting notes, chat messages, logs, PDFs, Word files) into **clean structured data**: document type, summary, keywords, key/value fields, entities (emails, phones, dates, amounts, people, organizations, URLs), tables, line items and action items.

## Features

- **Works fully offline** with a built-in rule-based extraction engine. No API key needed.
- **Optional Claude mode**: add an `ANTHROPIC_API_KEY` to `.env` for smarter extraction. If it fails, the app falls back to the rules engine automatically.
- **Web UI** with colour-highlighted entities, custom "fields to pull out", and tabs for Overview, Entities, Tables and JSON.
- **File upload**: txt, md, csv, json, log, pdf, docx (max 5 MB).
- **Export** as JSON, CSV or Markdown.
- **History** of past extractions stored in SQLite.
- **REST API** (FastAPI with interactive docs) and a **command-line tool**.
- **Tests** with pytest.

## Tech stack

Python, FastAPI, Uvicorn, Pydantic, SQLite, httpx, pypdf, python-docx, vanilla JavaScript, HTML and CSS.

## Project structure

```
structuriq/
├── app/
│   ├── main.py            FastAPI app and routes
│   ├── config.py          settings loaded from .env
│   ├── schemas.py         request models
│   ├── storage.py         SQLite history
│   ├── filereader.py      txt / pdf / docx to text
│   ├── exporters.py       JSON / CSV / Markdown export
│   ├── extractors/
│   │   ├── rules.py       offline extraction engine
│   │   ├── llm.py         optional Claude extractor
│   │   └── pipeline.py    combines rules + LLM
│   └── static/            index.html, style.css, app.js
├── samples/               example inputs (invoice, email, notes, messy note)
├── tests/                 pytest tests
├── cli.py                 command-line tool
├── run.bat / run.sh       one-command start
├── requirements.txt
└── .env.example
```

## Prerequisites

- Python 3.10 or newer (3.12 recommended)
- Git (only needed to clone or push)

Check your Python version:

```bash
python --version
```

## Setup and run

All commands run from the **project root** (the folder that directly contains `app/` and `requirements.txt`).

### Windows (PowerShell or VS Code terminal)

```powershell
# 1. Get the project
git clone https://github.com/kumarir39430-source/structuriq.git
cd structuriq

# 2. Create a virtual environment
python -m venv venv

# 3. Install dependencies (no need to activate the venv)
.\venv\Scripts\python -m pip install --upgrade pip
.\venv\Scripts\python -m pip install -r requirements.txt

# 4. Create your settings file
copy .env.example .env

# 5. Start the server
.\venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Shortcut that does steps 2 to 5 in one go:

```powershell
.\run.bat
```

### macOS / Linux (bash)

```bash
# 1. Get the project
git clone https://github.com/kumarir39430-source/structuriq.git
cd structuriq

# 2. Create a virtual environment
python3 -m venv venv

# 3. Install dependencies
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt

# 4. Create your settings file
cp .env.example .env

# 5. Start the server
venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Shortcut:

```bash
chmod +x run.sh
./run.sh
```

## Open it on localhost

When the terminal shows `Uvicorn running on http://127.0.0.1:8000`, open these in your browser:

| URL | What it is |
|---|---|
| http://localhost:8000 | The web app |
| http://localhost:8000/docs | Interactive API documentation (Swagger UI) |
| http://localhost:8000/api/health | Health check (shows whether Claude mode is on) |

To stop the server, press `Ctrl + C` in the terminal.

To use a different port, change `--port 8000` to another number, for example `--port 8080`, and open `http://localhost:8080`.

## How to use the web app

1. Choose a sample from **Load a sample...** (Invoice, Email, Meeting notes, Messy chat note), or paste your own text, or click **Upload file**.
2. Optionally type fields you want, for example `invoice number, total, due date`.
3. Click **Extract structure**.
4. Browse the tabs: **Overview**, **Entities**, **Tables**, **JSON**. Click **Highlighted** on the left to see the source text colour-coded by entity.
5. Download the result as JSON, CSV or Markdown, or reopen earlier results from **History**.

## Command-line usage

Run from the project root.

Windows (PowerShell):

```powershell
.\venv\Scripts\python cli.py samples\sample_invoice.txt --fields "invoice number,total" --format json
.\venv\Scripts\python cli.py samples\sample_email.txt --format md --out result.md
.\venv\Scripts\python cli.py samples\sample_notes.txt --format csv --out result.csv
```

macOS / Linux (bash):

```bash
venv/bin/python cli.py samples/sample_invoice.txt --fields "invoice number,total" --format json
venv/bin/python cli.py samples/sample_email.txt --format md --out result.md
venv/bin/python cli.py samples/sample_notes.txt --format csv --out result.csv
```

Options: `--fields`, `--mode auto|rules|llm`, `--format json|csv|md`, `--out FILE`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status and whether Claude mode is on |
| POST | `/api/extract` | Body: `{"text": "...", "fields": ["total"], "mode": "auto"}` |
| POST | `/api/extract/file` | Multipart form: `file`, optional `fields`, `mode` |
| POST | `/api/export` | Body: `{"result": {...}, "format": "json" or "csv" or "md"}` |
| GET | `/api/history` | List saved extractions |
| GET | `/api/history/{id}` | Get one saved extraction |
| DELETE | `/api/history/{id}` | Delete one saved extraction |

### Example requests

Windows (PowerShell):

```powershell
Invoke-RestMethod http://localhost:8000/api/health

$body = @{ text = "Total: `$50`nEmail: a@b.com"; fields = @("total"); mode = "auto" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/extract -ContentType "application/json" -Body $body
```

macOS / Linux (bash):

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "Total: $50\nEmail: a@b.com", "fields": ["total"], "mode": "auto"}'

curl -X POST http://localhost:8000/api/extract/file \
  -F "file=@samples/sample_invoice.txt" \
  -F "fields=invoice number,total"
```

## Settings (.env)

```
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-5-5
MAX_INPUT_CHARS=60000
DB_PATH=data/history.db
```

- Leave `ANTHROPIC_API_KEY` empty to use the offline rules engine only.
- To enable Claude mode, paste your key after the `=`, save, and restart the server. The badge in the top right changes to "Claude + rules".
- Never commit `.env`. It is already listed in `.gitignore`.

## Run the tests

Windows (PowerShell):

```powershell
.\venv\Scripts\python -m pytest
```

macOS / Linux (bash):

```bash
venv/bin/python -m pytest
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `Could not open requirements file` | You are in the wrong folder. Run `dir` (Windows) or `ls` (macOS/Linux) and make sure you can see `requirements.txt`. If you only see another `structuriq` folder, run `cd structuriq`. |
| PowerShell blocks venv activation | Use the commands above that call `.\venv\Scripts\python` directly. No activation is needed. |
| `pip install` fails on a very new Python (for example 3.14) | Install Python 3.12 and recreate the venv with `py -3.12 -m venv venv`. |
| `Address already in use` / port 8000 busy | Use another port, for example `--port 8001`, and open `http://localhost:8001`. |
| Red underlines in the editor under `pypdf` or `docx` | Packages are not installed in the selected interpreter. In VS Code or Antigravity press `Ctrl+Shift+P`, choose **Python: Select Interpreter**, and pick the one inside `venv`. |
| Page does not load | Make sure the server is still running in the terminal and the URL is exactly `http://localhost:8000`. |

## Known limits

- The rules engine is heuristic. Names and organizations are best-effort, phone detection expects 10 to 13 digits, and English text works best.
- Scanned (image-only) PDFs have no text layer, so nothing is extracted from them.
- Uploads are capped at 5 MB, and input text at `MAX_INPUT_CHARS`.

## Push to GitHub

Run from the project root. Make sure `.env` and `venv/` do not appear in `git status`.

```bash
git status
git add .
git commit -m "docs: add complete README with setup and localhost instructions"
git push
```

First-time setup of the repository:

```bash
git init
git add .
git commit -m "feat: add StructurIQ unstructured-to-structured extraction app"
git branch -M main
git remote add origin https://github.com/kumarir39430-source/structuriq.git
git push -u origin main
```

## Ideas to extend

- JSON-schema editor in the UI
- More document types in `DOC_TYPES` (`app/extractors/rules.py`)
- OCR for scanned PDFs
- Login and per-user history
- Docker support
