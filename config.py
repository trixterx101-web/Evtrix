"""
config.py — Evcarix Auto-Studio
=================================
DÜZELTME: GEMINI_API_KEY_1..5 formatı eklendi, placeholder key'ler filtreleniyor.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini API Keys ───────────────────────────────────────────────────────────
# .env'de hem GEMINI_API_KEY (eski) hem GEMINI_API_KEY_1..5 (yeni) desteklenir.
# writer.py kendi key listesini kendisi yükler; config'deki değişkenler
# diğer modüller için referans niteliğindedir.
_PLACEHOLDER = {"", "YOUR_NEW_GEMINI_KEY_HERE", "YOUR_KEY_HERE", "PLACEHOLDER"}

def _get_gemini_keys() -> list[str]:
    seen, keys = set(), []
    # Önce çoklu format
    for i in range(1, 6):
        k = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
        if k and k not in _PLACEHOLDER and k not in seen:
            seen.add(k)
            keys.append(k)
    # Sonra tek key format
    for env_name in ("GEMINI_API_KEY", "GEMINIGEN_API_KEY"):
        k = os.getenv(env_name, "").strip()
        if k and k not in _PLACEHOLDER and k not in seen:
            seen.add(k)
            keys.append(k)
    return keys

GEMINI_API_KEYS: list[str] = _get_gemini_keys()
GEMINI_API_KEY: str = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""  # geriye dönük uyumluluk
GEMINIGEN_API_KEY: str = GEMINI_API_KEY

# ── Groq ─────────────────────────────────────────────────────────────────────
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_API_KEY_2 = os.getenv("GROQ_API_KEY_2", "")
GROQ_API_KEY_3 = os.getenv("GROQ_API_KEY_3", "")

# ── Other LLMs ───────────────────────────────────────────────────────────────
OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
COHERE_API_KEY      = os.getenv("COHERE_API_KEY", "")
HF_TOKEN            = os.getenv("HF_TOKEN", "")

# ── Video / Image APIs ───────────────────────────────────────────────────────
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY", "")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
PEXELS_API_KEY    = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY   = os.getenv("PIXABAY_API_KEY", "")
KLING_ACCESS_KEY  = os.getenv("KLING_ACCESS_KEY", "")
KLING_SECRET_KEY  = os.getenv("KLING_SECRET_KEY", "")

# ── YouTube ───────────────────────────────────────────────────────────────────
YOUTUBE_CLIENT_SECRET_PATH = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
YOUTUBE_TOKEN_PATH         = os.getenv("YOUTUBE_TOKEN_PATH", "token.json")
CHANNEL_ID                 = os.getenv("CHANNEL_ID", "")

# ── Video Settings ────────────────────────────────────────────────────────────
SHORT_VIDEO_DURATION_MIN = 45
SHORT_VIDEO_DURATION_MAX = 59
LONG_VIDEO_DURATION_MIN  = 240
LONG_VIDEO_DURATION_MAX  = 360
VIDEO_DURATION_MIN       = 45
VIDEO_DURATION_MAX       = 59

VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS    = 30

THUMBNAIL_WIDTH   = 1080
THUMBNAIL_HEIGHT  = 1920
THUMBNAIL_QUALITY = "4K"

# ── Content Settings ──────────────────────────────────────────────────────────
DEFAULT_LANGUAGE      = "en"
SUPPORTED_LANGUAGES   = ["en"]
ENABLE_TURKISH_TITLES = False
ENABLE_GLOBAL_CONTENT = True
ENABLE_AI_VIDEO_FALLBACK = False
ENABLE_STABILITY_AI   = False

# ── Output ───────────────────────────────────────────────────────────────────
OUTPUT_DIR    = "output"
TEMP_DIR      = "assets/temp"
THUMBNAIL_DIR = "output/thumbnails"


def validate_config():
    issues = []

    if not GEMINI_API_KEYS:
        issues.append("[ERROR] Gemini: Hic gecerli key yok (GEMINI_API_KEY_1..5 veya GEMINI_API_KEY)")
    else:
        print(f"[SUCCESS] Gemini: {len(GEMINI_API_KEYS)} key yuklendi")

    if not GROQ_API_KEY:
        issues.append("[WARNING] GROQ_API_KEY eksik")
    else:
        groq_count = sum(1 for k in [GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3] if k)
        print(f"[SUCCESS] Groq: {groq_count} key yuklendi")

    if not PEXELS_API_KEY:
        issues.append("[ERROR] PEXELS_API_KEY eksik (stok video icin gerekli)")
    else:
        print("[SUCCESS] Pexels: key yuklendi")

    for msg in issues:
        print(msg)

    return len([i for i in issues if i.startswith("[ERROR]")]) == 0


if __name__ == "__main__":
    validate_config()
