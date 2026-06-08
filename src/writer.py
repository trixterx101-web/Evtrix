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

    # Farklı açılış hook'ları — her video farklı başlasın (YouTube benzer başlangıcı spam sayıyor)
    import random
    HOOK_STARTERS = [
        "Here's a number that will change how you see {topic}:",
        "Most people have no idea that {topic} works like this:",
        "The data on {topic} is more shocking than anyone admits.",
        "Nobody talks about this {topic} fact, but the numbers don't lie.",
        "We ran the real numbers on {topic}. The results surprised even us.",
        "If you own or plan to buy an EV, this {topic} data matters to you.",
        "Quick question: do you actually know the real cost of {topic}?",
        "Stop scrolling. This {topic} number will stick with you.",
    ]
    hook = random.choice(HOOK_STARTERS).replace("{topic}", topic)

    if is_long:
        tone = (
            "Style: No hype. Just numbers. Fact-first. Language: MANDATORY US ENGLISH. "
            "CRITICAL RULE: NEVER use 'Welcome to', 'Hello', 'Hey', 'In this video'. "
            f"Start IMMEDIATELY with this hook sentence: '{hook}' then follow with a shocking statistic. "
            "MID-VIDEO RULE: At the halfway point, add a 'pattern interrupt' — say something like "
            "'But here's where it gets really interesting...' or 'Wait — this next number changes everything.' "
            "This keeps viewers watching past the midpoint (critical for watch time). "
            "END with a direct engagement CTA: 'What surprised you most? Drop it in the comments below.' "
            "Then: 'Subscribe to Evtrix — new EV data every week. Hit the bell so you never miss it.'"
        )
        prompt = (
            f"Write a professional {duration_s}-second deep-dive EV script (~{words} words) about: {topic}.\n"
            f"{tone}\n"
            "Structure:\n"
            "1. HOOK (0-15s): Start with the provided hook + one shocking statistic.\n"
            "2. DATA ANALYSIS (15s-50%): 3-4 key data points with global examples (USA, Europe, China).\n"
            "3. PATTERN INTERRUPT (midpoint): Re-engage viewer with a surprising twist or reframe.\n"
            "4. EXPERT INSIGHT (50%-85%): What experts/industry leaders say. Specific quotes or reports.\n"
            "5. CONCLUSION + CTA (last 15%): Verdict + comment question + subscribe ask.\n"
            "CRITICAL: Every sentence needs a number, %, $, kWh, or km value. No vague statements.\n"
            "CRITICAL: US ENGLISH ONLY. Global perspective.\n"
            "Output ONLY the script text."
        )
    else:
        tone = (
            "Style: No hype. Just numbers. Fact-first. Language: MANDATORY US ENGLISH. "
            "CRITICAL RULE: NEVER use 'Welcome to', 'In this video', 'Hello', 'Hey', 'Hi'. "
            f"Start IMMEDIATELY with this hook: '{hook}' "
            "Use specific percentages, kWh values, and real-world data. "
            "At the 60% mark, add ONE curiosity bridge line like 'But the real number is even more surprising...' "
            "This prevents viewers from swiping away early. "
            "End with a direct engagement line: 'Comment your thoughts below.' "
            "Then: 'Subscribe to Evtrix for real EV data.'"
        )
        prompt = (
            f"Write a viral {duration_s}-second YouTube Shorts script (~{words} words) about: {topic}.\n"
            f"{tone}\n"
            "Structure: Hook stat -> 2-3 data points -> Curiosity bridge -> Final verdict -> CTA.\n"
            "Use specific numbers (%, $, miles, kWh). USA, Europe, China examples.\n"
            "CRITICAL: US ENGLISH ONLY. Zero filler words. Every sentence = one data point.\n"
            "Output ONLY the script text."
        )

    script = _llm_chain(prompt, fallback=f"{hook} The data on {topic} reveals trends most EV owners never see. Subscribe to Evtrix for more.")
    return {"script": script, "voice": "male" if is_long else "female"}


class CreativeWriter:
    def generate_short_content(self, topic: str):
        meta = generate_seo_metadata(topic, is_long=False)
        script_data = generate_script(topic, duration_s=52, is_long=False)

        final_tags = self._clean_tags(meta.get("tags", ["ev", "ai", "tech"]))

        chosen_title = random.choice([meta.get('title_a'), meta.get('title_b')])
        if not chosen_title:
            chosen_title = meta.get('title', topic)

        hashtag_tags = [f"#{t.replace(' ', '')}" for t in final_tags[:10]]
        if "#Shorts" not in hashtag_tags:
            hashtag_tags.insert(0, "#Shorts")
        if "#EVShorts" not in hashtag_tags:
            hashtag_tags.insert(1, "#EVShorts")

        seo_desc   = meta.get('seo_description', f'Exploring the latest data and trends behind {topic}.')
        hook_a     = meta.get('hook_a', 'Shocking EV data.')
        hook_b     = meta.get('hook_b', 'Real numbers, real impact.')
        keywords   = meta.get('keywords', [topic, 'electric vehicle', 'EV data'])
        kw_str     = ', '.join(keywords[:8]) if keywords else topic

        desc = (
            f"⚡ {hook_a}\n\n"
            f"{seo_desc}\n\n"
            f"In this short, Evtrix breaks down the real numbers behind {topic} — "
            f"no opinion, no hype, just verified data from global industry reports. "
            f"Whether you're an EV owner, considering your first electric vehicle, or just following "
            f"clean energy trends, this data directly impacts your decisions.\n\n"
            f"💡 {hook_b}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 WHAT YOU'LL LEARN\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"— The key stats and numbers on {topic}\n"
            f"— How this compares across USA, Europe & China\n"
            f"— What this means for EV buyers in 2025-2026\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 ABOUT EVTRIX\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Evtrix is an independent EV data channel covering electric vehicles, battery technology, "
            f"autonomous driving, and the future of clean transport. "
            f"We publish data-driven content every week — no sponsored bias, no hype.\n\n"
            f"❓ What surprised you most about {topic}? Comment below — we read every reply.\n\n"
            f"🔍 Keywords: {kw_str}\n\n"
            f"{' '.join(hashtag_tags)}\n\n"
            f"---\n"
            f"{STOCK_DISCLAIMER}"
        )

        return {
            "title": chosen_title,
            "script": script_data["script"],
            "voice": script_data["voice"],
            "tags": final_tags,
            "description": desc,
            "category": "short",
            "category_id": "28"
        }

    def generate_long_content(self, topic: str, duration_s: int = 540):
        meta = generate_seo_metadata(topic, is_long=True)
        script_data = generate_script(topic, duration_s=duration_s, is_long=True)

        final_tags = self._clean_tags(meta.get("tags", []))

        # Estimate chapters based on duration
        intro_end        = "0:00"
        analysis_start   = "1:00"
        insight_start    = f"{duration_s // 60 // 2}:{(duration_s // 2) % 60:02d}"
        conclusion_start = f"{(duration_s - 60) // 60}:{(duration_s - 60) % 60:02d}"

        hashtag_tags = [f"#{t.replace(' ', '')}" for t in final_tags[:12]]

        seo_desc   = meta.get('seo_description', f'A deep-dive data analysis of {topic} by Evtrix.')
        hook_a     = meta.get('hook_a', 'Expert EV analysis.')
        hook_b     = meta.get('hook_b', 'Real numbers, real impact.')
        keywords   = meta.get('keywords', [topic, 'electric vehicle', 'EV data'])
        kw_str     = ', '.join(keywords[:10]) if keywords else topic

        desc = (
            f"🚀 {hook_a}\n\n"
            f"{seo_desc}\n\n"
            f"In this deep-dive, Evtrix breaks down the real data behind {topic}. "
            f"We analyze verified numbers from global EV industry reports, manufacturer data, "
            f"and independent research — covering markets in the USA, Europe, and China. "
            f"If you're an EV enthusiast, buyer, or investor, this analysis gives you the edge "
            f"most YouTube channels won't touch.\n\n"
            f"💡 {hook_b}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱️ CHAPTERS\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{intro_end} — Hook & Shocking Data Point\n"
            f"{analysis_start} — Deep Data Analysis\n"
            f"{insight_start} — Industry Expert Insight\n"
            f"{conclusion_start} — Final Verdict & What It Means for You\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 WHAT'S COVERED IN THIS VIDEO\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"— Industry-leading EV data & real-world performance analysis on {topic}\n"
            f"— Technical specifications compared across major EV brands (Tesla, BYD, Rivian, Hyundai, VW)\n"
            f"— Market trends in the US, EU, and Chinese EV markets (2024-2026 data)\n"
            f"— Future impact: what the {topic} trend means for EV buyers & investors\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 ABOUT EVTRIX\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Evtrix is an independent EV data and analysis channel. We cover electric vehicles, "
            f"battery technology, autonomous driving systems, EV charging infrastructure, and the "
            f"future of sustainable transport. Our content is 100% data-driven — no sponsored "
            f"opinions, no manufacturer bias. Subscribe for new analysis every week.\n\n"
            f"❓ What surprised you most about {topic}? Drop your take in the comments — we reply to everyone.\n\n"
            f"🔍 Keywords: {kw_str}\n\n"
            f"{' '.join(hashtag_tags)}\n\n"
            f"---\n"
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
            "category_id": "28"
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
