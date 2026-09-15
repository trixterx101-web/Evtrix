"""
youtube_cc_source.py — v1.0
YouTube Creative Commons lisanslı videoları indirir.

NEDEİ EN İYİ KATMAN?
  ✅ YOUTUBE_API_KEY zaten sistemde var
  ✅ Telif riski SIFIR (videoLicense=creativeCommon filtresi)
  ✅ HD kalite, konu odaklı, gerçek içerik
  ✅ yt-dlp zaten requirements.txt'te var
  ✅ Pexels/Pixabay'dan çok daha konu-spesifik sonuçlar

KONU HARİTASI (5 ana kategori):
  electric vehicles → "EV charging test", "electric car range"
  artificial intelligence → "AI robot", "machine learning explained"
  robotics → "humanoid robot", "Boston Dynamics"
  battery systems → "battery technology", "solid state battery"
  future technologies → "future tech", "quantum computing"

Kullanım:
  from src.youtube_cc_source import YouTubeCCSource
  src = YouTubeCCSource()
  paths = await src.fetch(topic="electric vehicle battery", count=5)
"""
import os
import re
import json
import random
import logging
import asyncio
import hashlib
import subprocess
from pathlib import Path
from urllib.parse import quote

import requests

logger = logging.getLogger("YouTubeCCSource")

TEMP_DIR    = "assets/temp_videos"
LICENSE_LOG = "license_log.json"
USED_CC_FILE = "used_cc_videos.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EvcarixBot/1.0)"}

# ── Konu → YouTube arama sorguları haritası ──────────────────────────────────
TOPIC_QUERY_MAP = {
    # Elektrikli Araç
    "electric vehicle":      ["electric car range test CC", "EV charging speed test",
                               "electric vehicle technology explained", "electric car review CC"],
    "electric car":          ["electric car driving CC", "EV battery explained CC",
                               "charging electric vehicle tutorial"],
    "battery":               ["battery technology explained CC", "lithium ion battery CC",
                               "solid state battery 2024 CC", "EV battery test CC"],
    "charging":              ["EV charging station CC", "fast charging electric car CC",
                               "home EV charger install CC"],
    "tesla":                 ["electric car future technology CC", "EV technology explained"],

    # Yapay Zeka
    "artificial intelligence": ["artificial intelligence explained CC", "machine learning tutorial CC",
                                  "AI technology 2024 CC", "deep learning explained CC"],
    "ai":                    ["AI robot CC", "artificial intelligence future CC",
                               "neural network explained CC"],
    "machine learning":      ["machine learning tutorial CC", "deep learning CC",
                               "AI explained beginners CC"],

    # Robotik
    "robotics":              ["humanoid robot CC", "industrial robot CC",
                               "robot technology 2024 CC", "AI robot walking CC"],
    "robot":                 ["robot technology explained CC", "automation robotics CC",
                               "robot future CC"],
    "humanoid":              ["humanoid robot CC", "bipedal robot CC",
                               "AI humanoid walking CC"],

    # Batarya Sistemleri
    "battery systems":       ["battery storage technology CC", "lithium battery CC",
                               "energy storage explained CC", "battery manufacturing CC"],
    "solid state":           ["solid state battery CC", "next gen battery CC",
                               "battery breakthrough CC"],

    # Geleceğin Teknolojileri
    "future technology":     ["future technology CC", "tech innovation 2024 CC",
                               "quantum computing explained CC", "smart city technology CC"],
    "smart city":            ["smart city technology CC", "connected city CC",
                               "urban technology CC"],
    "quantum":               ["quantum computing explained CC", "quantum physics CC"],

    # Genel fallback
    "default":               ["electric vehicle CC", "EV technology CC",
                               "clean energy CC", "battery technology CC"],
}

def _log_license(file_path: str, video_id: str, title: str, channel: str):
    """Her indirilen CC videosunu license_log.json'a kaydet."""
    try:
        data = {}
        if os.path.exists(LICENSE_LOG):
            with open(LICENSE_LOG, "r") as f:
                data = json.load(f)
        data[os.path.basename(file_path)] = {
            "source": "YouTube Creative Commons",
            "license": "Creative Commons Attribution (CC-BY)",
            "video_id": video_id,
            "title": title,
            "channel": channel,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "attribution": f'"{title}" by {channel} (youtube.com/watch?v={video_id}) '
                           f'is licensed under Creative Commons Attribution (CC BY).'
        }
        with open(LICENSE_LOG, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"License log failed: {e}")


def _load_used_ids() -> set:
    if os.path.exists(USED_CC_FILE):
        try:
            with open(USED_CC_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def _save_used_id(video_id: str):
    used = _load_used_ids()
    used.add(video_id)
    used_list = list(used)[-500:]  # Son 500 video hatırla
    try:
        with open(USED_CC_FILE, "w") as f:
            json.dump(used_list, f)
    except Exception as e:
        logger.error(f"Used IDs save failed: {e}")


class YouTubeCCSource:
    """
    YouTube Creative Commons lisanslı video kaynağı.
    Tüm indirilen videolar CC-BY lisanslıdır — telif riski sıfır.
    """

    YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self):
        self.api_key  = os.getenv("YOUTUBE_API_KEY")
        self.used_ids = _load_used_ids()
        Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)

    def _get_queries(self, topic: str) -> list[str]:
        """Konuya göre YouTube arama sorguları döndür."""
        topic_lower = topic.lower()
        for key, queries in TOPIC_QUERY_MAP.items():
            if key in topic_lower:
                return queries
        # Fallback: konuyu doğrudan kullan
        base = topic.split()[:3]
        return [
            " ".join(base) + " creative commons",
            " ".join(base) + " CC license",
            " ".join(base) + " explained CC",
            "electric vehicle CC",
        ]

    def search_cc_videos(self, query: str, max_results: int = 15,
                          video_type: str = "short") -> list[dict]:
        """
        YouTube Data API v3 ile CC lisanslı video ara.
        videoLicense=creativeCommon filtresi → sadece CC-BY videolar.
        """
        if not self.api_key:
            logger.info("[YouTubeCC] YOUTUBE_API_KEY bulunamadı, atlanıyor.")
            return []

        # Short videolar için kısa, Long için orta uzunluk
        duration_filter = "short" if video_type == "short" else "medium"

        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "videoLicense": "creativeCommon",   # ← CC filtresi (ANAHTAR)
            "videoDuration": duration_filter,
            "order": "relevance",
            "relevanceLanguage": "en",
            "maxResults": max_results,
            "key": self.api_key,
        }

        try:
            r = requests.get(self.YT_SEARCH_URL, params=params,
                             headers=HEADERS, timeout=15)
            if r.status_code == 403:
                logger.warning("[YouTubeCC] API kota aşıldı veya key geçersiz.")
                return []
            if r.status_code != 200:
                logger.error(f"[YouTubeCC] API hatası: {r.status_code}")
                return []

            results = []
            for item in r.json().get("items", []):
                video_id = item.get("id", {}).get("videoId", "")
                snip     = item.get("snippet", {})
                title    = snip.get("title", "")
                channel  = snip.get("channelTitle", "")

                if not video_id or video_id in self.used_ids:
                    continue
                # Spam / tıklama tuzağı başlıkları filtrele
                if any(w in title.lower() for w in
                       ["compilation", "1 hour", "10 hours", "live stream",
                        "full movie", "full episode"]):
                    continue

                results.append({
                    "video_id": video_id,
                    "title": title,
                    "channel": channel,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "license": "Creative Commons Attribution (CC-BY)",
                })

            logger.info(f"[YouTubeCC] '{query}': {len(results)} CC video bulundu")
            return results

        except Exception as e:
            logger.error(f"[YouTubeCC] Arama hatası: {e}")
            return []

    def _download_with_ytdlp(self, video_id: str, title: str,
                              channel: str, dest_dir: str,
                              video_type: str = "short") -> str | None:
        """
        yt-dlp ile CC videosunu indir.
        Format: en iyi MP4, max 720p (CI hızı için)
        """
        dest = os.path.join(dest_dir, f"ytcc_{video_id}.mp4")
        if os.path.exists(dest) and os.path.getsize(dest) > 100_000:
            logger.info(f"[YouTubeCC] Cache hit: {video_id}")
            return dest

        # CI ortamında 720p, local'de 1080p
        height = "720" if os.getenv("CI") else "1080"

        import shutil
        import sys
        ytdlp_base = ["yt-dlp"] if shutil.which("yt-dlp") else [sys.executable, "-m", "yt_dlp"]

        cmd = ytdlp_base + [
            "--format", f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--output", dest,
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            "--no-check-certificate",
            "--geo-bypass",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "--socket-timeout", "30",
            "--retries", "3",
            f"https://www.youtube.com/watch?v={video_id}",
        ]


        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(dest):
                size_mb = os.path.getsize(dest) / (1024 * 1024)
                if size_mb > 0.5:
                    _log_license(dest, video_id, title, channel)
                    _save_used_id(video_id)
                    self.used_ids.add(video_id)
                    logger.info(f"[YouTubeCC] ✅ İndirildi: {title[:50]} ({size_mb:.1f}MB)")
                    return dest
                else:
                    os.remove(dest)
            else:
                stderr = result.stderr.decode()[:200] if result.stderr else ""
                logger.warning(f"[YouTubeCC] yt-dlp hatası ({video_id}): {stderr}")
        except subprocess.TimeoutExpired:
            logger.warning(f"[YouTubeCC] Timeout: {video_id}")
            if os.path.exists(dest):
                try:
                    os.remove(dest)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"[YouTubeCC] Download exception: {e}")

        return None

    async def fetch(self, topic: str, count: int = 5,
                    video_type: str = "short",
                    dest_dir: str = TEMP_DIR) -> list[str]:
        """
        Ana fonksiyon: CC lisanslı YouTube videolarını indir.

        Args:
            topic: "electric vehicle battery", "AI robotics" vb.
            count: Kaç klip isteniyor
            video_type: "short" | "long"
            dest_dir: Kayıt dizini

        Returns:
            İndirilen dosya yolları listesi
        """
        os.makedirs(dest_dir, exist_ok=True)

        if not self.api_key:
            logger.info("[YouTubeCC] API key yok → atlanıyor (opsiyonel kaynak)")
            return []

        queries = self._get_queries(topic)
        random.shuffle(queries)

        all_videos = []
        seen_ids   = set()

        # Birden fazla sorgu dene — çeşitlilik için
        for query in queries[:3]:
            if len(all_videos) >= count * 2:
                break
            videos = self.search_cc_videos(query, max_results=10,
                                            video_type=video_type)
            for v in videos:
                if v["video_id"] not in seen_ids:
                    seen_ids.add(v["video_id"])
                    all_videos.append(v)

        random.shuffle(all_videos)
        paths = []

        for video in all_videos:
            if len(paths) >= count:
                break
            path = self._download_with_ytdlp(
                video_id  = video["video_id"],
                title     = video["title"],
                channel   = video["channel"],
                dest_dir  = dest_dir,
                video_type= video_type,
            )
            if path:
                paths.append(path)

        logger.info(f"[YouTubeCC] Toplam: {len(paths)}/{count} CC klip (konu: '{topic}')")
        return paths

    def get_attribution_text(self, video_paths: list[str]) -> str:
        """
        Video açıklamasına eklenecek atıf metnini üretir.
        CC-BY lisans gerekliliği: attribution zorunlu.
        """
        try:
            data = {}
            if os.path.exists(LICENSE_LOG):
                with open(LICENSE_LOG, "r") as f:
                    data = json.load(f)

            attributions = []
            for path in video_paths:
                key = os.path.basename(path)
                if key in data and "ytcc" in key:
                    attr = data[key].get("attribution", "")
                    if attr:
                        attributions.append(attr)

            if attributions:
                return "\n\nVideo Credits (CC-BY):\n" + "\n".join(attributions[:5])
        except Exception:
            pass
        return ""
