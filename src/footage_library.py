import os
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

QUERY_POOL = {
    "electric_vehicle": [
        "electric car", "EV charging", "electric vehicle review",
        "tesla review", "electric car test drive", "EV range test",
        "highway driving", "night driving rain", "city traffic timelapse",
        "car dashboard interior", "road trip sunset", "tunnel driving",
        "car engine technology", "automotive engineering", "motor test",
        "charging cable plug", "battery pack", "power grid",
        "renewable energy car", "zero emission vehicle", "clean transport",
        "electric motor spinning", "drive test circuit", "acceleration test",
        "empty highway aerial", "city street cars", "parking lot cars",
        "traffic light intersection", "motorway timelapse", "car headlights night"
    ],
    "artificial_intelligence": [
        "machine learning explained", "AI technology demo",
        "neural network visualization", "data science tutorial",
        "computer screen code", "server room data center",
        "programmer coding", "software development",
        "digital screen technology", "futuristic interface",
        "binary code", "algorithm visualization",
        "typing keyboard closeup", "multiple monitors setup",
        "tech startup office", "innovation lab",
        "brain scan neuroscience", "network connections",
        "cloud computing", "cybersecurity"
    ],
    "robotics": [
        "robot technology", "industrial robot arm",
        "humanoid robot", "automation factory",
        "factory assembly line", "manufacturing plant",
        "welding sparks factory", "car manufacturing robot",
        "precision engineering", "CNC machine",
        "3D printer working", "laboratory technology",
        "mechanical engineering", "gear mechanism",
        "drone flying", "autonomous vehicle sensor"
    ],
    "battery_tech": [
        "battery technology", "solid state battery",
        "lithium battery", "energy storage",
        "solar panel installation", "wind turbine farm",
        "power plant aerial", "electricity grid",
        "laboratory chemistry", "scientific research",
        "mineral mining aerial", "semiconductor factory",
        "circuit board closeup", "electronic component",
        "energy cell microscope", "charging device"
    ],
    "future_tech": [
        "future technology", "innovation lab",
        "smart city", "space technology",
        "city aerial night lights", "skyscraper timelapse",
        "satellite orbit earth", "space station",
        "quantum physics lab", "particle accelerator",
        "nanotechnology research", "biotech laboratory",
        "augmented reality demo", "VR headset technology",
        "hyperloop concept", "autonomous drone fleet",
        "underwater technology", "deep sea research"
    ]
}

NASA_QUERIES = {
    "electric_vehicle": ["electric vehicle technology", "clean energy transport", "battery research"],
    "artificial_intelligence": ["artificial intelligence", "machine learning space", "autonomous systems"],
    "robotics": ["robotics", "robonaut", "autonomous robot", "mars rover"],
    "battery_tech": ["battery research", "energy storage", "solar power", "fuel cell"],
    "future_tech": ["future technology", "space exploration", "innovation", "orbital"],
}

ARCHIVE_COLLECTIONS = [
    "prelinger", "computersandtech", "nasa", "prelinger_auxiliary",
    "ephemera", "open_source_movies", "stock_footage", "Transportation",
    "SciFi_Horror", "feature_films"
]

# Gerçek çalışan NASA / DOE URL'leri
NASA_REAL_URLS = [
    "https://www.energy.gov/sites/default/files/2022-07/ev-charging-broll.mp4",
    "https://archive.org/download/gov.archives.arc.1257628/gov.archives.arc.1257628.mp4",
    "https://archive.org/download/gov.archives.arc.49442/gov.archives.arc.49442.mp4",
]


class FootageLibrary:
    def __init__(self):
        self.output_dir = "assets/footage"
        os.makedirs(self.output_dir, exist_ok=True)
        self.used_clips_file = "used_clips.json"
        self.used_ids = self._load_used()
        # Session ile connection pool kullan
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        })

    def _load_used(self) -> set:
        if os.path.exists(self.used_clips_file):
            try:
                with open(self.used_clips_file, "r") as f:
                    return set(json.load(f).get("ids", []))
            except:
                pass
        return set()

    def _mark_used(self, file_path: str):
        try:
            with open(file_path, "rb") as f:
                clip_id = hashlib.md5(f.read(8192)).hexdigest()
            self.used_ids.add(clip_id)
            with open(self.used_clips_file, "w") as f:
                json.dump({"ids": list(self.used_ids)}, f)
        except:
            pass

    def get_fresh_clips(self, topic: str, count: int = 1, format: str = "shorts") -> list[str]:
        """Shorts için tek query ile klip çek."""
        clips = []

        sources = [
            self._fetch_pexels,
            self._fetch_pixabay,
            self._fetch_wikimedia,
            self._fetch_coverr,
            self._fetch_nasa,
        ]
        random.shuffle(sources[:4])

        for source in sources:
            if len(clips) >= count:
                break
            try:
                new_clips = source(topic, count - len(clips), format)
                for c in new_clips:
                    if c and os.path.exists(c) and c not in clips:
                        clips.append(c)
                        self._mark_used(c)
                        logger.info(f"[{source.__name__}] +1 klip: {c}")
            except Exception as e:
                logger.error(f"Source {source.__name__} failed: {e}")

        logger.info(f"get_fresh_clips: {len(clips)}/{count} klip toplandı")
        return clips[:count]

    def get_varied_clips_for_long_video(self, topic: str, count: int, format: str = "long") -> list[str]:
        """
        Uzun video için maksimum çeşitlilik:
        - QUERY_POOL'daki her sorgu en fazla 1-2 kez kullanılır
        - Her kaynak farklı sayfa ve sorgu ile çağrılır
        - Duplicate klip olmaz (path bazlı dedup)
        - Hedef: count kadar FARKLI klip
        """
        query_pool = list(QUERY_POOL.get(topic, QUERY_POOL["electric_vehicle"]))
        random.shuffle(query_pool)

        clips = []
        seen_paths = set()
        query_idx = 0

        # 1. Tur: Pexels — birden fazla farklı sorgu + farklı sayfalar
        pexels_key = os.getenv("PEXELS_API_KEY")
        if pexels_key:
            for qi in range(min(len(query_pool), max(count // 3, 4))):
                if len(clips) >= count:
                    break
                q = query_pool[qi % len(query_pool)]
                page = random.randint(1, 8)
                try:
                    url = (
                        f"https://api.pexels.com/videos/search"
                        f"?query={requests.utils.quote(q)}&per_page=8"
                        f"&orientation=landscape&page={page}"
                    )
                    r = self._session.get(url, headers={"Authorization": pexels_key}, timeout=(5, 20))
                    if r.status_code == 200:
                        for v in r.json().get("videos", []):
                            if len(clips) >= count:
                                break
                            files = sorted(
                                [f for f in v["video_files"]
                                 if (f.get("width") or 0) >= 1280],
                                key=lambda x: (x.get("width") or 0)
                            )
                            if not files:
                                files = sorted(
                                    [f for f in v["video_files"]
                                     if (f.get("width") or 0) >= 720],
                                    key=lambda x: (x.get("width") or 0)
                                )
                            if files:
                                out = os.path.join(self.output_dir, f"pexels_{v['id']}.mp4")
                                if out not in seen_paths and self._download_direct(files[0]["link"], out):
                                    clips.append(out)
                                    seen_paths.add(out)
                                    self._mark_used(out)
                                    logger.info(f"[Pexels-Long] q='{q}' p={page} +1: {out}")
                except Exception as e:
                    logger.error(f"Pexels-Long q='{q}': {e}")

        # 2. Tur: Pixabay — farklı sorgu seti
        pixabay_key = os.getenv("PIXABAY_API_KEY")
        if pixabay_key and len(clips) < count:
            pix_queries = query_pool[len(query_pool)//2:]  # İkinci yarı sorgular
            random.shuffle(pix_queries)
            for q in pix_queries[:max(count // 3, 4)]:
                if len(clips) >= count:
                    break
                page = random.randint(1, 6)
                try:
                    url = (
                        f"https://pixabay.com/api/videos/"
                        f"?key={pixabay_key}&q={requests.utils.quote(q)}&per_page=10"
                        f"&page={page}&video_type=film"
                    )
                    r = self._session.get(url, timeout=(5, 20))
                    if r.status_code == 200:
                        for v in r.json().get("hits", []):
                            if len(clips) >= count:
                                break
                            f_data = (v["videos"].get("large")
                                      or v["videos"].get("medium")
                                      or v["videos"].get("small"))
                            if f_data:
                                out = os.path.join(self.output_dir, f"pixabay_{v['id']}.mp4")
                                if out not in seen_paths and self._download_direct(f_data["url"], out):
                                    clips.append(out)
                                    seen_paths.add(out)
                                    self._mark_used(out)
                                    logger.info(f"[Pixabay-Long] q='{q}' p={page} +1: {out}")
                except Exception as e:
                    logger.error(f"Pixabay-Long q='{q}': {e}")

        # 3. Tur: Wikimedia CC (ek çeşitlilik için)
        if len(clips) < count:
            try:
                wiki_clips = self._fetch_wikimedia(topic, min(count - len(clips), 5), format)
                for c in wiki_clips:
                    if c and c not in seen_paths and os.path.exists(c):
                        clips.append(c)
                        seen_paths.add(c)
            except Exception as e:
                logger.error(f"Wikimedia-Long: {e}")

        # 4. Tur: NASA (en sonda, çok az klip var)
        if len(clips) < count:
            try:
                nasa_clips = self._fetch_nasa(topic, min(count - len(clips), 3), format)
                for c in nasa_clips:
                    if c and c not in seen_paths and os.path.exists(c):
                        clips.append(c)
                        seen_paths.add(c)
            except Exception as e:
                logger.error(f"NASA-Long: {e}")

        logger.info(f"[LongVideoClips] {len(clips)}/{count} FARKLI klip toplandı")
        # Sonuçları karıştır — aynı konunun klipleri art arda gelmesin
        random.shuffle(clips)
        return clips

    def _fetch_youtube_cc(self, topic: str, count: int, format: str) -> list[str]:
        """Creative Commons YouTube videoları — sadece YOUTUBE_API_KEY varsa çalışır."""
        try:
            from googleapiclient.discovery import build
        except ImportError:
            return []
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return []

        queries = QUERY_POOL.get(topic, QUERY_POOL["future_tech"])
        query = random.choice(queries)

        try:
            youtube = build("youtube", "v3", developerKey=api_key)
            request = youtube.search().list(
                part="snippet", q=query, type="video",
                videoLicense="creativeCommon", videoDuration="short",
                maxResults=count * 3
            )
            res = request.execute()
            results = []
            for item in res.get("items", []):
                vid_id = item["id"]["videoId"]
                out = os.path.join(self.output_dir, f"yt_{vid_id}.mp4")
                if self._download_yt(vid_id, out):
                    results.append(out)
                if len(results) >= count:
                    break
            return results
        except Exception as e:
            logger.error(f"YouTube CC: {e}")
            return []

    def _download_yt(self, vid_id: str, out: str) -> bool:
        if os.path.exists(out):
            return True
        cmd = [
            "yt-dlp",
            "--format", "bestvideo[height<=1080][ext=mp4]",
            "--no-audio",
            "--output", out,
            f"https://youtube.com/watch?v={vid_id}"
        ]
        try:
            return subprocess.run(cmd, capture_output=True, timeout=60).returncode == 0
        except Exception:
            return False

    def _fetch_archive_org(self, topic: str, count: int, format: str) -> list[str]:
        """Archive.org — yavaş olabilir, timeout'lar ayarlı."""
        collection = random.choice(ARCHIVE_COLLECTIONS)
        query = random.choice(QUERY_POOL.get(topic, ["technology"]))
        params = {
            "q": f"({query}) AND mediatype:movies AND collection:{collection}",
            "fl[]": ["identifier", "format"],
            "rows": count * 5,
            "page": random.randint(1, 5),  # 20 yerine 5 — daha hızlı
            "output": "json"
        }
        try:
            r = self._session.get(
                "https://archive.org/advancedsearch.php",
                params=params, timeout=(5, 15)  # (connect, read)
            )
            if r.status_code != 200:
                return []
            data = r.json().get("response", {}).get("docs", [])
            results = []
            for item in data:
                ident = item.get("identifier", "")
                if not ident:
                    continue
                try:
                    fr = self._session.get(
                        f"https://archive.org/metadata/{ident}",
                        timeout=(5, 10)
                    ).json()
                except Exception:
                    continue

                def _safe_size(f):
                    s = f.get("size") or 0
                    try:
                        return int(s)
                    except (ValueError, TypeError):
                        return 0

                mp4s = [
                    f for f in fr.get("files", [])
                    if f["name"].endswith(".mp4")
                    and 500_000 < _safe_size(f) < 50_000_000
                ]
                if mp4s:
                    best = sorted(mp4s, key=lambda x: _safe_size(x), reverse=True)[0]
                    dl_url = f"https://archive.org/download/{ident}/{best['name']}"
                    out = os.path.join(self.output_dir, f"archive_{ident}.mp4")
                    if self._download_direct(dl_url, out):
                        results.append(out)
                if len(results) >= count:
                    break
            return results
        except Exception as e:
            logger.error(f"Archive.org: {e}")
            return []

    def _fetch_nasa(self, topic: str, count: int, format: str) -> list[str]:
        """NASA Images API + bilinen çalışan URL'ler."""
        results = []

        # Önce bilinen çalışan URL'leri dene
        for url in NASA_REAL_URLS:
            if len(results) >= count:
                break
            uid = hashlib.md5(url.encode()).hexdigest()[:10]
            out = os.path.join(self.output_dir, f"nasa_{uid}.mp4")
            if self._download_direct(url, out):
                results.append(out)

        if len(results) >= count:
            return results

        # NASA API dene
        query = random.choice(NASA_QUERIES.get(topic, ["technology"]))
        try:
            r = self._session.get(
                "https://images-api.nasa.gov/search",
                params={
                    "q": query,
                    "media_type": "video",
                    "page": random.randint(1, 3)
                },
                timeout=(5, 15)
            )
            if r.status_code != 200:
                return results
            items = r.json().get("collection", {}).get("items", [])
            for item in items:
                if len(results) >= count:
                    break
                try:
                    collection_url = item["href"]
                    cr = self._session.get(collection_url, timeout=(5, 10)).json()
                    mp4s = [u for u in cr if u.endswith("~orig.mp4") or u.endswith("~medium.mp4")]
                    if mp4s:
                        nasa_id = item["data"][0].get("nasa_id", "unknown")
                        out = os.path.join(self.output_dir, f"nasa_{nasa_id}.mp4")
                        if self._download_direct(mp4s[0], out):
                            results.append(out)
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"NASA API: {e}")

        return results

    def _fetch_pexels(self, topic: str, count: int, format: str) -> list[str]:
        """Pexels — en güvenilir kaynak. Her çağrıda farklı sorgu ve sayfa kullanır."""
        api_key = os.getenv("PEXELS_API_KEY")
        if not api_key:
            logger.warning("PEXELS_API_KEY yok")
            return []
        pool = QUERY_POOL.get(topic, ["technology", "electric vehicle"])
        # Her çağrıda rastgele 2 farklı sorgu dene, daha geniş kapsam
        queries = random.sample(pool, min(2, len(pool)))
        orientation = "portrait" if format == "shorts" else "landscape"
        results = []
        seen = set()
        for query in queries:
            if len(results) >= count:
                break
            url = (
                f"https://api.pexels.com/videos/search"
                f"?query={requests.utils.quote(query)}&per_page=12&orientation={orientation}"
                f"&page={random.randint(1, 8)}"
            )
            try:
                r = self._session.get(
                    url,
                    headers={"Authorization": api_key},
                    timeout=(5, 20)
                )
                if r.status_code != 200:
                    logger.error(f"Pexels HTTP {r.status_code}")
                    continue
                videos = r.json().get("videos", [])
                for v in videos:
                    if len(results) >= count:
                        break
                    def _safe_width(f):
                        try:
                            return int(f.get("width") or 0)
                        except (ValueError, TypeError):
                            return 0
                    files = sorted(
                        [f for f in v["video_files"] if _safe_width(f) >= 720],
                        key=lambda x: _safe_width(x)
                    )
                    if files:
                        out = os.path.join(self.output_dir, f"pexels_{v['id']}.mp4")
                        if out not in seen and self._download_direct(files[0]["link"], out):
                            results.append(out)
                            seen.add(out)
            except Exception as e:
                logger.error(f"Pexels q='{query}': {e}")
        return results

    def _fetch_pixabay(self, topic: str, count: int, format: str) -> list[str]:
        """Pixabay — güvenilir yedek kaynak. Her çağrıda farklı sorgu kullanır."""
        api_key = os.getenv("PIXABAY_API_KEY")
        if not api_key:
            logger.warning("PIXABAY_API_KEY yok")
            return []
        pool = QUERY_POOL.get(topic, ["technology", "electric vehicle"])
        queries = random.sample(pool, min(2, len(pool)))
        results = []
        seen = set()
        for query in queries:
            if len(results) >= count:
                break
            url = (
                f"https://pixabay.com/api/videos/"
                f"?key={api_key}&q={requests.utils.quote(query)}&per_page=12"
                f"&page={random.randint(1, 6)}"
            )
            try:
                r = self._session.get(url, timeout=(5, 20))
                if r.status_code != 200:
                    logger.error(f"Pixabay HTTP {r.status_code}")
                    continue
                videos = r.json().get("hits", [])
                for v in videos:
                    if len(results) >= count:
                        break
                    f_data = (
                        v["videos"].get("large")
                        or v["videos"].get("medium")
                        or v["videos"].get("small")
                    )
                    if f_data:
                        out = os.path.join(self.output_dir, f"pixabay_{v['id']}.mp4")
                        if out not in seen and self._download_direct(f_data["url"], out):
                            results.append(out)
                            seen.add(out)
            except Exception as e:
                logger.error(f"Pixabay q='{query}': {e}")
        return results

    def _fetch_wikimedia(self, topic: str, count: int, format: str) -> list[str]:
        """Wikimedia Commons — CC0/public domain."""
        query = random.choice(QUERY_POOL.get(topic, ["technology"]))
        params = {
            "action": "query",
            "list": "search",
            "srsearch": f"{query} filetype:video",
            "srnamespace": "6",
            "srlimit": count * 3,
            "format": "json"
        }
        try:
            r = self._session.get(
                "https://commons.wikimedia.org/w/api.php",
                params=params, timeout=(5, 15)
            )
            if r.status_code != 200:
                return []
            hits = r.json().get("query", {}).get("search", [])
            results = []
            for hit in hits:
                if len(results) >= count:
                    break
                title = hit["title"]
                try:
                    info_url = (
                        "https://commons.wikimedia.org/w/api.php"
                        f"?action=query&titles={title}"
                        "&prop=imageinfo&iiprop=url&format=json"
                    )
                    ir = self._session.get(info_url, timeout=(5, 10)).json()
                    pages = ir.get("query", {}).get("pages", {})
                    for p in pages.values():
                        url = p.get("imageinfo", [{}])[0].get("url", "")
                        if url and url.endswith(".mp4"):
                            out = os.path.join(
                                self.output_dir,
                                f"wiki_{hit['pageid']}.mp4"
                            )
                            if self._download_direct(url, out):
                                results.append(out)
                except Exception:
                    continue
            return results
        except Exception as e:
            logger.error(f"Wikimedia: {e}")
            return []

    def _fetch_coverr(self, topic: str, count: int, format: str) -> list[str]:
        """Coverr — CC0 lisanslı stock videolar."""
        query = random.choice(QUERY_POOL.get(topic, ["technology"]))
        try:
            r = self._session.get(
                "https://coverr.co/api/videos/search",
                params={"query": query, "per_page": 10, "page": random.randint(1, 3)},
                timeout=(5, 15)
            )
            if r.status_code != 200:
                return []
            videos = r.json().get("videos", [])
            results = []
            for v in videos:
                dl = v.get("urls", {}).get("mp4")
                if dl:
                    out = os.path.join(self.output_dir, f"coverr_{v['id']}.mp4")
                    if self._download_direct(dl, out):
                        results.append(out)
                if len(results) >= count:
                    break
            return results
        except Exception as e:
            logger.error(f"Coverr: {e}")
            return []

    def _download_direct(self, url: str, out: str) -> bool:
        """
        Güvenli indirme:
        - (connect=5s, read=20s) timeout
        - Max 300MB
        - Max 60 saniye toplam indirme süresi
        """
        if os.path.exists(out) and os.path.getsize(out) > 50_000:
            return True
        try:
            r = self._session.get(
                url,
                timeout=(5, 20),   # connect=5s, read=20s
                stream=True
            )
            if r.status_code != 200:
                return False
            # Content-type kontrolü
            ct = r.headers.get("content-type", "")
            if ct and "video" not in ct and "octet-stream" not in ct:
                return False
            # Content-length kontrolü
            cl = int(r.headers.get("content-length", 0))
            if cl and (cl < 50_000 or cl > 300_000_000):
                return False

            start_time = time.time()
            downloaded = 0

            with open(out, "wb") as f:
                for chunk in r.iter_content(chunk_size=131_072):
                    f.write(chunk)
                    downloaded += len(chunk)
                    # Zaman sınırı: 60 saniye
                    if time.time() - start_time > 60:
                        logger.warning(f"Timeout (60s): {url[:60]}")
                        break
                    # Boyut sınırı: 300MB
                    if downloaded > 300_000_000:
                        logger.warning(f"Boyut sınırı (300MB): {url[:60]}")
                        break

            if os.path.exists(out) and os.path.getsize(out) > 50_000:
                return True
            # Başarısız — sil
            if os.path.exists(out):
                os.remove(out)
            return False

        except requests.exceptions.ConnectTimeout:
            logger.warning(f"ConnectTimeout: {url[:60]}")
        except requests.exceptions.ReadTimeout:
            logger.warning(f"ReadTimeout: {url[:60]}")
        except Exception as e:
            logger.error(f"İndirme hatası: {url[:60]} | {e}")
        if os.path.exists(out):
            try:
                os.remove(out)
            except Exception:
                pass
        return False
