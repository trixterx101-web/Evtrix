import os
import json
import random
import datetime
import pandas as pd
from src.trend_engine import TrendEngine
from src.writer import CreativeWriter

try:
    from src.content_discovery import ContentDiscovery
    _discovery = ContentDiscovery()
except Exception as e:
    print(f"[Brain] ContentDiscovery yüklenemedi: {e}")
    _discovery = None

HISTORY_FILE = "used_topics.json"
HISTORY_LIMIT = 100

MANUAL_MODE_TOPICS = {
    "electric vehicles":      ["Future of electric vehicles", "EV adoption trends", "Electric car technology 2026", "Best electric vehicles 2026"],
    "artificial intelligence":["AI in electric vehicles", "Machine learning for EVs", "AI autonomous driving", "Neural networks in cars"],
    "robotics":               ["Robot electric vehicles", "Autonomous EV robots", "Future robotics transport", "Self-driving robot cars"],
    "new technologies":       ["New EV technology 2026", "Future car innovations", "Next gen electric vehicles", "EV tech breakthroughs"],
    "battery systems":        ["EV battery technology", "Solid state battery EVs", "Battery range improvement", "Lithium battery future"],
    "smart cities":           ["Smart city EV charging", "Urban electric transport", "City EV infrastructure", "Smart grid electric cars"],
    "devices of the future":  ["Future EV devices", "Next gen car technology", "Smart EV gadgets 2026", "Electric vehicle innovation"],
}

# ── Profesyonel başlık formülleri ─────────────────────────────
TITLE_FORMULAS = [
    "Nobody Is Talking About This {topic} Secret in 2026",
    "Your {topic} Is Lying to You — Here's the Real Data",
    "I Tested {topic} for 30 Days — The Results Are Shocking",
    "Why Every {topic} Expert Is Wrong About This",
    "The {topic} Truth They Don't Want You to Know",
    "{topic}: The 2026 Data That Changes Everything",
    "Warning: What {topic} Really Costs in 2026",
    "This {topic} Mistake Is Costing You Thousands",
    "The Real Reason {topic} Is Better Than You Think",
    "What Happens When You Push {topic} to Its Limit",
    "{topic} vs Reality: We Ran the Numbers",
    "Why {topic} Will Look Different in 12 Months",
    "The {topic} Breakdown Nobody Shows You",
    "Is {topic} Worth It? 2026 Data Answers",
    "We Ranked Every {topic} — The Winner Shocked Us",
]

# ── Konu → Anahtar kelime eşleştirmesi ───────────────────────
TOPIC_KEYWORDS = {
    "battery":          ["EV Battery", "Battery Pack", "Battery Tech"],
    "charge":           ["EV Charging", "Fast Charging", "Charging Speed"],
    "range":            ["EV Range", "Range Loss", "Real Range"],
    "winter":           ["Winter EV", "Cold Weather", "Winter Range"],
    "heat pump":        ["Heat Pump", "EV Heating", "Winter Efficiency"],
    "lfp":              ["LFP Battery", "LFP vs NMC", "Iron Battery"],
    "solid state":      ["Solid State Battery", "Next Gen Battery", "Future Battery"],
    "tesla":            ["Tesla", "Tesla Model", "Tesla vs"],
    "byd":              ["BYD", "BYD vs Tesla", "Chinese EV"],
    "autonomous":       ["Self Driving", "Autonomous EV", "FSD"],
    "motor":            ["EV Motor", "Electric Motor", "Motor Tech"],
    "v2g":              ["V2G Charging", "Bi-Directional", "Vehicle to Grid"],
    "thermal":          ["Thermal Management", "Battery Cooling", "EV Heat"],
    "degradation":      ["Battery Degradation", "Battery Health", "Cell Aging"],
    "400v":             ["400V vs 800V", "Charging Architecture", "Voltage System"],
    "800v":             ["800V EV", "Ultra Fast Charging", "High Voltage EV"],
    "ai":               ["AI in EV", "Machine Learning", "Neural Network"],
    "robot":            ["Robotics", "Autonomous Robot", "EV Robot"],
    "future":           ["Future Tech", "EV Future", "Next Gen EV"],
    "cost":             ["EV Cost", "EV Price", "Total Cost"],
    "efficiency":       ["EV Efficiency", "Energy Use", "Real MPGe"],
}


def _improve_title_with_gemini(topic: str, raw_title: str) -> str:
    """
    Gemini ile başlığı profesyonel formüle göre iyileştir.
    raw_title zayıfsa Gemini yeniden üretir.
    """
    try:
        import google.generativeai as genai

        keys = [k for k in [
            os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_API_KEY_2"),
            os.getenv("GEMINI_API_KEY_3"),
            os.getenv("GEMINI_API_KEY_4"),
            os.getenv("GEMINI_API_KEY_5"),
        ] if k]

        if not keys:
            return raw_title

        prompt = f"""You are a YouTube title expert for the channel "Evtrix" — the #1 EV data channel. Topics: EVs, AI, Battery Tech, Robotics, Future Technology.

Topic: {topic}
Current title: {raw_title}

Generate ONE viral YouTube title following these rules:
1. Maximum 70 characters
2. Creates curiosity or shock
3. Contains a specific number, fact, or question when possible
4. No clickbait lies — must be relevant to topic
5. English only. US/Europe/Global perspective.
6. Use one of these proven formulas:
   - "Nobody Is Talking About [X] — But They Should Be"
   - "I Tested [X] for 30 Days — The Results Are Shocking"
   - "Why [X] Will Change Everything in 2026"
   - "The [X] Truth That Nobody Shows You"
   - "[Number]% of EV Owners Don't Know This About [X]"
   - "Warning: What [X] Really Costs in 2026"
   - "[X] vs Reality: We Ran the Numbers"

Return ONLY the title. No quotes. No explanation."""

        # Tüm key'leri dene, quota aşılırsa sıradakine geç
        response = None
        for key in keys:
            try:
                genai.configure(api_key=key)
                model    = genai.GenerativeModel("gemini-2.0-flash-lite")
                response = model.generate_content(prompt)
                break  # Başarılıysa dur
            except Exception as key_err:
                err_str = str(key_err)
                if "429" in err_str or "quota" in err_str.lower():
                    print(f"[Brain] Key kota aşıldı, sıradaki deneniyor...")
                    continue
                raise key_err

        if not response:
            return raw_title

        new_title = response.text.strip().strip('"').strip("'")

        # Kalite kontrolü
        if len(new_title) < 20 or len(new_title) > 100:
            return raw_title
        if new_title.lower() == raw_title.lower():
            return raw_title

        print(f"[Brain] 📝 Başlık iyileştirildi: {new_title}")
        return new_title

    except Exception as e:
        print(f"[Brain] Başlık iyileştirme hatası: {e}")
        return raw_title


def _generate_fallback_title(topic: str) -> str:
    """Gemini olmadan formül tabanlı güçlü başlık üret."""
    topic_lower = topic.lower()

    # Konu kelimesiyle eşleş
    keyword = topic
    for k, v in TOPIC_KEYWORDS.items():
        if k in topic_lower:
            keyword = random.choice(v)
            break

    formula = random.choice(TITLE_FORMULAS)
    title = formula.replace("{topic}", keyword)
    return title


def _validate_title(title: str) -> bool:
    """Başlığın kalite standartlarını karşılayıp karşılamadığını kontrol et."""
    if not title:
        return False
    if len(title) < 15:
        return False
    if len(title) > 100:
        return False

    # Zayıf başlık kalıpları
    weak_patterns = [
        "ev tech:", "ev future:", "ev data:", "evtrix:", "evcarix:",
        "short:", "video:", "daily:", "update:"
    ]
    title_lower = title.lower()
    for pattern in weak_patterns:
        if title_lower.startswith(pattern):
            return False

    return True


class EvcarixBrain:
    def __init__(self):
        self.trend_engine = TrendEngine()
        self.writer = CreativeWriter()

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_history(self, topic):
        history = self._load_history()
        history.append(topic)
        if len(history) > HISTORY_LIMIT:
            history = history[-HISTORY_LIMIT:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def select_strategic_topic(self, video_type="short"):
        content_mode = os.getenv("CONTENT_MODE", "auto").strip().lower()
        print(f"[Brain] Content Mode: {content_mode}")

        # ── 1. Trend Modu ─────────────────────────────────────────
        if content_mode == "trend" and video_type == "short":
            try:
                trend_plan = self.trend_engine.trigger_from_youtube_trend(hours_back=48)
                if trend_plan:
                    print(f"[Brain] 🔥 Trend modu aktif: {trend_plan['title']}")
                    return trend_plan['full_topic'], trend_plan
                else:
                    print("[Brain] ⚠️ Trend bulunamadı, auto moda geçiliyor.")
            except Exception as e:
                print(f"[Brain] Trend hatası: {e}")

        # ── 2. ContentDiscovery Modları ───────────────────────────
        discovery_modes = ["educational", "scientific", "ev_news"]
        if content_mode in discovery_modes and _discovery:
            try:
                topics = _discovery.discover(strategy=content_mode, limit=10)
                if topics:
                    chosen = random.choice(topics)
                    topic_title = chosen.get("title", "Future of Electric Vehicles")
                    print(f"[Brain] 🔍 ContentDiscovery ({content_mode}): {topic_title[:60]}")
                    print(f"        Kaynak: {chosen.get('source', '?')}")
                    _discovery.mark_used(topic_title)
                    return topic_title, None
                else:
                    print(f"[Brain] ⚠️ ContentDiscovery ({content_mode}) boş döndü, auto moda geçiliyor.")
            except Exception as e:
                print(f"[Brain] ContentDiscovery hatası: {e}")

        # ── 3. Manuel Konu Modları ────────────────────────────────
        if content_mode in MANUAL_MODE_TOPICS:
            topic_list = MANUAL_MODE_TOPICS[content_mode]
            history = self._load_history()
            unused = [t for t in topic_list if t not in history]
            topic = random.choice(unused if unused else topic_list)
            print(f"[Brain] 🎯 Manuel mod ({content_mode}): {topic}")
            return topic, None

        # ── 4. Sıralı Havuz (Auto/Default) ───────────────────────
        try:
            csv_path = os.path.join("data", "topics.csv")
            if not os.path.exists(csv_path):
                print(f"[Brain] ❌ {csv_path} bulunamadı!")
                return "Future of Electric Vehicles", None

            df = pd.read_csv(csv_path, on_bad_lines='skip')
            if df.empty:
                return "Future of Electric Vehicles", None

            state_file = "sequential_state.json"
            state = {"next_index": 0}
            if os.path.exists(state_file):
                try:
                    with open(state_file, "r") as f:
                        state = json.load(f)
                except Exception as e:
                    print(f"[Brain] State okuma hatası: {e}")

            idx = state.get("next_index", 0)
            if idx >= len(df):
                print(f"[Brain] 🔄 Liste sonu ({len(df)}), başa dönülüyor.")
                idx = 0

            # ── EV-Only Niş Filtresi ──────────────────────────────
            EV_KEYWORDS = {
                "ev", "electric", "battery", "charge", "charging", "range",
                "motor", "vehicle", "car", "tesla", "byd", "rivian",
                "kwh", "volt", "solar", "grid", "v2g", "lfp", "nmc",
                "autonomous", "self-driving", "fsd", "drivetrain",
                "lithium", "sodium", "solid-state", "degradation",
                "efficiency", "consumption", "aerodynamic", "drag",
                "infrastructure", "supercharger", "ccs", "chademo",
                "heat pump", "thermal", "cooling", "warranty",
                "maintenance", "depreciation", "cost", "price",
                "market", "sales", "adoption", "gigafactory",
            }
            max_skip = min(10, len(df))
            skipped = 0
            topic = "Future of Electric Vehicles"
            category = "general"
            while skipped < max_skip:
                row = df.iloc[idx % len(df)]
                candidate = row['topic']
                if any(kw in candidate.lower() for kw in EV_KEYWORDS):
                    topic = candidate
                    category = row.get('category_id', 'general')
                    break
                print(f"[Brain] ⏭️ Niş-dışı konu atlandı: {candidate}")
                idx += 1
                skipped += 1

            state["next_index"] = idx + 1
            with open(state_file, "w") as f:
                json.dump(state, f)

            print(f"[Brain] 🔄 Sıralı seçim: [{idx+1}/{len(df)}] ({category}) -> {topic}")
            return topic, None

        except Exception as e:
            import traceback
            print(f"[Brain] ❌ Sıralı seçim hatası: {e}")
            traceback.print_exc()
            return "Future of Electric Vehicles", None

    def create_daily_plan(self, slot="evening", video_type="short"):
        topic, trend_plan = self.select_strategic_topic(video_type)

        if trend_plan:
            self._save_history(topic)
            trend_plan['video_type'] = video_type

            # Trend başlığını da iyileştir
            raw_title = trend_plan.get('title', topic)
            if not _validate_title(raw_title):
                trend_plan['title'] = _generate_fallback_title(topic)
            else:
                trend_plan['title'] = _improve_title_with_gemini(topic, raw_title)

            return trend_plan

        if video_type == "long":
            print(f"[Brain] Haftalık Uzun Video üretiliyor: {topic}")
            content = self.writer.generate_long_content(topic)
        else:
            print(f"[Brain] Günlük Shorts üretiliyor: {topic}")
            content = self.writer.generate_short_content(topic)

        self._save_history(topic)

        # ── Başlık Kalite Kontrol & İyileştirme ──────────────────
        raw_title = content.get('title', topic)
        print(f"[Brain] 📋 Ham başlık: {raw_title}")

        if not _validate_title(raw_title):
            # Zayıf başlık → formül tabanlı yeniden üret
            print(f"[Brain] ⚠️ Zayıf başlık tespit edildi, yeniden üretiliyor...")
            improved_title = _generate_fallback_title(topic)
        else:
            # İyi başlık → Gemini ile daha da iyileştir
            improved_title = _improve_title_with_gemini(topic, raw_title)

        content['title'] = improved_title
        print(f"[Brain] ✅ Final başlık: {improved_title}")

        tags = content.get('tags', [])
        if len(tags) > 30:
            tags = tags[:30]

        return {
            "topic":       topic,
            "full_topic":  topic,
            "script":      content['script'],
            "title":       content['title'],
            "description": content['description'],
            "tags":        tags,
            "voice":       content.get('voice', "female"),
            "category":    content.get('category', 'general'),
            "video_type":  video_type,
        }
