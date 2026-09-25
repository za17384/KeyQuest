"""Runtime configuration for KEYSTROKE QUEST."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip()

DB_PATH = BASE_DIR / os.environ.get("KQ_DB_PATH", "keystroke_quest.db")

# Groq requests are given a short budget so a slow API never stalls a stage.
AI_TIMEOUT_SECONDS = float(os.environ.get("KQ_AI_TIMEOUT", "12"))

# How many drill lines to request per stage.
LINES_PER_STAGE = 6

SECRET_KEY = os.environ.get("KQ_SECRET_KEY", "keystroke-quest-local")


def ai_enabled() -> bool:
    """True when a Groq key is present and the SDK is importable."""
    if not GROQ_API_KEY:
        return False
    try:
        import groq  # noqa: F401
    except ImportError:
        return False
    return True
