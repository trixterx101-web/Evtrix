"""
src/writer.py — Evtrix Auto-Studio
====================================
v9.0 EVTRIX OPTIMIZED:
  - Brand name standardized to 'Evtrix' everywhere
  - Groq (Primary) / OpenRouter (Fallback)
  - Dynamic Title selection between Fact and Curiosity/Question
  - #Shorts added to description (YouTube Shorts algorithm)
  - Stronger CTA and disclaimer
"""

import os
import time
import random
import logging
import re
import json
from typing import Optional

print("=== WRITER LOADED — BRAND: EVTRIX v9.0 ===", flush=True)
logger = logging.getLogger("Writer")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

ENABLE_GEMINI = False
PRIMARY_LLM = "groq"

_PLACEHOLDERS = {"", "YOUR_NEW_GEMINI_KEY_HERE", "YOUR_KEY_HERE", "PLACEHOLDER", "none", "None"}
_cooldowns: dict[str, float] = {}

STOCK_DISCLAIMER = (
    "Stock footage courtesy of Pexels, Pixabay (CC0). "
    "Manufacturer press imagery used for editorial/informational purposes only. "
    "No affiliation with any manufacturer shown."
)

def _load_keys(env_names: list[str]) -> list[str]:
    seen, out = set(), []
    for name in env_names:
        k = os.getenv(name, "").strip()
        if k and k not in _PLACEHOLDERS:
            if k not in seen:
                seen.add(k)
                out.append(k)
    return out

_GROQ_KEYS = _load_keys(["GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3"])
_GEMINI_KEYS = _load_keys(["GEMINI_API_KEY", "GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_4", "GEMINI_API_KEY_5"])

def _available_keys(keys: list[str]) -> list[str]:
    now = time.time()
    return [k for k in keys if _cooldowns.get(k, 0) <= now]

# ─────────────────────────────────────────────────────────────────────────────
# PROVIDERS
# ─────────────────────────────────────────────────────────────────────────────

def call_groq(prompt: str, model: str = "llama-3.3-70b-versatile") -> Optional[str]:
    avail = _available_keys(_GROQ_KEYS)
    if not avail: return None
    try:
        from groq import Groq
        for key in avail:
            try:
                client = Groq(api_key=key)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=900,
                )
                return resp.choices[0].message.content.strip()
            except Exception:
                _cooldowns[key] = time.time() + 120
    except: pass
    return None

def call_openrouter(prompt: str, model: str = "meta-llama/llama-3-8b-instruct:free") -> Optional[str]:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key or key in _PLACEHOLDERS: return None
    try:
        import requests
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
    except: pass
    return None

def call_openai(prompt: str, model: str = "gpt-4o-mini") -> Optional[str]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key in _PLACEHOLDERS: return None
    try:
        import requests
        response = requests.post(
            url="https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
    except: pass
    return None

def call_gemini(prompt: str, model: str = "gemini-2.0-flash") -> Optional[str]:
    if not ENABLE_GEMINI: return None
    avail = _available_keys(_GEMINI_KEYS)
    if not avail: return None
    try:
        import google.generativeai as genai
        for key in avail:
            try:
                genai.configure(api_key=key)
                m = genai.GenerativeModel(model)
                resp = m.generate_content(prompt, request_options={"timeout": 60})
                return resp.text.strip()
            except Exception as e:
                logger.error(f"[Gemini REAL ERROR] {e}")
                _cooldowns[key] = time.time() + 300
    except: pass
    return None

# ─────────────────────────────────────────────────────────────────────────────
# CORE CHAIN
# ─────────────────────────────────────────────────────────────────────────────

def _llm_chain(prompt: str, fallback: str = "") -> str:
    """v9.0 Revised Chain"""
    providers = [
        lambda: call_groq(prompt),
        lambda: call_openrouter(prompt, "meta-llama/llama-3-8b-instruct:free"),
        lambda: call_openrouter(prompt, "mistralai/mistral-7b-instruct"),
    ]

    if ENABLE_GEMINI:
        providers.append(lambda: call_gemini(prompt))

    for prov in providers:
        try:
            res = prov()
            if res:
                if "groq" in str(prov): logger.info("[LLM] ✅ Groq aktif")
                return res
        except: continue

    return fallback

# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API v9.0 (Evtrix Optimized)
# ─────────────────────────────────────────────────────────────────────────────

def generate_seo_metadata(topic: str, is_long: bool = False) -> dict:
    """Tek bir LLM çağrısı ile tüm SEO metadatayı (Title, Tags, Hook, SEO Description) üretir."""
    brand_style = (
        "Style: Data-driven, analytical, no-hype. Language: ALWAYS US ENGLISH. Tone: Global Professional. "
        "Identity: Evtrix — The #1 Electric Vehicle Data Channel. Motto: 'No hype. Just numbers.'"
    )

    if is_long:
        prompt = (
            f"Generate EXPERT YouTube SEO metadata for a 5-10 minute deep-dive EV video about: '{topic}'.\n"
            f"{brand_style}\n"
            "SEO RULES:\n"
            "1. Generate TWO TITLE VERSIONS (Version A: Fact-based, Version B: Curiosity-based).\n"
            "2. Max 70 chars per title. High-CTR. Put main search keywords at the absolute BEGINNING.\n"
            "3. TAGS: 20 high-ranking tags including broad and specific search terms.\n"
            "4. DESCRIPTION HOOK: Two different opener lines (Hook A and Hook B).\n"
            "5. SEO DESCRIPTION: A detailed, keyword-rich description paragraph (3-4 sentences) that naturally describes the topic for search algorithm indexation.\n"
            "Return ONLY JSON:\n"
            "{\n"
            "  \"title_a\": \"[FACT TITLE]\",\n"
            "  \"title_b\": \"[CURIOSITY TITLE]\",\n"
            "  \"tags\": [\"tag1\", \"tag2\", ...],\n"
            "  \"hook_a\": \"[HOOK VERSION A]\",\n"
            "  \"hook_b\": \"[HOOK VERSION B]\",\n"
            "  \"keywords\": [\"kw1\", \"kw2\", ...],\n"
            "  \"seo_description\": \"[Detailed SEO Description Paragraph]\"\n"
            "}"
        )
    else:
        prompt = (
            f"Generate VIRAL YouTube Shorts SEO metadata for: '{topic}'.\n"
            f"{brand_style}\n"
            "SEO RULES:\n"
            "1. Generate TWO TITLE VERSIONS (Version A: Number-heavy, Version B: Question-based).\n"
            "2. Max 55 chars per title. High-CTR viral style. Use numbers (%, $, Miles, kWh).\n"
            "3. TAGS: 15 high-velocity trending tags including viral short-form tags. MUST include: 'Shorts', 'EVShorts', 'ElectricVehicles'.\n"
            "4. HOOK: Two punchy, keyword-rich opening sentences (Hook A and Hook B). Start with a shocking stat.\n"
            "5. SEO SUMMARY: A short 2-sentence punchy summary filled with search terms.\n"
            "Return ONLY JSON:\n"
            "{\n"
            "  \"title_a\": \"[NUMBER TITLE]\",\n"
            "  \"title_b\": \"[QUESTION TITLE]\",\n"
            "  \"tags\": [\"tag1\", \"tag2\", ...],\n"
            "  \"hook_a\": \"[PUNCHY HOOK A]\",\n"
            "  \"hook_b\": \"[PUNCHY HOOK B]\",\n"
            "  \"seo_description\": \"[Short SEO Summary]\"\n"
            "}"
        )

    res = _llm_chain(prompt)
    try:
        match = re.search(r'\{.*\}', res, re.DOTALL)
        if match: return json.loads(match.group(0))
    except: pass
    return {
        "title_a": f"{topic.upper()} — The Real Numbers",
        "title_b": f"The Truth About {topic}?",
        "tags": ["ev", "electric car", "Evtrix", "Shorts", "EVShorts", "ElectricVehicles"],
        "hook_a": "The truth about EVs.",
        "hook_b": "Shocking EV numbers.",
        "seo_description": f"Exploring the latest data and trends behind {topic}. We break down the key numbers and what they mean for the future of electric vehicles."
    }

def generate_script(topic: str, duration_s: int = 52, is_long: bool = False, **kwargs) -> dict:
    words = int(duration_s * 2.4)

    if is_long:
        tone = (
            "Style: No hype. Just numbers. Fact-first. Language: MANDATORY US ENGLISH. "
            "Start naturally with a strong shocking statistic — NO greetings, NO 'welcome to'. "
            "End with: 'Subscribe to Evtrix for real EV data every week.'"
        )
        prompt = (
            f"Write a professional {duration_s}-second deep-dive script (~{words} words) about: {topic}.\n"
            f"{tone}\n"
            "Structure: Hook (shocking stat) -> Data Analysis -> Expert Insight -> Conclusion.\n"
            "CRITICAL: USE US ENGLISH ONLY. GLOBAL PERSPECTIVE. Real numbers only.\n"
            "Output ONLY the script text."
        )
    else:
        tone = (
            "Style: No hype. Just numbers. Fact-first. Language: MANDATORY US ENGLISH. "
            "CRITICAL RULE: NEVER use introduction phrases like 'Welcome to', 'In this video', 'Hello', 'Hey'. "
            "Start IMMEDIATELY with a shocking number, statistic, or fact. "
            "Use specific percentages, kWh values, and real-world data. "
            "End naturally with: 'Subscribe to Evtrix for real EV data.'"
        )
        prompt = (
            f"Write a viral {duration_s}-second YouTube Shorts script (~{words} words) about: {topic}.\n"
            f"{tone}\n"
            "Use specific percentages and kWh values. Global examples (USA, Europe, China).\n"
            "CRITICAL: US ENGLISH ONLY. No filler words. Every sentence must have a data point.\n"
            "Output ONLY the script text."
        )

    script = _llm_chain(prompt, fallback=f"The data on {topic} is shocking. Real numbers reveal surprising trends that most EV owners don't know. Subscribe to Evtrix for more.")
    return {"script": script, "voice": "male" if is_long else "female"}


class CreativeWriter:
    def generate_short_content(self, topic: str):
        meta = generate_seo_metadata(topic, is_long=False)
        script_data = generate_script(topic, duration_s=52, is_long=False)

        final_tags = self._clean_tags(meta.get("tags", ["ev", "ai", "tech"]))

        chosen_title = random.choice([meta.get('title_a'), meta.get('title_b')])
        if not chosen_title:
            chosen_title = meta.get('title', topic)

        # Build SEO-optimized description with #Shorts for YouTube algorithm
        hashtag_tags = [f"#{t.replace(' ', '')}" for t in final_tags[:10]]
        # Ensure #Shorts is always present for YouTube Shorts algorithm
        if "#Shorts" not in hashtag_tags:
            hashtag_tags.insert(0, "#Shorts")
        if "#EVShorts" not in hashtag_tags:
            hashtag_tags.insert(1, "#EVShorts")

        desc = (
            f"⚡ {meta.get('hook_a', meta.get('hook', 'Shocking EV data.'))}\\n\\n"
            f"{meta.get('seo_description', 'Exploring the latest EV data and trends.')}\\n\\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\\n"
            f"📊 MORE EV DATA FROM EVTRIX\\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\\n"
            f"🔔 Subscribe for daily EV data & real-world tests.\\n"
            f"📱 Follow Evtrix — No hype. Just numbers.\\n\\n"
            f"{' '.join(hashtag_tags)}\\n\\n"
            f"---\\n"
            f"{STOCK_DISCLAIMER}"
        )

        return {
            "title": chosen_title,
            "script": script_data["script"],
            "voice": script_data["voice"],
            "tags": final_tags,
            "description": desc,
            "category": "short",
            "category_id": "28"  # Science & Technology
        }

    def generate_long_content(self, topic: str, duration_s: int = 300):
        meta = generate_seo_metadata(topic, is_long=True)
        script_data = generate_script(topic, duration_s=duration_s, is_long=True)

        final_tags = self._clean_tags(meta.get("tags", []))

        # Estimate chapters based on duration
        intro_end = "0:00"
        analysis_start = "1:00"
        insight_start = f"{duration_s // 60 // 2}:{(duration_s // 2) % 60:02d}"
        conclusion_start = f"{(duration_s - 60) // 60}:{(duration_s - 60) % 60:02d}"

        hashtag_tags = [f"#{t.replace(' ', '')}" for t in final_tags[:12]]

        desc = (
            f"🚀 {meta.get('hook_a', meta.get('hook', 'Expert EV analysis.'))}\\n\\n"
            f"{meta.get('seo_description', 'Deep-diving into the raw data and trends.')}\\n\\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
            f"⏱️ CHAPTERS\\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
            f"{intro_end} — Hook & Key Data Point\\n"
            f"{analysis_start} — Deep Data Analysis\\n"
            f"{insight_start} — Expert Insight\\n"
            f"{conclusion_start} — Final Verdict\\n\\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
            f"📌 MORE FROM EVTRIX\\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
            f"⚡ Key points covered:\\n"
            f"— Industry-leading EV data analysis\\n"
            f"— Technical specifications & real-world performance\\n"
            f"— Future market impact & what it means for you\\n\\n"
            f"🔔 Subscribe to Evtrix — The #1 EV Data Channel.\\n"
            f"📱 New data-driven EV content every week.\\n\\n"
            f"{' '.join(hashtag_tags)}\\n\\n"
            f"---\\n"
            f"{STOCK_DISCLAIMER}"
        )

        chosen_title = random.choice([meta.get('title_a'), meta.get('title_b')])
        if not chosen_title:
            chosen_title = meta.get('title', f"{topic} — EV Data Deep Dive | Evtrix")

        return {
            "title": chosen_title,
            "script": script_data["script"],
            "voice": "male",
            "tags": final_tags,
            "description": desc,
            "category": "long",
            "category_id": "28"  # Science & Technology
        }

    def _clean_tags(self, tags: list) -> list:
        """Tags limitine ve kaliteye dikkat eder. YouTube SEO için optimize edilmiş."""
        must_have = [
            "Evtrix", "Electric Vehicle", "EV", "Electric Car",
            "EV Data", "Battery Technology", "Shorts", "EVShorts",
            "ElectricVehicles", "CleanEnergy"
        ]
        cleaned = []
        for t in must_have:
            cleaned.append(t)

        current_len = sum(len(t) + 2 for t in cleaned)
        for t in tags:
            tag = re.sub(r'[^a-zA-Z0-9\s]', '', str(t)).strip()
            if len(tag) < 2 or tag.lower() in [c.lower() for c in cleaned]:
                continue
            tag = " ".join(tag.split())
            if current_len + len(tag) + 2 < 480:
                cleaned.append(tag)
                current_len += len(tag) + 2
        return cleaned[:45]
