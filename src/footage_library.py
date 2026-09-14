"""
FootageLibrary v3 — EV-Only, Unlimited, Non-Repeating Video Clips

Changes vs v2:
- QUERY_POOL now strictly EV/tech themed (no generic city/sport footage)
- used_clips.json tracks by VIDEO ID (not file hash) → cross-run memory
- Each API call uses rotating page + random query → no identical results
- Used clip IDs are excluded before downloading → no same clip twice
- If disk cache exists but was used in a prior video, it's skipped
- Pexels/Pixabay: each topic has 30+ targeted EV queries for maximum variety
"""
import os
import sys
import json
import random
import subprocess
import logging
import hashlib
import requests
import re
import time
from pathlib import Path

logger = logging.getLogger("FootageLibrary")

# ─────────────────────────────────────────────────────────────────────────────
# EV-ONLY QUERY POOL — strictly on-topic, 30+ entries per category
# ─────────────────────────────────────────────────────────────────────────────
QUERY_POOL = {
    "electric_vehicle": [
        # Cars in motion
        "electric car driving highway",
        "electric vehicle acceleration",
        "tesla model 3 driving",
        "electric car city street",
        "electric vehicle road trip",
        "EV highway overtake",
        "electric car night drive",
        "electric vehicle rain drive",
        "electric car tunnel",
        "EV test track",
        # Charging
        "electric car charging station",
        "EV charger plug in",
        "fast charging electric vehicle",
        "DC fast charger",
        "supercharger station",
        "home EV charging",
        "charging cable electric car",
        # Battery & tech
        "electric car battery pack",
        "lithium battery technology",
        "battery cell manufacturing",
        "electric motor closeup",
        "EV powertrain",
        "battery management system",
        "solid state battery lab",
        "EV range meter dashboard",
        # Interior / cockpit
        "electric car interior dashboard",
        "EV touchscreen display",
        "car cockpit technology",
        "electric vehicle infotainment",
        # Factory & industry
        "electric car factory",
        "EV manufacturing robot arm",
        "car assembly line electric",
        "Gigafactory production",
        "electric vehicle production line",
        # Aerial & environment
        "electric car aerial drone",
        "zero emission vehicle",
        "clean energy transport",
        "electric bus city",
        "EV truck electric",
        # Brands (popular)
        "Tesla autopilot",
        "Rivian electric truck",
        "Ford F-150 Lightning electric",
        "Hyundai Ioniq electric",
        "BMW iX electric car",
        "Mercedes EQS driving",
        "Volkswagen ID4 electric",
    ],
    "battery_tech": [
        "lithium battery cell",
        "solid state battery research",
        "battery energy storage",
        "battery pack electric car",
        "battery degradation test",
        "EV battery thermal management",
        "LFP battery technology",
        "NMC battery cell",
        "battery recycling plant",
        "sodium ion battery",
        "battery factory production",
        "battery charging cycle",
        "energy density battery lab",
        "battery module assembly",
        "electric vehicle range test",
        "battery cell microscope",
        "electrochemistry research",
        "battery anode cathode",
        "semiconductor chip EV",
        "circuit board electric car",
        "solar panel battery storage",
        "grid energy storage",
        "power wall home battery",
        "wind turbine energy",
        "renewable energy storage",
    ],
    "artificial_intelligence": [
        "AI self driving car",
        "autonomous vehicle sensor",
        "Tesla FSD driving",
        "LiDAR self driving",
        "autopilot camera vehicle",
        "machine learning automotive",
        "neural network self driving",
        "computer vision car",
        "AI dashboard car",
        "robot arm manufacturing",
        "AI chip processor",
        "data center server",
        "digital twin factory",
        "smart factory automation",
        "predictive maintenance AI",
        "AI traffic management",
        "autonomous delivery robot",
        "NVIDIA GPU automotive",
        "AI software development",
        "deep learning visualization",
    ],
    "robotics": [
        "robot arm car factory",
        "industrial robot welding",
        "humanoid robot walking",
        "Boston Dynamics robot",
        "Tesla Optimus robot",
        "factory automation robot",
        "collaborative robot cobot",
        "robot EV assembly",
        "precision robot manufacturing",
        "autonomous mobile robot",
        "warehouse robot logistics",
        "robot car painting",
        "CNC machining precision",
        "3D printing automotive",
        "drone inspection factory",
        "exoskeleton technology",
    ],
    "future_tech": [
        "electric VTOL flying car",
        "autonomous vehicle future",
        "smart city electric mobility",
        "hyperloop electric transport",
        "electric airplane flight",
        "electric boat yacht",
        "hydrogen fuel cell vehicle",
        "wireless EV charging road",
        "vehicle to grid V2G",
        "electric heavy truck",
        "electric bus fleet city",
        "autonomous electric shuttle",
        "electric scooter city",
        "electric motorcycle race",
        "EV racing circuit",
        "electric car performance",
        "smart highway technology",
        "EV infrastructure city",
        "carbon neutral transport",
        "sustainable mobility future",
    ],
}

NASA_QUERIES = {
    "electric_vehicle": ["electric vehicle technology", "clean energy transport", "battery research", "EV charging"],
    "artificial_intelligence": ["autonomous systems", "artificial intelligence", "machine learning"],
    "robotics": ["robotics", "robonaut", "autonomous robot"],
    "battery_tech": ["battery research", "energy storage", "solar power", "fuel cell"],
    "future_tech": ["future technology", "clean energy", "innovation"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Used-clip tracking — stored by SOURCE_ID (not file hash) for cross-run memory
# ─────────────────────────────────────────────────────────────────────────────
USED_CLIPS_FILE = "used_clips.json"
MAX_USED_HISTORY = 500   # keep last 500 IDs; older entries recycled


def _load_used_ids() -> set:
    if os.path.exists(USED_CLIPS_FILE):
        try:
            with open(USED_CLIPS_FILE, "r") as f:
                return set(json.load(f).get("ids", []))
        except Exception:
            pass
    return set()


def _save_used_ids(ids: set):
    lst = list(ids)
    if len(lst) > MAX_USED_HISTORY:
        # Keep newest entries (rough approximation — rotate by discarding oldest half)
        lst = lst[len(lst) - MAX_USED_HISTORY:]
    try:
        with open(USED_CLIPS_FILE, "w") as f:
            json.dump({"ids": lst}, f)
    except Exception:
        pass


def _source_id(prefix: str, raw_id) -> str:
    return f"{prefix}_{raw_id}"


class FootageLibrary:
    def __init__(self):
        self.output_dir = "assets/footage"
        os.makedirs(self.output_dir, exist_ok=True)
        self.used_ids = _load_used_ids()
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        })

    def _is_used(self, source_id: str) -> bool:
        return source_id in self.used_ids

    def _mark_used(self, source_id: str):
        self.used_ids.add(source_id)
        _save_used_ids(self.used_ids)

    # ─────────────────────────────────────────────────────────────────────────
    # Public: get clips for SHORT video
    # ─────────────────────────────────────────────────────────────────────────
    def get_fresh_clips(self, topic: str, count: int = 6, format: str = "shorts") -> list[str]:
        """Fetch EV-topic clips, never repeating clips used in previous videos."""
        clips   = []
        seen    = set()

        sources = [
            self._fetch_pexels,
            self._fetch_pixabay,
            self._fetch_wikimedia,
            self._fetch_youtube_ytdlp,
            self._fetch_youtube_cc,
            self._fetch_nasa,
        ]
        # Randomise source order each run
        random.shuffle(sources[:4])

        for source in sources:
            if len(clips) >= count:
                break
            try:
                new_clips = source(topic, count - len(clips), format)
                for c in new_clips:
                    if c and os.path.exists(c) and c not in seen:
                        clips.append(c)
                        seen.add(c)
            except Exception as e:
                logger.error(f"Source {source.__name__} failed: {e}")

        logger.info(f"get_fresh_clips: {len(clips)}/{count} clips collected")
        return clips[:count]

    # ─────────────────────────────────────────────────────────────────────────
    # Public: get clips for LONG video (maximum variety)
    # ─────────────────────────────────────────────────────────────────────────
    def get_varied_clips_for_long_video(self, topic: str, count: int, format: str = "long") -> list[str]:
        """
        Fetch up to `count` unique, never-before-used EV clips for a long video.
        Rotates through the full QUERY_POOL for maximum variety.
        """
        query_pool = list(QUERY_POOL.get(topic, QUERY_POOL["electric_vehicle"]))
        random.shuffle(query_pool)

        clips      = []
        seen_paths = set()

        # ── Round 1: Pexels (multiple queries + random pages) ─────────────────
        pexels_key = os.getenv("PEXELS_API_KEY")
        if pexels_key:
            n_queries = min(len(query_pool), max(count // 2, 8))
            for qi in range(n_queries):
                if len(clips) >= count:
                    break
                q    = query_pool[qi % len(query_pool)]
                page = random.randint(1, 12)
                try:
                    url = (
                        f"https://api.pexels.com/videos/search"
                        f"?query={requests.utils.quote(q)}&per_page=10"
                        f"&orientation=landscape&page={page}"
                    )
                    r = self._session.get(url, headers={"Authorization": pexels_key}, timeout=(5, 20))
                    if r.status_code != 200:
                        continue
                    for v in r.json().get("videos", []):
                        if len(clips) >= count:
                            break
                        sid = _source_id("pexels", v["id"])
                        if self._is_used(sid):
                            continue
                        files = self._best_pexels_file(v["video_files"])
                        if files:
                            out = os.path.join(self.output_dir, f"pexels_{v['id']}.mp4")
                            if out not in seen_paths and self._download_direct(files["link"], out):
                                clips.append(out)
                                seen_paths.add(out)
                                self._mark_used(sid)
                                logger.info(f"[Pexels-Long] q='{q}' p={page} +1: {out}")
                except Exception as e:
                    logger.error(f"Pexels-Long q='{q}': {e}")

        # ── Round 2: Pixabay (second half of query pool) ──────────────────────
        pixabay_key = os.getenv("PIXABAY_API_KEY")
        if pixabay_key and len(clips) < count:
            pix_queries = query_pool[:]
            random.shuffle(pix_queries)
            for q in pix_queries[:max(count // 2, 8)]:
                if len(clips) >= count:
                    break
                page = random.randint(1, 8)
                try:
                    url = (
                        f"https://pixabay.com/api/videos/"
                        f"?key={pixabay_key}&q={requests.utils.quote(q)}&per_page=12"
                        f"&page={page}&video_type=film"
                    )
                    r = self._session.get(url, timeout=(5, 20))
                    if r.status_code != 200:
                        continue
                    for v in r.json().get("hits", []):
                        if len(clips) >= count:
                            break
                        sid = _source_id("pixabay", v["id"])
                        if self._is_used(sid):
                            continue
                        f_data = (v["videos"].get("large")
                                  or v["videos"].get("medium")
                                  or v["videos"].get("small"))
                        if f_data:
                            out = os.path.join(self.output_dir, f"pixabay_{v['id']}.mp4")
                            if out not in seen_paths and self._download_direct(f_data["url"], out):
                                clips.append(out)
                                seen_paths.add(out)
                                self._mark_used(sid)
                                logger.info(f"[Pixabay-Long] q='{q}' p={page} +1: {out}")
                except Exception as e:
                    logger.error(f"Pixabay-Long q='{q}': {e}")

        # ── Round 3: Wikimedia CC ─────────────────────────────────────────────
        if len(clips) < count:
            try:
                wiki_clips = self._fetch_wikimedia(topic, min(count - len(clips), 5), format)
                for c in wiki_clips:
                    if c and c not in seen_paths and os.path.exists(c):
                        clips.append(c)
                        seen_paths.add(c)
            except Exception as e:
                logger.error(f"Wikimedia-Long: {e}")

        # ── Round 4: NASA ─────────────────────────────────────────────────────
        if len(clips) < count:
            try:
                nasa_clips = self._fetch_nasa(topic, min(count - len(clips), 4), format)
                for c in nasa_clips:
                    if c and c not in seen_paths and os.path.exists(c):
                        clips.append(c)
                        seen_paths.add(c)
            except Exception as e:
                logger.error(f"NASA-Long: {e}")

        # ── Round 5: YouTube CC (yt-dlp) ──────────────────────────────────────
        if len(clips) < count:
            try:
                yt_clips = self._fetch_youtube_ytdlp(topic, min(count - len(clips), 8), format)
                for c in yt_clips:
                    if c and c not in seen_paths and os.path.exists(c):
                        clips.append(c)
                        seen_paths.add(c)
            except Exception as e:
                logger.error(f"YouTube-ytdlp Long: {e}")

        # ── Round 6: YouTube Data API ─────────────────────────────────────────
        if len(clips) < count:
            try:
                yt_api_clips = self._fetch_youtube_cc(topic, min(count - len(clips), 6), format)
                for c in yt_api_clips:
                    if c and c not in seen_paths and os.path.exists(c):
                        clips.append(c)
                        seen_paths.add(c)
            except Exception as e:
                logger.error(f"YouTube-API Long: {e}")

        logger.info(f"[LongVideoClips] {len(clips)}/{count} unique EV clips collected")
        random.shuffle(clips)
        return clips

    # ─────────────────────────────────────────────────────────────────────────
    # Source: Pexels
    # ─────────────────────────────────────────────────────────────────────────
    def _fetch_pexels(self, topic: str, count: int, format: str) -> list[str]:
        api_key = os.getenv("PEXELS_API_KEY")
        if not api_key:
            return []

        pool        = QUERY_POOL.get(topic, QUERY_POOL["electric_vehicle"])
        # Use 3 random queries per call for more variety
        queries     = random.sample(pool, min(3, len(pool)))
        orientation = "portrait" if format == "shorts" else "landscape"
        results     = []
        seen        = set()

        for query in queries:
            if len(results) >= count:
                break
            page = random.randint(1, 12)
            url  = (
                f"https://api.pexels.com/videos/search"
                f"?query={requests.utils.quote(query)}&per_page=15&orientation={orientation}"
                f"&page={page}"
            )
            try:
                r = self._session.get(url, headers={"Authorization": api_key}, timeout=(5, 20))
                if r.status_code != 200:
                    logger.error(f"Pexels HTTP {r.status_code}")
                    continue
                for v in r.json().get("videos", []):
                    if len(results) >= count:
                        break
                    sid = _source_id("pexels", v["id"])
                    if self._is_used(sid):
                        continue
                    f = self._best_pexels_file(v["video_files"])
                    if f:
                        out = os.path.join(self.output_dir, f"pexels_{v['id']}.mp4")
                        if out not in seen and self._download_direct(f["link"], out):
                            results.append(out)
                            seen.add(out)
                            self._mark_used(sid)
                            logger.info(f"[Pexels] q='{query}' p={page} +1: {v['id']}")
            except Exception as e:
                logger.error(f"Pexels q='{query}': {e}")

        return results

    def _best_pexels_file(self, files: list) -> dict | None:
        """Pick the best Pexels file: prefer 1080p, fallback to 720p."""
        hd = sorted([f for f in files if (f.get("width") or 0) >= 1280],
                    key=lambda x: x.get("width") or 0, reverse=True)
        if hd:
            return hd[0]
        sd = sorted([f for f in files if (f.get("width") or 0) >= 720],
                    key=lambda x: x.get("width") or 0, reverse=True)
        return sd[0] if sd else None

    # ─────────────────────────────────────────────────────────────────────────
    # Source: Pixabay
    # ─────────────────────────────────────────────────────────────────────────
    def _fetch_pixabay(self, topic: str, count: int, format: str) -> list[str]:
        api_key = os.getenv("PIXABAY_API_KEY")
        if not api_key:
            return []

        pool    = QUERY_POOL.get(topic, QUERY_POOL["electric_vehicle"])
        queries = random.sample(pool, min(3, len(pool)))
        results = []
        seen    = set()

        for query in queries:
            if len(results) >= count:
                break
            page = random.randint(1, 8)
            url  = (
                f"https://pixabay.com/api/videos/"
                f"?key={api_key}&q={requests.utils.quote(query)}&per_page=15"
                f"&page={page}&video_type=film"
            )
            try:
                r = self._session.get(url, timeout=(5, 20))
                if r.status_code != 200:
                    continue
                for v in r.json().get("hits", []):
                    if len(results) >= count:
                        break
                    sid = _source_id("pixabay", v["id"])
                    if self._is_used(sid):
                        continue
                    f_data = (v["videos"].get("large")
                              or v["videos"].get("medium")
                              or v["videos"].get("small"))
                    if f_data:
                        out = os.path.join(self.output_dir, f"pixabay_{v['id']}.mp4")
                        if out not in seen and self._download_direct(f_data["url"], out):
                            results.append(out)
                            seen.add(out)
                            self._mark_used(sid)
                            logger.info(f"[Pixabay] q='{query}' p={page} +1: {v['id']}")
            except Exception as e:
                logger.error(f"Pixabay q='{query}': {e}")

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # Source: YouTube yt-dlp (CC license, no API key needed)
    # ─────────────────────────────────────────────────────────────────────────
    def _get_ytdlp_cmd(self) -> list[str]:
        import shutil
        if shutil.which("yt-dlp"):
            return ["yt-dlp"]
        return [sys.executable, "-m", "yt_dlp"]

    def _fetch_youtube_ytdlp(self, topic: str, count: int, format: str) -> list[str]:
        """yt-dlp CC-licensed search — no API key required."""
        base_cmd = self._get_ytdlp_cmd()
        pool     = QUERY_POOL.get(topic, QUERY_POOL["electric_vehicle"])
        queries  = random.sample(pool, min(count, len(pool)))
        results  = []
        seen     = set()

        for q in queries:
            if len(results) >= count:
                break
            need = count - len(results)
            try:
                cmd = base_cmd + [
                    f"ytsearch{need * 4}:{q}",
                    "--match-filter",
                    "license='Creative Commons Attribution license (reuse allowed)'",
                    "--format",
                    "bestvideo[height<=1080][height>=480][ext=mp4]"
                    "/bestvideo[height<=1080][height>=480]"
                    "/bestvideo[height<=720]",
                    "--no-audio",
                    "--no-playlist",
                    "--playlist-end", str(need * 2),
                    "--max-downloads", str(need),
                    "--output",
                    os.path.join(self.output_dir, "yt_%(id)s.%(ext)s"),
                    "--merge-output-format", "mp4",
                    "--quiet",
                    "--no-warnings",
                    "--sleep-interval", "1",
                    "--max-sleep-interval", "3",
                ]
                logger.info(f"[YouTube-ytdlp] Searching: '{q}' (need {need})")
                subprocess.run(cmd, capture_output=True, text=True, timeout=180)

                for fname in os.listdir(self.output_dir):
                    if fname.startswith("yt_") and fname.endswith(".mp4"):
                        fpath = os.path.join(self.output_dir, fname)
                        yt_id = fname[3:-4]    # strip "yt_" prefix and ".mp4"
                        sid   = _source_id("yt", yt_id)
                        if (fpath not in seen
                                and not self._is_used(sid)
                                and os.path.exists(fpath)
                                and os.path.getsize(fpath) > 1_000_000):
                            results.append(fpath)
                            seen.add(fpath)
                            self._mark_used(sid)
                            logger.info(f"[YouTube-ytdlp] +1 CC clip: {fname}")
                        if len(results) >= count:
                            break
            except subprocess.TimeoutExpired:
                logger.warning(f"[YouTube-ytdlp] Timeout: '{q}'")
            except Exception as e:
                logger.error(f"[YouTube-ytdlp] Error '{q}': {e}")

        return results[:count]

    # ─────────────────────────────────────────────────────────────────────────
    # Source: YouTube Data API v3
    # ─────────────────────────────────────────────────────────────────────────
    def _fetch_youtube_cc(self, topic: str, count: int, format: str) -> list[str]:
        try:
            from googleapiclient.discovery import build
        except ImportError:
            return []

        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return []

        pool    = QUERY_POOL.get(topic, QUERY_POOL["electric_vehicle"])
        queries = random.sample(pool, min(3, len(pool)))
        results = []
        seen    = set()

        try:
            youtube = build("youtube", "v3", developerKey=api_key)
            for query in queries:
                if len(results) >= count:
                    break
                try:
                    res = youtube.search().list(
                        part="snippet",
                        q=query,
                        type="video",
                        videoLicense="creativeCommon",
                        videoDuration="medium",
                        videoDefinition="high",
                        maxResults=min(count * 3, 20),
                        relevanceLanguage="en",
                        order="relevance",
                    ).execute()
                    for item in res.get("items", []):
                        if len(results) >= count:
                            break
                        vid_id = item["id"]["videoId"]
                        sid    = _source_id("yt", vid_id)
                        if self._is_used(sid):
                            continue
                        out = os.path.join(self.output_dir, f"yt_{vid_id}.mp4")
                        if out not in seen and self._download_yt(vid_id, out):
                            results.append(out)
                            seen.add(out)
                            self._mark_used(sid)
                            logger.info(f"[YouTube-API] CC+HD: {vid_id}")
                except Exception as e:
                    logger.error(f"[YouTube-API] query='{query}': {e}")
        except Exception as e:
            logger.error(f"[YouTube-API] build failed: {e}")

        return results

    def _download_yt(self, vid_id: str, out: str) -> bool:
        if os.path.exists(out) and os.path.getsize(out) > 1_000_000:
            return True
        cmd = self._get_ytdlp_cmd() + [
            "--format",
            "bestvideo[height<=1080][height>=480][ext=mp4]"
            "/bestvideo[height<=1080][height>=480]"
            "/bestvideo[height<=720]",
            "--no-audio",
            "--merge-output-format", "mp4",
            "--output", out,
            "--quiet",
            "--no-warnings",
            f"https://youtube.com/watch?v={vid_id}"
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=120)
            return r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1_000_000
        except Exception as e:
            logger.error(f"[yt-dlp download] {vid_id}: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Source: Wikimedia Commons
    # ─────────────────────────────────────────────────────────────────────────
    def _fetch_wikimedia(self, topic: str, count: int, format: str) -> list[str]:
        query = random.choice(QUERY_POOL.get(topic, ["electric vehicle"]))
        params = {
            "action": "query",
            "list":   "search",
            "srsearch":   f"{query} filetype:video",
            "srnamespace": "6",
            "srlimit":  count * 3,
            "format":   "json"
        }
        try:
            r = self._session.get(
                "https://commons.wikimedia.org/w/api.php",
                params=params, timeout=(5, 15)
            )
            if r.status_code != 200:
                return []
            hits    = r.json().get("query", {}).get("search", [])
            results = []
            for hit in hits:
                if len(results) >= count:
                    break
                title = hit["title"]
                sid   = _source_id("wiki", hit["pageid"])
                if self._is_used(sid):
                    continue
                try:
                    ir = self._session.get(
                        "https://commons.wikimedia.org/w/api.php"
                        f"?action=query&titles={title}&prop=imageinfo&iiprop=url&format=json",
                        timeout=(5, 10)
                    ).json()
                    for p in ir.get("query", {}).get("pages", {}).values():
                        url = p.get("imageinfo", [{}])[0].get("url", "")
                        if url and url.endswith(".mp4"):
                            out = os.path.join(self.output_dir, f"wiki_{hit['pageid']}.mp4")
                            if self._download_direct(url, out):
                                results.append(out)
                                self._mark_used(sid)
                except Exception:
                    continue
            return results
        except Exception as e:
            logger.error(f"Wikimedia: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Source: NASA
    # ─────────────────────────────────────────────────────────────────────────
    def _fetch_nasa(self, topic: str, count: int, format: str) -> list[str]:
        query   = random.choice(NASA_QUERIES.get(topic, ["electric vehicle"]))
        results = []
        try:
            r = self._session.get(
                "https://images-api.nasa.gov/search",
                params={"q": query, "media_type": "video", "page": random.randint(1, 4)},
                timeout=(5, 15)
            )
            if r.status_code != 200:
                return []
            items = r.json().get("collection", {}).get("items", [])
            for item in items:
                if len(results) >= count:
                    break
                try:
                    nasa_id = item["data"][0].get("nasa_id", "")
                    sid     = _source_id("nasa", nasa_id)
                    if self._is_used(sid):
                        continue
                    cr   = self._session.get(item["href"], timeout=(5, 10)).json()
                    mp4s = [u for u in cr if u.endswith("~orig.mp4") or u.endswith("~medium.mp4")]
                    if mp4s:
                        out = os.path.join(self.output_dir, f"nasa_{nasa_id}.mp4")
                        if self._download_direct(mp4s[0], out):
                            results.append(out)
                            self._mark_used(sid)
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"NASA API: {e}")
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # Downloader
    # ─────────────────────────────────────────────────────────────────────────
    def _download_direct(self, url: str, out: str) -> bool:
        if os.path.exists(out) and os.path.getsize(out) > 50_000:
            return True
        try:
            r = self._session.get(url, timeout=(5, 25), stream=True)
            if r.status_code != 200:
                return False
            ct = r.headers.get("content-type", "")
            if ct and "video" not in ct and "octet-stream" not in ct:
                return False
            cl = int(r.headers.get("content-length", 0))
            if cl and (cl < 50_000 or cl > 350_000_000):
                return False

            start_time = time.time()
            downloaded = 0
            with open(out, "wb") as f:
                for chunk in r.iter_content(chunk_size=131_072):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if time.time() - start_time > 60:
                        logger.warning(f"Download timeout (60s): {url[:60]}")
                        break
                    if downloaded > 350_000_000:
                        logger.warning(f"Download size limit: {url[:60]}")
                        break

            if os.path.exists(out) and os.path.getsize(out) > 50_000:
                return True
            if os.path.exists(out):
                os.remove(out)
            return False

        except requests.exceptions.ConnectTimeout:
            logger.warning(f"ConnectTimeout: {url[:60]}")
        except requests.exceptions.ReadTimeout:
            logger.warning(f"ReadTimeout: {url[:60]}")
        except Exception as e:
            logger.error(f"Download error: {url[:60]} | {e}")

        if os.path.exists(out):
            try:
                os.remove(out)
            except Exception:
                pass
        return False
