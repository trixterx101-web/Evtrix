"""
topic_queue.py — Evcarix Akıllı Konu Kuyruğu
============================================
Birden fazla kaynaktan trend konular toplar, izleyici ilgisine göre puanlar
ve topic_queue.json dosyasına sıralar. Her video üretiminde sıradaki konu alınır.

Kaynak önceliği:
  1. YouTube EV Trending (view count bazlı)
  2. EV RSS Haberleri  (Electrek, InsideEVs, CleanTechnica, GreenCarReports)
  3. Reddit EV/Futurology (hot posts)
  4. Google Trends RSS
  5. Arxiv AI/Robotics makaleleri
  6. Core fallback havuzu (WORKING_LOGIC'te tanımlı)
"""
import os
import json
import random
import re
import hashlib
import datetime
import requests
import feedparser

QUEUE_FILE        = "topic_queue.json"
HISTORY_FILE      = "used_topics.json"
HISTORY_LIMIT     = 60          # son 60 konu tekrar edilmez
QUEUE_MIN_SIZE    = 10          # kuyruk bu değerin altına düşerse yeniden doldur
QUEUE_MAX_SIZE    = 30          # kuyrukta en fazla bu kadar konu tutulur

# ── Scoring Ağırlıkları ───────────────────────────────────────────────
SCORE_WEIGHTS = {
    "youtube_trending":  50,    # En yüksek: gerçek izlenme verisi var
    "youtube_ev_search": 40,    # Yüksek: EV aramasında çıkıyor
    "ev_rss":            30,    # Haber kaynağı — güncel
    "reddit_hot":        20,    # Topluluk etkileşimi
    "google_trends":     15,    # Genel trend
    "arxiv":             10,    # Akademik — niş ama kaliteli
    "core_fallback":      5,    # Statik havuz — en düşük öncelik
}

# Viral hook kelimeleri → puan bonusu
VIRAL_KEYWORDS = {
    "secret": 8, "shocking": 8, "nobody": 7, "truth": 7, "lie": 6,
    "real data": 10, "test": 8, "vs": 6, "breakdown": 7, "exposed": 7,
    "cost": 6, "actually": 5, "wrong": 6, "fail": 5, "win": 5,
    "2026": 5, "new": 4, "first": 4, "fastest": 6, "cheapest": 6,
    "record": 7, "breakthrough": 9, "million": 5, "billion": 5,
    "robot": 7, "ai": 6, "humanoid": 8, "tesla": 6, "byd": 5,
    "solid state": 9, "sodium": 8, "silicon": 7, "v2g": 7,
}

# Niş EV / Tech anahtar kelimeleri → konu geçerliliği
EV_KEYWORDS = [
    "ev", "electric", "battery", "charge", "charging", "range", "motor",
    "vehicle", "car", "tesla", "byd", "rivian", "kwh", "volt", "solar",
    "grid", "v2g", "lfp", "nmc", "autonomous", "self-driving", "fsd",
    "lithium", "sodium", "solid-state", "degradation", "efficiency",
    "robot", "robotics", "humanoid", "ai", "artificial intelligence",
    "automation", "gigafactory", "silicon anode", "ultra-fast", "800v",
    "smart city", "smart grid", "wltp", "heat pump", "thermal",
    "optimus", "waymo", "autopilot", "drivetrain", "aerodynamics",
]

BLOCKED = [
    "lamborghini", "ferrari", "bugatti", "hypercar", "supercar", "formula",
    "nascar", "rally", "drift", "prank", "vlog", "challenge", "reaction",
    "cooking", "food", "dance", "sport", "basketball", "football",
    "celebrity", "gossip", "india", "hindi", "rickshaw", "scooter",
]

CORE_FALLBACK = [
    "EV Battery Degradation: LFP vs NMC after 100k Miles — Real Data",
    "Solid-State Battery 2026: Which Company Is Actually Closest?",
    "Tesla vs BYD: Real-World Efficiency Test — Who Wins?",
    "800V vs 400V Charging: Does It Actually Matter?",
    "Vehicle-to-Grid (V2G): How Much Can Your EV Really Earn?",
    "EV Winter Range Loss: Every Major Model Tested in -20°C",
    "Silicon Anode Batteries: Real Performance vs Marketing Claims",
    "How AI Manages Your EV Battery in Real Time — Explained",
    "EV True Cost of Ownership: 5-Year Data Analysis",
    "Humanoid Robots in Gigafactories: Speed & Cost Data",
    "Heat Pump Efficiency in EVs: Real Cold Weather Numbers",
    "DC Fast Charging Impact on Battery Health: Long-Term Study",
    "EV Aerodynamics: How Drag Coefficient Kills Your Range",
    "Sodium-Ion Batteries: Are They Ready to Beat Lithium?",
    "Tesla Optimus vs Reality: What the Data Actually Shows",
    "Self-Driving Levels Explained: L2 vs L3 vs L4 in 2026",
    "Smart Charging Grids: How Cities Handle EV Peak Demand",
    "EV Efficiency: Wh/km Breakdown — Best & Worst Models",
    "Second-Life EV Batteries: Real Economics of Grid Storage",
    "Ultra-Fast Charging 500kW: Physics Limits Explained",
]


# ─────────────────────────────────────────────────────────────────────
class TopicQueue:
    """
    Trend konularını toplar, puanlar, kuyruğa yazar ve sırayla döndürür.
    """

    def __init__(self):
        self._history: list[str] = self._load_history()
        self._queue:   list[dict] = self._load_queue()

    # ── Kalıcı Depolama ───────────────────────────────────────────────
    def _load_history(self) -> list:
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_history(self, topic: str):
        if topic not in self._history:
            self._history.append(topic)
        if len(self._history) > HISTORY_LIMIT:
            self._history = self._history[-HISTORY_LIMIT:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self._history, f, ensure_ascii=False, indent=2)

    def _load_queue(self) -> list:
        if os.path.exists(QUEUE_FILE):
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("queue", [])
            except Exception:
                return []
        return []

    def _save_queue(self):
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.datetime.now().isoformat(),
                "count": len(self._queue),
                "queue": self._queue
            }, f, ensure_ascii=False, indent=2)

    # ── Yardımcı Filtreler ────────────────────────────────────────────
    def _is_relevant(self, text: str) -> bool:
        tl = text.lower()
        if any(b in tl for b in BLOCKED):
            return False
        return any(kw in tl for kw in EV_KEYWORDS)

    def _is_used(self, topic: str) -> bool:
        tl = topic.lower()[:60]
        return any(tl in h.lower() or h.lower()[:60] in tl for h in self._history)

    def _is_in_queue(self, topic: str) -> bool:
        tl = topic.lower()[:60]
        return any(tl in q["topic"].lower() or q["topic"].lower()[:60] in tl
                   for q in self._queue)

    def _topic_hash(self, topic: str) -> str:
        return hashlib.md5(topic.lower().strip().encode()).hexdigest()[:8]

    def _score(self, topic: str, source: str, view_count: int = 0) -> int:
        score = SCORE_WEIGHTS.get(source, 0)
        tl = topic.lower()
        for word, bonus in VIRAL_KEYWORDS.items():
            if word in tl:
                score += bonus
        # View count bonusu (YouTube)
        if view_count > 1_000_000:
            score += 20
        elif view_count > 100_000:
            score += 12
        elif view_count > 10_000:
            score += 6
        return score

    # ── Kaynak: YouTube Trending ──────────────────────────────────────
    def _fetch_youtube_trending(self) -> list[dict]:
        """YouTube'un en çok izlenen videolarını Science&Tech + Autos kategorilerinden çek."""
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return []
        items = []
        # Bölge + Kategori kombinasyonları
        # 28 = Science & Tech | 2 = Autos & Vehicles
        combos = [
            ("US", "28"), ("GB", "28"), ("DE", "28"),
            ("US", "2"),  ("GB", "2"),
        ]
        for region, cat_id in combos:
            try:
                r = requests.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "snippet,statistics",
                        "chart": "mostPopular",
                        "regionCode": region,
                        "videoCategoryId": cat_id,
                        "maxResults": 15,
                        "key": api_key
                    }, timeout=10
                )
                r.raise_for_status()
                for it in r.json().get("items", []):
                    title = it["snippet"].get("title", "")
                    views = int(it.get("statistics", {}).get("viewCount", 0) or 0)
                    if self._is_relevant(title):
                        items.append({"topic": title, "source": "youtube_trending", "view_count": views})
            except Exception as e:
                print(f"[TopicQueue] YouTube trending {region} hata: {e}")
        return items

    # ── Kaynak: YouTube EV Arama ──────────────────────────────────────
    def _fetch_youtube_ev_search(self) -> list[dict]:
        """YouTube'da trend EV/AI aramaları yapıp GERCEK view count ile döndür."""
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return []
        # En çok izlenen EV/AI/Robotics konularını kapsayan geniş sorgu havuzu
        queries = [
            # ⚡ EV Performans & Test
            "electric car real world range test 2026",
            "EV battery degradation long term data",
            "EV vs gas car total cost 2026",
            "800V ultra fast charging real test",
            "best electric car 2026 real test review",
            "EV winter range cold weather test",
            "electric car charging speed comparison 2026",
            # 🔋 Batarya Teknolojisi
            "solid state battery breakthrough 2026",
            "LFP vs NMC battery real world comparison",
            "sodium ion battery vs lithium latest",
            "silicon anode battery real performance",
            "EV battery technology future 2026",
            # 🚗 Marka Karşılaştirmaları
            "Tesla vs BYD efficiency real world test",
            "BYD electric car range test review",
            "Tesla autopilot FSD real world 2026",
            "Rivian vs Tesla comparison data",
            "Hyundai Kia EV real world test",
            # 🤖 AI & Robotics
            "humanoid robot factory 2026 real footage",
            "Tesla Optimus robot update 2026",
            "AI self driving car real world test 2026",
            "autonomous vehicle safety data 2026",
            "Waymo robotaxi real experience 2026",
            # 💡 Gelecek Teknoloji
            "vehicle to grid V2G real world test",
            "wireless EV charging real test",
            "EV charging infrastructure 2026 update",
            "electric truck real world range payload test",
            "EV depreciation data 2026 real numbers",
        ]
        items = []
        # Her çalışmada rastgele 6 sorgu seç (API kotayı koru)
        selected_queries = random.sample(queries, min(6, len(queries)))
        for query in selected_queries:
            try:
                # Adım 1: Arama yap
                search_r = requests.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "part": "snippet",
                        "q": query,
                        "type": "video",
                        "order": "viewCount",
                        "relevanceLanguage": "en",
                        "maxResults": 8,
                        "publishedAfter": "2024-01-01T00:00:00Z",
                        "key": api_key
                    }, timeout=10
                )
                search_r.raise_for_status()
                search_items = search_r.json().get("items", [])
                video_ids = [it["id"]["videoId"] for it in search_items if it["id"].get("videoId")]
                if not video_ids:
                    continue

                # Adım 2: Gerçek view count'ı çek
                stats_r = requests.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "snippet,statistics",
                        "id": ",".join(video_ids),
                        "key": api_key
                    }, timeout=10
                )
                stats_r.raise_for_status()
                for it in stats_r.json().get("items", []):
                    title = it["snippet"].get("title", "")
                    views = int(it.get("statistics", {}).get("viewCount", 0) or 0)
                    if self._is_relevant(title):
                        items.append({
                            "topic": title,
                            "source": "youtube_ev_search",
                            "view_count": views
                        })
            except Exception as e:
                print(f"[TopicQueue] YouTube EV search hata ({query[:35]}): {e}")
        # View count'a göre sırala (en çok izlenen öne çıksın)
        items.sort(key=lambda x: x["view_count"], reverse=True)
        print(f"[TopicQueue] YouTube EV search: {len(items)} trend konu toplandı")
        return items

    # ── Kaynak: EV RSS Haber Akışları ────────────────────────────────
    def _fetch_ev_rss(self) -> list[dict]:
        feeds = [
            "https://electrek.co/feed/",
            "https://insideevs.com/rss/articles/all/",
            "https://cleantechnica.com/feed/",
            "https://www.greencarreports.com/rss/news",
            "https://www.teslarati.com/feed/",
            "https://www.motortrend.com/feeds/electric-vehicles/",
        ]
        items = []
        for url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:6]:
                    title = entry.get("title", "").strip()
                    if title and self._is_relevant(title):
                        items.append({"topic": title, "source": "ev_rss", "view_count": 0})
            except Exception as e:
                print(f"[TopicQueue] RSS hata ({url[:40]}): {e}")
        return items

    # ── Kaynak: Reddit Hot Posts ──────────────────────────────────────
    def _fetch_reddit(self) -> list[dict]:
        subreddits = ["ElectricVehicles", "teslamotors", "Futurology", "technology", "artificial"]
        items = []
        for sub in subreddits:
            try:
                feed = feedparser.parse(f"https://www.reddit.com/r/{sub}/hot/.rss?limit=15")
                for entry in feed.entries[:5]:
                    title = re.sub(r'^[A-Z]{2,4}[: ]+', '', entry.get("title", "")).strip()
                    if title and self._is_relevant(title):
                        items.append({"topic": title[:150], "source": "reddit_hot", "view_count": 0})
            except Exception as e:
                print(f"[TopicQueue] Reddit r/{sub} hata: {e}")
        return items

    # ── Kaynak: Google Trends RSS ─────────────────────────────────────
    def _fetch_google_trends(self) -> list[dict]:
        items = []
        for region in ["US", "GB"]:
            try:
                feed = feedparser.parse(
                    f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={region}")
                for entry in feed.entries[:8]:
                    title = entry.get("title", "").strip()
                    if title and self._is_relevant(title):
                        items.append({"topic": title, "source": "google_trends", "view_count": 0})
            except Exception as e:
                print(f"[TopicQueue] Google Trends {region} hata: {e}")
        return items

    # ── Kaynak: Arxiv AI/Robotics ─────────────────────────────────────
    def _fetch_arxiv(self) -> list[dict]:
        feeds = [
            "https://rss.arxiv.org/rss/cs.AI",
            "https://rss.arxiv.org/rss/cs.RO",
        ]
        items = []
        for url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    title = entry.get("title", "").strip()
                    if title and self._is_relevant(title):
                        items.append({"topic": title[:120], "source": "arxiv", "view_count": 0})
            except Exception as e:
                print(f"[TopicQueue] Arxiv hata: {e}")
        return items

    # ── Kuyruğu Doldur ───────────────────────────────────────────────
    def refresh(self, force: bool = False) -> int:
        """
        Tüm kaynaklardan konu toplar, puanlar ve kuyruğa ekler.
        force=True → mevcut kuyruk temizlenir ve sıfırdan doldurulur.
        FORCE_FRESH_TREND env varı da force=True gibi davranır.
        """
        # FORCE_FRESH_TREND: manuel tetiklemede her zaman taze trend verisi al
        if os.getenv("FORCE_FRESH_TREND", "").lower() == "true":
            force = True
            print("[TopicQueue] 🔥 FORCE_FRESH_TREND aktif — kuyruk temizlenip yenileniyor...", flush=True)

        if force:
            self._queue = []
            print("[TopicQueue] 🔄 Kuyruk temizlendi.", flush=True)

        if not force and len(self._queue) >= QUEUE_MIN_SIZE:
            print(f"[TopicQueue] Kuyrukta {len(self._queue)} konu var, yenileme gerekmez.")
            return len(self._queue)

        print("[TopicQueue] 🔄 Kaynaklardan konu toplanıyor...", flush=True)

        raw: list[dict] = []
        raw += self._fetch_youtube_trending()
        raw += self._fetch_youtube_ev_search()  # ⭐ Güncel view count ile
        raw += self._fetch_ev_rss()
        raw += self._fetch_reddit()
        raw += self._fetch_google_trends()
        raw += self._fetch_arxiv()

        # Core fallback her zaman eklenir (en düşük öncelik)
        for t in CORE_FALLBACK:
            raw.append({"topic": t, "source": "core_fallback", "view_count": 0})

        # Puanla + filtrele + deduplicate
        seen_hashes = set()
        scored = []
        for item in raw:
            topic = item["topic"].strip()
            if not topic:
                continue
            h = self._topic_hash(topic)
            if h in seen_hashes:
                continue
            if self._is_used(topic):
                continue
            if self._is_in_queue(topic):
                continue
            seen_hashes.add(h)
            score = self._score(topic, item["source"], item.get("view_count", 0))
            scored.append({
                "topic":      topic,
                "source":     item["source"],
                "score":      score,
                "view_count": item.get("view_count", 0),
                "added_at":   datetime.datetime.now().isoformat(),
            })

        # Yüksek puanlıdan düşüğe sırala
        scored.sort(key=lambda x: x["score"], reverse=True)

        # Kuyruğa ekle (üst sınıra kadar)
        added = 0
        for item in scored:
            if len(self._queue) >= QUEUE_MAX_SIZE:
                break
            self._queue.append(item)
            added += 1

        self._save_queue()
        print(f"[TopicQueue] ✅ {added} yeni konu eklendi → Toplam: {len(self._queue)}", flush=True)

        # En yüksek puanlı 5 konuyu logla
        print("[TopicQueue] 🏆 TOP 5 TREND KONU:", flush=True)
        for i, item in enumerate(self._queue[:5], 1):
            views_str = f"{item['view_count']:,}" if item['view_count'] else "?"
            print(f"  [{i}] ({item['score']}p) 👁 {views_str} views [{item['source']}] {item['topic'][:70]}")

        return len(self._queue)

    # ── Sıradaki Konuyu Al ────────────────────────────────────────────
    def pop_next(self) -> dict | None:
        """
        Kuyruktaki en yüksek puanlı konuyu çıkarır ve döndürür.
        Kuyruk boşsa None döner.
        """
        # Kuyruk azsa otomatik yenile
        if len(self._queue) < QUEUE_MIN_SIZE:
            self.refresh()

        if not self._queue:
            return None

        # Kuyruk zaten score'a göre sıralı, ilkini al
        item = self._queue.pop(0)
        self._save_history(item["topic"])
        self._save_queue()

        print(f"[TopicQueue] 📌 Seçilen konu: ({item['score']}p) [{item['source']}] {item['topic'][:70]}")
        return item

    # ── Kuyruk Durumu ─────────────────────────────────────────────────
    def status(self) -> dict:
        return {
            "queue_size":    len(self._queue),
            "history_size":  len(self._history),
            "top_topics":    [
                {"rank": i+1, "score": q["score"], "source": q["source"], "topic": q["topic"][:80]}
                for i, q in enumerate(self._queue[:10])
            ]
        }


# ── CLI: python -m src.topic_queue ──────────────────────────────────
if __name__ == "__main__":
    import sys
    q = TopicQueue()
    if "--refresh" in sys.argv:
        q.refresh(force=True)
    elif "--status" in sys.argv:
        st = q.status()
        print(f"\n📊 Kuyruk: {st['queue_size']} konu | Geçmiş: {st['history_size']} konu")
        for t in st["top_topics"]:
            print(f"  [{t['rank']}] ({t['score']}p) [{t['source']}] {t['topic']}")
    elif "--pop" in sys.argv:
        item = q.pop_next()
        print(f"\nSeçilen: {item}")
    else:
        print("Kullanım: python -m src.topic_queue [--refresh | --status | --pop]")
