import os

from dotenv import load_dotenv

load_dotenv()


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./menu.db")
    # Render hands out postgres:// or postgresql:// URLs; we ship psycopg 3.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _database_url()

# Public origin used in QR codes, e.g. https://cartaclara.tech
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

# mock | tinker | openai (any OpenAI-compatible server: Ollama, vLLM, llama.cpp)
LLM_BACKEND = os.getenv("LLM_BACKEND", "mock")
LLM_CONCURRENCY = int(os.getenv("LLM_CONCURRENCY", "4"))

TINKER_BASE_MODEL = os.getenv("TINKER_BASE_MODEL", "Qwen/Qwen3.5-4B")
# tinker://<run_id>/sampler_weights/<name>, printed by training/train.py.
# Empty means "sample from the untuned base model".
TINKER_MODEL_PATH = os.getenv("TINKER_MODEL_PATH", "")

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ollama")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gemma3:4b")

# Optional: per-restaurant glossary memory. Left empty, the glossary is off.
BACKBOARD_API_KEY = os.getenv("BACKBOARD_API_KEY", "")
BACKBOARD_BASE_URL = os.getenv("BACKBOARD_BASE_URL", "https://app.backboard.io/api")
