"""
audio_bg_engine.py — v1.0
Ücretsiz arka plan müziği ve SFX motoru. Telif riski sıfır.

Kaynaklar (öncelik sırasıyla):
  1. Incompetech (Kevin MacLeod) — CC-BY, kategori & BPM filtrelemeli
  2. Free Music Archive (FMA) — CC0/CC-BY API
  3. ccMixter — CC lisanslı
  4. Freesound.org — CC0 SFX (FREESOUND_CLIENT_ID gerekli)
  5. Looperman — Ücretsiz loop'lar (scrape)

Atıf gereksinimi (CC-BY için):
  description alanına "Music: <title> by Kevin MacLeod (incompetech.com)
  Licensed under Creative Commons: By Attribution 4.0" ekle.
"""
import os, re, json, random, logging, requests, time, hashlib
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger("AudioBgEngine")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EvcarixBot/1.0)"}
AUDIO_CACHE_DIR = "assets/audio_cache"
LICENSE_LOG = "license_log.json"

# Kevin MacLeod genre → BPM mapping (Incompetech categories)
INCOMPETECH_GENRES = {
    "epic":         ["Epic", "Cinematic", "Dramatic"],
    "calm":         ["Ambient", "Atmospheric", "Drone"],
    "upbeat":       ["Electronic", "Funk", "Upbeat"],
    "technology":   ["Electronic", "Cinematic", "Driving"],
    "science":      ["Ambient", "Cinematic", "Ethereal"],
    "data":         ["Electronic", "Minimal", "Atmospheric"],
    "default":      ["Cinematic", "Electronic", "Ambient"],
}

# Incompetech public download base (CC-BY 4.0)
INCOMPETECH_BASE = "https://incompetech.com"
INCOMPETECH_API  = "https://incompetech.com/music/royalty-free/music.html"

# FMA API
FMA_API_BASE = "https://freemusicarchive.org/api"

# ccMixter API
CCMIXTER_API = "http://api.ccmixter.org/api/query"


def _log_license(file_path: str, source: str, license_type: str,
                  author: str, title: str, attribution: str = ""):
    try:
        data = {}
        if os.path.exists(LICENSE_LOG):
            with open(LICENSE_LOG, "r") as f:
                data = json.load(f)
        data[os.path.basename(file_path)] = {
            "source": source, "license": license_type,
            "author": author, "title": title,
            "attribution": attribution, "timestamp": time.time()
        }
        with open(LICENSE_LOG, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"License log failed: {e}")


def _download_audio(url: str, dest: str, timeout: int = 60) -> bool:
    try:
        url = url.replace(" ", "%20")
        r = requests.get(url, headers=HEADERS, stream=True, timeout=timeout)
        if r.status_code != 200:
            logger.warning(f"Audio HTTP {r.status_code}: {url}")
            return False
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1024 * 256):
                if chunk:
                    f.write(chunk)
        if os.path.getsize(dest) < 10_000:
            os.remove(dest)
            return False
        return True
    except Exception as e:
        logger.error(f"Audio download failed ({url}): {e}")
        if os.path.exists(dest):
            try:
                os.remove(dest)
            except Exception:
                pass
        return False


class IncompetechSource:
    """
    Kevin MacLeod — Incompetech.com
    Lisans: Creative Commons Attribution 4.0 (CC-BY)
    Kullanım: description'a atıf ekle.
    API key gerekmez.
    """

    # Doğrudan indirilebilen ücretsiz track listesi (statik, güvenilir)
    # Kaynak: incompetech.com/music/royalty-free/music.html
    TRACKS = [
        # Cinematic / Uplifting
        {"title": "Inspired",         "genre": "Cinematic",  "bpm": 110,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Inspired.mp3"},
        {"title": "Cipher",           "genre": "Electronic", "bpm": 120,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher.mp3"},
        {"title": "Decisions",        "genre": "Cinematic",  "bpm": 100,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Decisions.mp3"},
        {"title": "Ouroboros",        "genre": "Ambient",    "bpm": 80,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Ouroboros.mp3"},
        {"title": "Impact Moderato",  "genre": "Dramatic",   "bpm": 115,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Impact Moderato.mp3"},
        {"title": "Spacial Winds",    "genre": "Ambient",    "bpm": 70,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Spacial Winds.mp3"},
        {"title": "Digital Lemonade", "genre": "Electronic", "bpm": 125,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Digital Lemonade.mp3"},
        {"title": "Funky Chunk",      "genre": "Funk",       "bpm": 105,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Funky Chunk.mp3"},
        {"title": "Hyperfun",         "genre": "Electronic", "bpm": 140,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Hyperfun.mp3"},
        {"title": "Corncob",          "genre": "Upbeat",     "bpm": 108,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Corncob.mp3"},
        {"title": "The Builder",      "genre": "Cinematic",  "bpm": 90,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/The Builder.mp3"},
        {"title": "Night Owl",        "genre": "Atmospheric","bpm": 85,
         "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Night Owl.mp3"},
    ]

    def get_track(self, mood: str = "technology",
                  dest_dir: str = AUDIO_CACHE_DIR) -> dict | None:
        """Mood'a göre uygun bir track indir ve döndür."""
        os.makedirs(dest_dir, exist_ok=True)
        genres = INCOMPETECH_GENRES.get(mood, INCOMPETECH_GENRES["default"])
        candidates = [t for t in self.TRACKS if t["genre"] in genres]
        if not candidates:
            candidates = self.TRACKS
        random.shuffle(candidates)

        for track in candidates:
            fname = re.sub(r'[^a-zA-Z0-9]', '_', track["title"]) + ".mp3"
            dest = os.path.join(dest_dir, f"incompetech_{fname}")
            if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
                logger.info(f"[Incompetech] Cache hit: {track['title']}")
                return {**track, "path": dest,
                        "attribution": f"Music: {track['title']} by Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 http://creativecommons.org/licenses/by/4.0/"}
            logger.info(f"[Incompetech] İndiriliyor: {track['title']}")
            if _download_audio(track["url"], dest):
                _log_license(dest, "Incompetech", "CC-BY 4.0",
                             "Kevin MacLeod", track["title"],
                             f"Music by Kevin MacLeod (incompetech.com)")
                return {**track, "path": dest,
                        "attribution": f"Music: {track['title']} by Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 http://creativecommons.org/licenses/by/4.0/"}
        return None


class FMASource:
    """
    Free Music Archive — freemusicarchive.org
    CC0 / CC-BY lisanslı. Public API, key gerektirmez.
    """

    API_URL = "https://freemusicarchive.org/api/get/tracks.json"

    def get_track(self, genre: str = "Electronic",
                  dest_dir: str = AUDIO_CACHE_DIR) -> dict | None:
        os.makedirs(dest_dir, exist_ok=True)
        try:
            params = {
                "genre": genre, "limit": 10, "page": random.randint(1, 5),
                "license": "Attribution", "sort": "track_date_created",
                "order": "desc"
            }
            r = requests.get(self.API_URL, params=params,
                             headers=HEADERS, timeout=20)
            if r.status_code != 200:
                logger.warning(f"FMA API error: {r.status_code}")
                return None
            data = r.json()
            tracks = data.get("dataset", [])
            random.shuffle(tracks)
            for track in tracks:
                url = track.get("track_file") or track.get("track_url")
                if not url:
                    continue
                title  = track.get("track_title", "Unknown")
                artist = track.get("artist_name", "Unknown")
                lic    = track.get("license_title", "CC-BY")
                # NC lisanslarını atla (ticari kullanım için uygun değil)
                if "noncommercial" in lic.lower() or "nc" in lic.lower():
                    continue
                fname = hashlib.md5(url.encode()).hexdigest()[:12]
                dest  = os.path.join(dest_dir, f"fma_{fname}.mp3")
                if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
                    return {"title": title, "artist": artist,
                            "license": lic, "path": dest,
                            "attribution": f"Music: {title} by {artist} (freemusicarchive.org)"}
                if _download_audio(url, dest):
                    _log_license(dest, "FreeMusucArchive", lic, artist, title)
                    return {"title": title, "artist": artist,
                            "license": lic, "path": dest,
                            "attribution": f"Music: {title} by {artist} (freemusicarchive.org)"}
        except Exception as e:
            logger.error(f"FMA error: {e}")
        return None


class ccMixerSource:
    """
    ccMixter — CC lisanslı ambient/electronic müzik.
    Public API, key gerektirmez.
    ⚠️ Monetizasyon güvenliği: NC (NonCommercial) lisanslı içerikler filtreleniyor.
    """

    def get_track(self, tags: str = "ambient electronic",
                  dest_dir: str = AUDIO_CACHE_DIR) -> dict | None:
        os.makedirs(dest_dir, exist_ok=True)
        try:
            params = {
                "tags": tags, "limit": 15, "offset": random.randint(0, 50),
                "f": "json", "lic": "open"
            }
            r = requests.get(CCMIXTER_API, params=params,
                             headers=HEADERS, timeout=20)
            if r.status_code != 200:
                return None
            tracks = r.json()
            random.shuffle(tracks)
            for track in tracks:
                url = track.get("download_url") or track.get("filesize_l")
                if not url or not url.startswith("http"):
                    continue
                title  = track.get("upload_name", "Unknown")
                artist = track.get("user_name", "Unknown")
                lic    = track.get("license_name", "CC")
                # ⚠️ MONETIZASYON KORUMASI: NC ve ND lisansları ticari kullanıma kapalı
                lic_lower = lic.lower()
                if ("noncommercial" in lic_lower or "-nc" in lic_lower
                        or "no derivatives" in lic_lower or "-nd" in lic_lower):
                    logger.debug(f"[ccMixter] NC/ND lisans atlandı: {title} ({lic})")
                    continue
                fname  = hashlib.md5(url.encode()).hexdigest()[:12]
                dest   = os.path.join(dest_dir, f"ccmixter_{fname}.mp3")
                if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
                    return {"title": title, "artist": artist,
                            "license": lic, "path": dest,
                            "attribution": f"Music: {title} by {artist} (ccmixter.org) — {lic}"}
                if _download_audio(url, dest):
                    _log_license(dest, "ccMixter", lic, artist, title)
                    return {"title": title, "artist": artist,
                            "license": lic, "path": dest,
                            "attribution": f"Music: {title} by {artist} (ccmixter.org) — {lic}"}
        except Exception as e:
            logger.error(f"ccMixter error: {e}")
        return None


class FreesoundSFX:
    """
    Freesound.org — CC0 ses efektleri.
    Kimlik doğrulama: ?token=API_KEY (Bearer header değil!)
    
    Key alma: freesound.org/apiv2/apply/ → ücretsiz hesap aç, uygulama yarat.
    GitHub Secret: FREESOUND_API_KEY
    """

    BASE = "https://freesound.org/apiv2"

    def __init__(self):
        # Yeni ad: FREESOUND_API_KEY (eski FREESOUND_TOKEN da destekleniyor)
        self.api_key = (
            os.getenv("FREESOUND_API_KEY")
            or os.getenv("FREESOUND_TOKEN")
            or os.getenv("FREESOUND_CLIENT_ID")
        )

    def search_sfx(self, query: str, count: int = 3,
                   dest_dir: str = AUDIO_CACHE_DIR) -> list[str]:
        """CC0 SFX indir. API key yoksa sessizce boş liste dön."""
        if not self.api_key:
            logger.info("[Freesound] API key bulunamadı, SFX atlanıyor.")
            logger.info("[Freesound] Key al: https://freesound.org/apiv2/apply/")
            return []

        os.makedirs(dest_dir, exist_ok=True)
        paths = []
        try:
            # Doğru auth yöntemi: ?token= query param (Bearer header değil)
            params = {
                "query": query,
                "filter": 'license:"Creative Commons 0"',
                "fields": "id,name,previews,license",
                "page_size": count * 3,
                "token": self.api_key,  # ← Bu şekilde gönderilmeli
            }
            r = requests.get(
                f"{self.BASE}/search/text/",
                params=params,
                headers=HEADERS,
                timeout=15
            )
            if r.status_code == 401:
                logger.warning("[Freesound] 401 Unauthorized — API key geçersiz veya süresi dolmuş.")
                logger.warning("[Freesound] https://freesound.org/apiv2/apply/ adresinden yenile.")
                return []
            if r.status_code != 200:
                logger.warning(f"[Freesound] HTTP {r.status_code}: {r.text[:100]}")
                return []

            for sound in r.json().get("results", []):
                # Preview URL (doğrudan indirilebilir, token gerekmez)
                preview_url = (
                    sound.get("previews", {}).get("preview-hq-mp3")
                    or sound.get("previews", {}).get("preview-lq-mp3")
                )
                if not preview_url:
                    continue
                fname = f"sfx_{sound['id']}.mp3"
                dest  = os.path.join(dest_dir, fname)
                if os.path.exists(dest) and os.path.getsize(dest) > 1000:
                    paths.append(dest)
                elif _download_audio(preview_url, dest):
                    _log_license(dest, "Freesound", "CC0", "Unknown",
                                 sound.get("name", ""))
                    paths.append(dest)
                if len(paths) >= count:
                    break

        except Exception as e:
            logger.error(f"[Freesound] Hata: {e}")
        return paths


class AudioBgEngine:
    """
    Ana arka plan müziği motoru.
    Öncelik: Incompetech → FMA → ccMixter → sessiz
    """

    def __init__(self):
        self.incompetech = IncompetechSource()
        self.fma         = FMASource()
        self.ccmixter    = ccMixerSource()
        self.freesound   = FreesoundSFX()

    def get_background_music(self, mood: str = "technology",
                              dest_dir: str = AUDIO_CACHE_DIR) -> dict | None:
        """
        Mood'a uygun bir arka plan müziği indir ve metadata döndür.
        
        Args:
            mood: epic | calm | upbeat | technology | science | data | default
        Returns:
            {"path": str, "title": str, "attribution": str} veya None
        """
        logger.info(f"[AudioBgEngine] Müzik aranıyor: mood={mood}")

        # 1. Incompetech (en güvenilir, kaliteli)
        track = self.incompetech.get_track(mood, dest_dir)
        if track:
            logger.info(f"[AudioBgEngine] ✅ Incompetech: {track['title']}")
            return track

        # 2. FMA
        genre_map = {
            "epic": "Cinematic", "calm": "Ambient",
            "upbeat": "Electronic", "technology": "Electronic",
            "science": "Ambient", "data": "Electronic", "default": "Ambient"
        }
        track = self.fma.get_track(genre_map.get(mood, "Electronic"), dest_dir)
        if track:
            logger.info(f"[AudioBgEngine] ✅ FMA: {track['title']}")
            return track

        # 3. ccMixter
        tag_map = {
            "epic": "epic dramatic", "calm": "ambient calm",
            "upbeat": "upbeat electronic", "technology": "electronic technology",
            "science": "ambient space", "default": "ambient electronic"
        }
        track = self.ccmixter.get_track(tag_map.get(mood, "ambient"), dest_dir)
        if track:
            logger.info(f"[AudioBgEngine] ✅ ccMixter: {track['title']}")
            return track

        logger.warning("[AudioBgEngine] ❌ Hiç müzik bulunamadı — arka plan sessiz olacak.")
        return None

    def get_sfx(self, sfx_type: str = "notification",
                dest_dir: str = AUDIO_CACHE_DIR) -> list[str]:
        """Ses efekti (SFX) al. Freesound CC0."""
        query_map = {
            "notification": "notification alert",
            "whoosh": "whoosh transition",
            "impact": "impact hit dramatic",
            "tick": "tick clock timer",
            "pop": "pop bubble interface",
        }
        return self.freesound.search_sfx(
            query_map.get(sfx_type, sfx_type), count=2, dest_dir=dest_dir)

    def mix_bg_music_with_voice(self, voice_path: str, music_path: str,
                                 output_path: str, music_volume: float = 0.12) -> str:
        """
        FFmpeg ile sesi ve arka plan müziğini karıştır.
        music_volume: 0.0 (sessiz) → 1.0 (tam ses). 0.12 önerilir.
        Returns: output_path
        """
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-i", voice_path,
            "-i", music_path,
            "-filter_complex",
            f"[1:a]volume={music_volume},aloop=loop=-1:size=2e+09[bg];"
            f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=3[out]",
            "-map", "[out]",
            "-c:a", "aac", "-b:a", "320k", "-ac", "2",
            output_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"[AudioBgEngine] ✅ Ses karıştırıldı: {output_path}")
                return output_path
            else:
                logger.error(f"FFmpeg mix failed: {result.stderr.decode()[:200]}")
        except Exception as e:
            logger.error(f"Audio mix error: {e}")
        # Fallback: sadece voice
        return voice_path
