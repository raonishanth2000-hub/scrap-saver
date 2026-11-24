"""Settings, read from environment variables (or a .env file)."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv is optional
    pass

ROOT = Path(__file__).resolve().parent.parent

# Which AI provider to use: "openai" (paid), "gemini" (free tier) or "groq" (free tier).
# All three are called through the OpenAI Python library.
PROVIDERS = {
    "openai": {
        "base_url": None,
        "models": ["gpt-5-nano", "gpt-5-mini", "gpt-4.1-mini", "gpt-4o-mini"],
        "embedding": "text-embedding-3-small",
        "key_env": "OPENAI_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.0-flash"],
        "embedding": "gemini-embedding-001",
        "key_env": "GEMINI_API_KEY",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "llama-3.1-8b-instant"],
        "embedding": "",  # Groq has no embeddings: search uses keywords + synonyms
        "key_env": "GROQ_API_KEY",
    },
}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
if LLM_PROVIDER not in PROVIDERS:
    # Pick automatically from whichever key is present.
    LLM_PROVIDER = next((p for p in ("openai", "gemini", "groq") if os.getenv(PROVIDERS[p]["key_env"], "").strip()), "openai")
_P = PROVIDERS[LLM_PROVIDER]

OPENAI_API_KEY = os.getenv(_P["key_env"], "").strip()
BASE_URL = os.getenv("LLM_BASE_URL", "").strip() or _P["base_url"]
# First choice of chat model (optional). If unavailable, Scrap Saver tries the provider's other models in order.
OPENAI_MODEL = (os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or _P["models"][0]).strip()
FALLBACK_MODELS = [m for m in _P["models"] if m != OPENAI_MODEL]
EMBEDDING_MODEL = (os.getenv("LLM_EMBEDDING_MODEL") or os.getenv("OPENAI_EMBEDDING_MODEL") or _P["embedding"]).strip()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
# A 16-character Google "App password" (not your normal password).
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()

DB_PATH = Path(os.getenv("PAYTRAIL_DB", str(ROOT / "data" / "paytrail.db")))

# How many recent receipt-like emails to read per sync.
MAX_EMAILS = int(os.getenv("PAYTRAIL_MAX_EMAILS", "60"))
# How far back to look, in days.
LOOKBACK_DAYS = int(os.getenv("PAYTRAIL_LOOKBACK_DAYS", "365"))


def has_openai() -> bool:
    return bool(OPENAI_API_KEY)


def has_gmail() -> bool:
    return bool(GMAIL_ADDRESS and GMAIL_APP_PASSWORD)
