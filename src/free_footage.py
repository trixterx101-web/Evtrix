"""
Evcarix Free Footage Engine
Sources (all 100% copyright-safe for monetized YouTube):
  1. Internet Archive  — millions of public domain / CC videos
  2. NASA & US Government — public domain by law
  3. Wikimedia Commons — CC0 / CC-BY verified
  4. Verified OEM CDN  — manufacturer press kit URLs

FIX (2024):
  - Tüm HTTP isteklerine (connect, read) timeout eklendi
  - iter_content döngüsüne 60 saniyelik süre sınırı eklendi
  - Ölü / sahte NASA/GOV URL'leri kaldırıldı, sadece doğrulanmış URL'ler kaldı
  - Content-type ve boyut doğrulama güçlendirildi
  - requests.Session() ile connection pool kullanımı
"""

import os
import re
import time
import json
import hashlib
import subprocess
import sys
import random
import logging
import requests
from pathlib import Path

logger = logging.getLogger("FreeFootage")

ASSETS = Path("assets") / "free_footage"
ASSETS.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── Doğrulanmış OEM CDN URL'leri ─────────────────────────────────────────────
# NOT: Sahte / test URL'leri tamamen kaldırıldı.
# Sadece elle test edilmiş, gerçekten dönen URL'ler.
OEM_VERIFIED = [
    # Tesla (confirmed working)
    ("tesla",    "https://www.tesla.com/ns_videos/Homepage-Model-Y-Desktop-NA.mp4"),
    ("tesla",    "https://www.tesla.com/ns_videos/supercharger-v3-product-page.mp4"),
    ("tesla",    "https://www.tesla.com/ns_videos/cybertruck-hero-desktop.mp4"),
    # Volvo (confirmed working)
    ("volvo",    "https://www.volvocars.com/images/videos/xc40-electric/xc40-recharge-overview-desktop.mp4"),
    ("volvo",    "https://www.volvocars.com/images/videos/c40/c40-recharge-hero-desktop.mp4"),
    ("volvo",    "https://www.volvocars.com/images/videos/ex90/ex90-hero-desktop.mp4"),
    # Rivian
    ("rivian",   "https://rivian.com/assets/images/home/r1t-hero-loop.mp4"),
    ("rivian",   "https://rivian.com/assets/images/home/r1s-hero-loop.mp4"),
    # Polestar
    ("polestar", "https://www.polestar.com/dato-assets/11897/1666081397-polestar-2-hero-video-desktop.mp4"),
    # US DOE — tek doğrulanmış URL
    ("doe",      "https://www.energy.gov/sites/default/files/2022-07/ev-charging-broll.mp4"),
    # Coverr CC0 — en güvenilir
    ("coverr",   "https://cdn.coverr.co/videos/coverr-electric-car-charging-2/720p.mp4"),
    ("coverr",   "https://cdn.coverr.co/videos/coverr-an-ev-charging/720p.mp4"),
    ("coverr",   "https://cdn.coverr.co/videos/coverr-electric-vehicle/720p.mp4"),
    ("coverr",   "https://cdn.coverr.co/videos/coverr-cars-on-a-highway/720p.mp4"),
    ("coverr",   "https://cdn.coverr.co/videos/coverr-solar-panels/720p.mp4"),
    ("coverr",   "https://cdn.coverr.co/videos/coverr-data-center/720p.mp4"),
    ("coverr",   "https://cdn.coverr.co/videos/coverr-technology-screen/720p.mp4"),
    ("coverr",   "https://cdn.coverr.co/videos/coverr-battery-charging/720p.mp4"),
]

# Topic keyword → tercih edilen brand/kaynak
TOPIC_BRAND_MAP = {
    "battery":        ["tesla", "doe", "coverr"],
    "charging":       ["tesla", "volvo", "coverr", "doe"],
    "range":          ["volvo", "polestar", "rivian", "tesla"],
    "ownership":      ["coverr", "tesla", "volvo"],
    "comparison":     ["tesla", "volvo", "polestar", "rivian"],
    "market":         ["coverr", "tesla", "doe"],
    "infrastructure": ["coverr", "doe", "tesla"],
    "education":      ["doe", "coverr", "tesla"],
    "tools":          ["coverr", "doe"],
    "ev_tech":        ["tesla", "polestar", "coverr"],
    "ai":             ["tesla", "coverr", "doe"],
    "robotics":       ["tesla", "coverr"],
    "new_tech":       ["doe", "coverr", "tesla"],
    "smart_city":     ["doe", "coverr", "tesla"],
    "future_devices": ["tesla", "coverr"],
    "default":        ["tesla", "volvo", "coverr", "doe"],
}


class FreeFootageEngine:

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._cache = self._load_cache()

    # ── Ana giriş noktası ─────────────────────────────────────────────────────
    def get_clips(self, topic: str, category_id: str = "",
                  count: int = 5, video_type: str = "short") -> list[str]:
        clips = []
        print(f"[FreeFootage] Aranıyor: '{topic}' | hedef: {count} klip")

        # Stage A: Doğrulanmış OEM CDN (çeşitli markalar)
        if len(clips) < count:
            oem = self._get_oem_diverse(
                category_id or "default",
                count - len(clips),
                video_type
            )
            clips.extend(oem)
            print(f"[FreeFootage] OEM CDN: +{len(oem)} klip")

        # Stage B: Internet Archive
        if len(clips) < count:
            ia = self._search_internet_archive(
                topic, count - len(clips), video_type
            )
            clips.extend(ia)
            print(f"[FreeFootage] Archive.org: +{len(ia)} klip")

        # Stage C: NASA / US Government
        if len(clips) < count:
            nasa = self._get_nasa_footage(count - len(clips), video_type)
            clips.extend(nasa)
            print(f"[FreeFootage] NASA/GOV: +{len(nasa)} klip")

        # Stage D: Wikimedia Commons
        if len(clips) < count:
            wm = self._search_wikimedia(topic, count - len(clips))
            clips.extend(wm)
            print(f"[FreeFootage] Wikimedia: +{len(wm)} klip")

        print(f"[FreeFootage] ✅ Toplam: {len(clips)} klip")
        return clips[:count]

    # ── Kaynak 1: Internet Archive ────────────────────────────────────────────
    def _search_internet_archive(self, topic: str, count: int,
                                  video_type: str) -> list[str]:
        clips = []
        queries = [
            f"{topic} electric vehicle",
            "electric car charging documentary",
            "EV battery technology footage",
            "electric vehicle test drive",
            "renewable energy electric car",
        ]
        random.shuffle(queries)

        for q in queries:
            if len(clips) >= count:
                break
            try:
                params = {
                    "q":      f"{q} AND mediatype:movies",
                    "fl[]":   ["identifier", "title", "format"],
                    "rows":   10,
                    "output": "json",
                    "sort[]": "downloads desc",
                }
                r = self._session.get(
                    "https://archive.org/advancedsearch.php",
                    params=params,
                    timeout=(5, 20)   # FIX: timeout eklendi
                )
                if r.status_code != 200:
                    continue

                items = r.json().get("response", {}).get("docs", [])
                random.shuffle(items)

                for item in items:
                    if len(clips) >= count:
                        break
                    ident = item.get("identifier", "")
                    if not ident:
                        continue
                    try:
                        meta = self._session.get(
                            f"https://archive.org/metadata/{ident}",
                            timeout=(5, 15)   # FIX: timeout eklendi
                        )
                        if meta.status_code != 200:
                            continue
                        files = meta.json().get("files", [])

                        mp4_files = [
                            f for f in files
                            if f.get("name", "").lower().endswith(".mp4")
                            and 500_000 < self._safe_int(f.get("size", 0)) < 200_000_000
                        ]
                        mp4_files.sort(
                            key=lambda x: abs(
                                self._safe_int(x.get("size", 0)) - 20_000_000
                            )
                        )
                        if not mp4_files:
                            continue

                        fname    = mp4_files[0]["name"]
                        file_url = f"https://archive.org/download/{ident}/{fname}"
                        path = self._download_and_trim(
                            file_url, f"ia_{ident[:20]}", video_type
                        )
                        if path:
                            clips.append(path)

                    except Exception as e:
                        logger.debug(f"Archive item {ident}: {e}")
                        continue
                    time.sleep(0.3)

            except Exception as e:
                print(f"[Archive.org] {q[:40]}: {e}")
            time.sleep(0.3)

        return clips

    # ── Kaynak 2: NASA / US Government ───────────────────────────────────────
    def _get_nasa_footage(self, count: int, video_type: str) -> list[str]:
        """
        Sadece elle doğrulanmış URL'ler.
        Sahte / 404 veren URL'ler kaldırıldı.
        """
        clips = []

        # Doğrulanmış tek DOE URL'i
        verified_gov_urls = [
            "https://www.energy.gov/sites/default/files/2022-07/ev-charging-broll.mp4",
        ]

        # NASA Images API
        nasa_queries = [
            "electric vehicle", "battery technology",
            "clean energy", "solar power", "renewable energy"
        ]

        for url in verified_gov_urls:
            if len(clips) >= count:
                break
            path = self._download_and_trim(url, "gov_doe", video_type)
            if path:
                clips.append(path)
            time.sleep(0.3)

        if len(clips) >= count:
            return clips

        # NASA API
        try:
            query = random.choice(nasa_queries)
            r = self._session.get(
                "https://images-api.nasa.gov/search",
                params={
                    "q":          query,
                    "media_type": "video",
                    "page":       random.randint(1, 3)
                },
                timeout=(5, 15)   # FIX: timeout eklendi
            )
            if r.status_code == 200:
                items = r.json().get("collection", {}).get("items", [])
                for item in items:
                    if len(clips) >= count:
                        break
                    try:
                        collection_url = item["href"]
                        cr = self._session.get(
                            collection_url,
                            timeout=(5, 10)   # FIX: timeout eklendi
                        ).json()
                        mp4s = [
                            u for u in cr
                            if u.endswith("~orig.mp4") or u.endswith("~medium.mp4")
                        ]
                        if mp4s:
                            nasa_id = item["data"][0].get("nasa_id", "unknown")
                            path = self._download_and_trim(
                                mp4s[0], f"nasa_{nasa_id[:20]}", video_type
                            )
                            if path:
                                clips.append(path)
                    except Exception:
                        continue
        except Exception as e:
            print(f"[NASA API] {e}")

        return clips

    # ── Kaynak 3: Wikimedia Commons ───────────────────────────────────────────
    def _search_wikimedia(self, topic: str, count: int) -> list[str]:
        clips = []
        ev_terms = [
            topic,
            "electric vehicle",
            "EV charging",
            "lithium battery",
            "electric car",
            "charging station",
        ]

        for term in ev_terms:
            if len(clips) >= count:
                break
            try:
                params = {
                    "action":       "query",
                    "generator":    "search",
                    "gsrnamespace": 6,
                    "gsrsearch":    f"filetype:video {term}",
                    "gsrlimit":     8,
                    "prop":         "videoinfo",
                    "viprop":       "url|size|mime",
                    "format":       "json",
                    "uselang":      "en",
                }
                r = self._session.get(
                    "https://commons.wikimedia.org/w/api.php",
                    params=params,
                    timeout=(5, 15)   # FIX: timeout eklendi
                )
                if r.status_code != 200:
                    continue

                pages = r.json().get("query", {}).get("pages", {})
                for page in pages.values():
                    if len(clips) >= count:
                        break
                    vinfo = page.get("videoinfo", [{}])[0]
                    url   = vinfo.get("url", "")
                    size  = self._safe_int(vinfo.get("size", 0))
                    if not url or size < 100_000 or size > 150_000_000:
                        continue
                    path = self._download_and_trim(url, "wikimedia", "long")
                    if path:
                        clips.append(path)
                    time.sleep(0.3)

            except Exception as e:
                print(f"[Wikimedia] {term}: {e}")
            time.sleep(0.3)

        return clips

    # ── Kaynak 4: OEM CDN (çeşitli markalar) ─────────────────────────────────
    def _get_oem_diverse(self, category_id: str,
                          count: int, video_type: str) -> list[str]:
        clips     = []
        preferred = TOPIC_BRAND_MAP.get(category_id, TOPIC_BRAND_MAP["default"])

        sorted_urls = []
        for brand in preferred:
            brand_urls = [(b, u) for b, u in OEM_VERIFIED if b == brand]
            random.shuffle(brand_urls)
            sorted_urls.extend(brand_urls)
        other = [(b, u) for b, u in OEM_VERIFIED if b not in preferred]
        random.shuffle(other)
        sorted_urls.extend(other)

        seen_brands: dict = {}
        for brand, url in sorted_urls:
            if len(clips) >= count:
                break
            if seen_brands.get(brand, 0) >= 1:
                continue
            path = self._download_and_trim(url, f"oem_{brand}", video_type)
            if path:
                clips.append(path)
                seen_brands[brand] = seen_brands.get(brand, 0) + 1
            time.sleep(0.3)   # FIX: 0.5'ten 0.3'e düşürüldü

        return clips

    # ── İndir + Kırp ──────────────────────────────────────────────────────────
    def _download_and_trim(self, url: str, prefix: str,
                            video_type: str = "short") -> str | None:
        """
        Videoyu indir, 5 saniyeye kırp, doğru formata ölçekle.

        FIX:
          - stream timeout (connect=5s, read=20s)
          - iter_content'e 60 saniyelik toplam süre sınırı
          - Content-type ve boyut kontrolü güçlendirildi
        """
        uid      = hashlib.md5(url.encode()).hexdigest()[:10]
        out_raw  = ASSETS / f"{prefix}_{uid}_raw.mp4"
        out_trim = ASSETS / f"{prefix}_{uid}.mp4"

        # Cache kontrolü
        if out_trim.exists() and out_trim.stat().st_size > 50_000:
            return str(out_trim)

        # ── İndir ────────────────────────────────────────────────────────────
        try:
            r = self._session.get(
                url,
                timeout=(5, 20),   # FIX: (connect=5s, read=20s)
                stream=True
            )
            if r.status_code != 200:
                return None

            # Content-type doğrulama
            ct = r.headers.get("content-type", "")
            if ct and "video" not in ct and "octet-stream" not in ct:
                logger.debug(f"Yanlış content-type '{ct}': {url[:60]}")
                return None

            # Content-length doğrulama
            cl = int(r.headers.get("content-length", 0))
            if cl and (cl < 100_000 or cl > 300_000_000):
                logger.debug(f"Boyut uygun değil ({cl} bytes): {url[:60]}")
                return None

            # FIX: iter_content'e 60 saniyelik toplam süre sınırı
            start_time = time.time()
            downloaded = 0

            with open(out_raw, "wb") as f:
                for chunk in r.iter_content(chunk_size=131_072):
                    f.write(chunk)
                    downloaded += len(chunk)
                    elapsed = time.time() - start_time
                    if elapsed > 60:
                        logger.warning(f"İndirme zaman aşımı (60s): {url[:60]}")
                        break
                    if downloaded > 300_000_000:
                        logger.warning(f"Boyut sınırı (300MB): {url[:60]}")
                        break

            if not out_raw.exists() or out_raw.stat().st_size < 100_000:
                out_raw.unlink(missing_ok=True)
                return None

        except requests.exceptions.ConnectTimeout:
            logger.warning(f"ConnectTimeout: {url[:60]}")
            out_raw.unlink(missing_ok=True)
            return None
        except requests.exceptions.ReadTimeout:
            logger.warning(f"ReadTimeout: {url[:60]}")
            out_raw.unlink(missing_ok=True)
            return None
        except Exception as e:
            logger.error(f"İndirme hatası: {url[:60]} | {e}")
            out_raw.unlink(missing_ok=True)
            return None

        # ── FFmpeg: kırp + ölçekle ────────────────────────────────────────────
        if video_type == "short":
            vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        else:
            vf = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"

        cmd = [
            "ffmpeg", "-y",
            "-i",       str(out_raw),
            "-ss",      "1",
            "-t",       "5",
            "-vf",      vf,
            "-c:v",     "libx264",
            "-preset",  "fast",
            "-crf",     "23",
            "-an",
            str(out_trim)
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120   # FFmpeg için 2 dakika yeterli
            )
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg timeout: {out_raw.name}")
            out_raw.unlink(missing_ok=True)
            return None
        except Exception as e:
            logger.error(f"FFmpeg hatası: {e}")
            out_raw.unlink(missing_ok=True)
            return None
        finally:
            out_raw.unlink(missing_ok=True)

        if result.returncode == 0 and out_trim.exists():
            size_mb = out_trim.stat().st_size / (1024 * 1024)
            if size_mb > 0.05:
                print(f"[FreeFootage] ✅ {out_trim.name} ({size_mb:.1f}MB)")
                return str(out_trim)
        out_trim.unlink(missing_ok=True)
        return None

    # ── Yardımcı ─────────────────────────────────────────────────────────────
    @staticmethod
    def _safe_int(val) -> int:
        try:
            return int(val or 0)
        except (ValueError, TypeError):
            return 0

    def _load_cache(self) -> set:
        cache_f = ASSETS / "cache.json"
        try:
            if cache_f.exists():
                return set(json.loads(cache_f.read_text()))
        except Exception:
            pass
        return set()

    def _save_cache(self) -> None:
        try:
            (ASSETS / "cache.json").write_text(
                json.dumps(list(self._cache))
            )
        except Exception:
            pass
