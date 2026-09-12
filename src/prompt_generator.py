"""
src/prompt_generator.py — Evcarix Auto-Studio
=============================================
v8.5 ALGORITHM & API OPTIMIZED:
  - Generates raw, searchable queries instead of poetic descriptions
  - Fully compatible with Pexels/Pixabay search limits
  - Fallback mechanisms updated for guaranteed video hits
"""

import os
import json
import logging

logger = logging.getLogger("PromptGenerator")

def generate_scene_prompts(topic: str, script: str, count: int = 6) -> list[str]:
    """Groq ile Pexels/Pixabay API uyumlu net sahne arama kelimeleri üretir."""

    # ── 1. Groq (Ücretsiz, Hızlı) ────────────────────────────────
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            logger.info("[PromptGen] Groq deneniyor...")
            from groq import Groq
            client = Groq(api_key=groq_key)

            prompt_text = f"""You are an expert video editor optimizing tags for Pexels and Pixabay video search APIs.
Generate exactly {count} short, raw, and direct search queries based on the video topic: '{topic}' and script: '{script[:400]}'

Rules:
1. Each string MUST be a simple, searchable keyword phrase that actually exists in stock footage sites (e.g., "tesla model s driving", "ev factory robot", "lithium battery cell close up").
2. DO NOT use abstract, poetic, or unsearchable words like "cinematic", "4k", "abstract", "visualization", "glowing", "stunning", "neon glow".
3. Keep each query under 3-5 words maximum. English only.
4. Focus strictly on electric vehicles, clean energy, future tech, batteries, charging stations.
5. Return ONLY a valid JSON array of {count} strings, nothing else.

Example format:
["electric car charging station", "ev factory production", "tesla highway driving"]"""

            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.6,
                max_tokens=500
            )

            text = response.choices[0].message.content
            result = _parse_json_list(text, count)
            if result:
                logger.info(f"[PromptGen] ✅ Groq başarılı: {len(result)} API arama kelimesi üretildi.")
                return result
        except Exception as e:
            logger.warning(f"[PromptGen] Groq hatası: {e}")

    # ── 2. Gemini (Yedek) ─────────────────────────────────────────
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            logger.info("[PromptGen] Gemini deneniyor...")
            from google import genai
            client = genai.Client(api_key=gemini_key)

            prompt_text = f"""Act as a Pexels API expert. Generate exactly {count} raw, simple video search queries for topic '{topic}'. 
Max 4 words per query. No adjectives like 'cinematic', 'epic', 'stunning'. Return ONLY a JSON array of strings."""
            
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt_text
            )
            if response and response.text:
                result = _parse_json_list(response.text, count)
                if result:
                    logger.info(f"[PromptGen] ✅ Gemini başarılı: {len(result)} API arama kelimesi üretildi.")
                    return result
        except Exception as e:
            logger.warning(f"[PromptGen] Gemini hatası: {e}")

    # ── 3. Statik Fallback ────────────────────────────────────────
    logger.warning("[PromptGen] Tüm AI'lar başarısız, statik fallback kullanılıyor.")
    return _get_fallback_prompts(topic, count)


def _parse_json_list(text, count):
    try:
        clean_text = text.strip()
        if "```" in clean_text:
            clean_text = clean_text.split("```")[1]
            if clean_text.startswith("json"):
                clean_text = clean_text[4:]
        data = json.loads(clean_text.strip())
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    return [str(x) for x in v[:count]]
        if isinstance(data, list):
            return [str(x) for x in data[:count]]
    except:
        pass
    return None


def _get_fallback_prompts(topic: str, count: int) -> list[str]:
    """API'ler çökerse stok sitelerinde kesinlikle videosu bulunan ham kelimeler."""
    base = [
        "electric car driving",
        "ev battery technology",
        "electric vehicle charging station",
        "tesla road trip",
        "futuristic car dashboard",
        "solar panels clean energy"
    ]
    result = []
    for i in range(count):
        result.append(base[i % len(base)])
    return result
