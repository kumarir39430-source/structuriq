import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is optional at runtime
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5").strip()
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "60000"))
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "data" / "history.db")))
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH

LLM_ENABLED = bool(ANTHROPIC_API_KEY)
