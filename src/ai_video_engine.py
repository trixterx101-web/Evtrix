"""
src/ai_video_engine.py — Evtrix Auto-Studio
===========================================
v8.6 BRAND OPTIMIZED:
  - Updated watermark to 'EVTRIX' for automated animation clips
  - Fixed Pixabay vertical/portrait orientation bug
  - Added micro-movements to FFmpeg fallback animation to maintain retention
"""

import os
import time
import random
import requests
import subprocess
import logging

logger = logging.getLogger("AIVideoGenerator")
OUTPUT_DIR = "assets/ai_clips"
os.makedirs(OUTPUT_DIR, exist_ok=True)

THEMES = {
    "electric": {"bg": "#001833", "acc": "#00D4FF"},
    "green":    {"bg": "#001A00", "acc": "#00FF88"},
    "purple":   {"bg": "#0D001A", "acc": "#CC44FF"},
    "orange":   {"bg": "#1A0800", "acc": "#FF6B00"},
    "gold":     {"bg": "#1A1400", "acc": "#FFD700"},
    "red":      {"bg": "#1A0000", "acc": "#FF3300"},
}

KEYWORD_THEME = {
    "electric": ["electric", "battery", "energy", "charge", "ev", "volt", "lithium"],
    "green":    ["green", "solar", "eco", "sustainable", "clean", "renewable"],
    "purple":   ["ai", "data", "tech", "future", "digital", "smart"],
    "orange":   ["cost", "price", "mining", "heat", "warm"],
    "gold":     ["luxury", "premium", "speed", "performance", "range", "fast"],
    "red":      ["power", "fire", "turbo", "sport", "loss", "danger"],
}

def _pick_theme(prompt: str) -> dict:
    pl = prompt.lower()
    for name, kws in KEYWORD_THEME.items():
        if any(k in pl for k in kws):
            return {**THEMES[name], "name": name}
    return {**THEMES["electric"], "name": "electric"}

def _pick_pexels_query(prompt: str) -> str:
    import re
    clean = prompt.lower()
    clean = re.sub(r'\b(cinematic|slow motion|shot of|abstract|4k|8k|visualization|close up|extreme)\b', '', clean)
    clean = " ".join(clean.split()).strip()
    return clean if clean else "electric vehicle"

def _safe_text(text: str, max_len: int = 20) -> str:
    import re
    text = re.sub(r"[^a-zA-Z0-9 .,!?%-]", "", text)
    return text[:max_len].strip()

class AIVideoGenerator:
    def __init__(self):
        self.pexels_key  = os.getenv("PEXELS_API_KEY")
        self.pixabay_key = os.getenv("PIXABAY_API_KEY")
        self.muapi_key   = os.getenv("MUAPI_KEY")

    def generate_clips(self, prompts: list) -> list:
        clips = []
        for i, prompt in enumerate(prompts):
            logger.info(f"[AIVideo] Sahne {i+1}/{len(prompts)} üretiliyor...")
            path = None

            if i % 2 == 0:
                path = self._pexels(prompt, i)

            if not path:
                path = self._pixabay(prompt, i)

            if not path:
                path = self._pexels(prompt, i)

            if not path:
                logger.info(f"[AIVideo] Animasyon üretiliyor (Sahne {i+1})")
                path = self._ffmpeg_anim(prompt, i)

            if path and self._validate(path):
                clips.append(path)
                logger.info(f"[AIVideo] Sahne {i+1} hazır: {path}")
            else:
                logger.warning(f"[AIVideo] Sahne {i+1} üretilemedi!")

        return clips

    def _pexels(self, prompt: str, idx: int):
        if not self.pexels_key:
            return None
        query = _pick_pexels_query(prompt)
        try:
            headers = {"Authorization": self.pexels_key}
            params  = {"query": query, "per_page": 10, "orientation": "portrait"}
            r = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers, params=params, timeout=15
            )
            if r.status_code != 200:
                logger.warning(f"[Pexels] HTTP {r.status_code} — {query}")
                return None
            videos = r.json().get("videos", [])
            if not videos:
                return None
            random.shuffle(videos)
            for video in videos:
                files = sorted(
                    video.get("video_files", []),
                    key=lambda x: x.get("width", 0), reverse=True
                )
                chosen = next((f for f in files if 720 <= f.get("width", 0) <= 1920), None)
                if not chosen and files:
                    chosen = files[0]
                if not chosen:
                    continue
                url    = chosen.get("link")
                vid_id = video.get("id", idx)
                save   = os.path.join(OUTPUT_DIR, f"pexels_{vid_id}_{idx}.mp4")
                if os.path.exists(save) and os.path.getsize(save) > 50000:
                    logger.info(f"[Pexels] Cache: {save}")
                    return save
                result = self._download(url, save)
                if result:
                    logger.info(f"[Pexels] İndirildi: {save} ({query})")
                    return result
        except Exception as e:
            logger.warning(f"[Pexels] Hata: {e}")
        return None

    def _pixabay(self, prompt: str, idx: int):
        if not self.pixabay_key:
            return None
        query = _pick_pexels_query(prompt)
        try:
            params = {
                "key": self.pixabay_key,
                "q": query,
                "video_type": "film",
                "orientation": "vertical",
                "per_page": 10,
                "safesearch": "true"
            }
            r = requests.get(
                "https://pixabay.com/api/videos/",
                params=params, timeout=15
            )
            if r.status_code != 200:
                return None
            hits = r.json().get("hits", [])
            if not hits:
                return None
            random.shuffle(hits)
            for hit in hits:
                videos = hit.get("videos", {})
                chosen = (videos.get("large") or
                          videos.get("medium") or
                          videos.get("small"))
                if not chosen:
                    continue
                url    = chosen.get("url")
                vid_id = hit.get("id", idx)
                save   = os.path.join(OUTPUT_DIR, f"pixabay_{vid_id}_{idx}.mp4")
                if os.path.exists(save) and os.path.getsize(save) > 50000:
                    logger.info(f"[Pixabay] Cache: {save}")
                    return save
                result = self._download(url, save)
                if result:
                    logger.info(f"[Pixabay] İndirildi: {save} ({query})")
                    return result
        except Exception as e:
            logger.warning(f"[Pixabay] Hata: {e}")
        return None

    def _ffmpeg_anim(self, prompt: str, idx: int):
        out   = os.path.join(OUTPUT_DIR, f"anim_{idx}.mp4")
        theme = _pick_theme(prompt)
        bg    = theme["bg"]
        acc   = theme["acc"]

        words = prompt.upper().split()
        t1  = _safe_text(" ".join(words[:2]), 20) or "ELECTRIC"
        t2  = _safe_text(" ".join(words[2:4]), 20) or "VEHICLE"
        sub = _safe_text(" ".join(words[4:7]), 30) or "EV TECHNOLOGY"

        lines = []
        for i in range(6):
            y     = 300 + i * 250
            alpha = round(0.15 + i * 0.05, 2)
            lines.append(
                f"drawbox=x=0:y={y}:w=iw:h=3:color={acc}@{alpha}:t=fill"
            )

        bars = []
        for i in range(4):
            x     = 100 + i * 230
            h_bar = 200 + i * 80
            y_bar = 800 - i * 40
            bars.append(
                f"drawbox=x={x}:y={y_bar}:w=80:h={h_bar}:color={acc}@0.3:t=fill"
            )

        vf_parts = [
            f"drawbox=x=0:y=0:w=iw:h=ih:color={bg}@1:t=fill",
            *lines,
            *bars,
            f"drawtext=text='{t1}':fontsize=110:fontcolor={acc}:x=(w-tw)/2:y=700-(t*15):shadowcolor=black@0.8:shadowx=4:shadowy=4",
            f"drawtext=text='{t2}':fontsize=110:fontcolor={acc}:x=(w-tw)/2:y=840-(t*15):shadowcolor=black@0.8:shadowx=4:shadowy=4",
            f"drawtext=text='{sub}':fontsize=46:fontcolor=white@0.75:x=(w-tw)/2:y=1010-(t*10)",
            f"drawtext=text='EVTRIX':fontsize=36:fontcolor={acc}@0.5:x=(w-tw)/2:y=1750", # Marka adı EVTRIX olarak güncellendi! ✅
        ]

        vf = ",".join(vf_parts)

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={bg}:size=1080x1920:rate=30",
            "-vf", vf,
            "-t", "5",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-an",
            out
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000:
            return out
        logger.error(f"[FFmpeg] Hata: {result.stderr[-200:]}")
        return None

    def _validate(self, path: str) -> bool:
        if not path or not os.path.exists(path):
            return False
        if os.path.getsize(path) < 5000:
            return False
        return True

    def _download(self, url: str, save_path: str):
        try:
            r = requests.get(url, timeout=60, stream=True)
            if r.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                if os.path.getsize(save_path) > 5000:
                    return save_path
        except Exception as e:
            logger.warning(f"[Download] {e}")
        return None
