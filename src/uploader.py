import os
import re
import time
import json
import base64
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

# =============================================================================
# SELF-HEALING TOKEN SYSTEM
# Her basarili auth sonrasi GitHub Secret otomatik guncellenir.
# Token hicbir zaman "expired" olmaz -- kendini yeniler.
# =============================================================================

def _update_github_secret(name: str, value: str) -> bool:
    """GitHub Actions Secret REST API uzerinden gunceller.
    
    Self-healing token sisteminin kalbi: Her basarili OAuth refresh
    sonrasi yeni token JSON ve refresh_token otomatik olarak GitHub Secret'a
    geri yazilir. Bir sonraki pipeline calismasinda guncel token kullanilir.
    
    Gereksinim: GITHUB_TOKEN env var (Actions'ta ${{ secrets.GITHUB_TOKEN }})
    Gereksinim: PyNaCl (pynacl paketi) -- secret sifreleme icin
    """
    try:
        from nacl import encoding, public as nacl_public
    except ImportError:
        print(f"[Uploader] WARN PyNaCl kurulu degil, GitHub Secret guncellenemedi: {name}", flush=True)
        return False

    import urllib.request
    import urllib.error

    github_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not github_token:
        print(f"[Uploader] WARN GITHUB_TOKEN bulunamadi, Secret guncellenemedi: {name}", flush=True)
        return False

    repo = os.getenv("GITHUB_REPOSITORY", "trixterx101-web/Evtrix")
    api_base = f"https://api.github.com/repos/{repo}/actions/secrets"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }

    try:
        # 1. Repo public key'ini al (secret sifreleme icin gerekli)
        req = urllib.request.Request(f"{api_base}/public-key", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            pub_key_data = json.loads(r.read())

        pk = nacl_public.PublicKey(pub_key_data["key"].encode(), encoding.Base64Encoder())
        sealed_box = nacl_public.SealedBox(pk)
        encrypted = base64.b64encode(sealed_box.encrypt(value.encode())).decode()

        # 2. Secret'i sifrelenmis degerle guncelle (PUT)
        body = json.dumps({
            "encrypted_value": encrypted,
            "key_id": pub_key_data["key_id"]
        }).encode()
        req2 = urllib.request.Request(
            f"{api_base}/{name}",
            data=body,
            headers=headers,
            method="PUT"
        )
        with urllib.request.urlopen(req2, timeout=15) as r:
            r.read()

        print(f"[Uploader] GitHub Secret otomatik guncellendi: {name}", flush=True)
        return True

    except urllib.error.HTTPError as e:
        body_txt = e.read().decode(errors="replace") if e.fp else ""
        print(f"[Uploader] WARN GitHub Secret guncellenemedi ({name}): HTTP {e.code} -- {body_txt[:200]}", flush=True)
        return False
    except Exception as e:
        print(f"[Uploader] WARN GitHub Secret guncellenemedi ({name}): {e}", flush=True)
        return False


def _save_token_self_healing(creds) -> None:
    """Basarili auth sonrasi token'i hem lokale hem GitHub Secret'a yazar."""
    token_json = creds.to_json()

    # Lokal token.json
    try:
        with open("token.json", "w") as f:
            f.write(token_json)
    except Exception as e:
        print(f"[Uploader] WARN token.json yazilamadi: {e}", flush=True)

    # GitHub Secret'lari guncelle (CI ortaminda)
    if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
        _update_github_secret("YOUTUBE_TOKEN_JSON", token_json)
        if creds.refresh_token:
            _update_github_secret("YOUTUBE_REFRESH_TOKEN", creds.refresh_token)


class YouTubeUploader:
    def __init__(self, client_secrets_file):
        # youtube.force-ssl is REQUIRED for thumbnails().set()
        self.scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.force-ssl"
        ]
        self.client_secrets_file = client_secrets_file
        self.youtube = self.get_authenticated_service()

    def get_authenticated_service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        print("[Uploader] YouTube Uploader baslatiliyor...", flush=True)

        client_id     = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")

        # == Strateji 1: YOUTUBE_TOKEN_JSON (tam token JSON) ==================
        # En guvenilir yontem: tam Credentials JSON'u parse et ve refresh et.
        # Basari olursa self-healing sistemi yeni token'i Secret'a geri yazar.
        token_json_str = os.getenv("YOUTUBE_TOKEN_JSON")
        if token_json_str:
            print("[Uploader] Strateji 1: YOUTUBE_TOKEN_JSON ile auth deneniyor...", flush=True)
            try:
                token_data = json.loads(token_json_str)
                if client_id:
                    token_data["client_id"] = client_id
                if client_secret:
                    token_data["client_secret"] = client_secret
                creds = Credentials.from_authorized_user_info(token_data, self.scopes)
                if creds.expired or not creds.valid:
                    print("[Uploader] Token suresi dolmus, yenileniyor...", flush=True)
                    creds.refresh(Request())
                print("[Uploader] YOUTUBE_TOKEN_JSON ile basariyla auth alindi.", flush=True)
                _save_token_self_healing(creds)
                return build("youtube", "v3", credentials=creds)
            except Exception as e:
                print(f"[Uploader] WARN Strateji 1 basarisiz: {e}", flush=True)

        # == Strateji 2: YOUTUBE_REFRESH_TOKEN ================================
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
        if refresh_token and client_id and client_secret:
            print("[Uploader] Strateji 2: YOUTUBE_REFRESH_TOKEN ile auth deneniyor...", flush=True)
            try:
                creds = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=self.scopes,
                )
                creds.refresh(Request())
                print("[Uploader] YOUTUBE_REFRESH_TOKEN ile basariyla auth alindi.", flush=True)
                _save_token_self_healing(creds)
                return build("youtube", "v3", credentials=creds)
            except Exception as e:
                print(f"[Uploader] WARN Strateji 2 basarisiz: {e}", flush=True)

        # == Strateji 3: Yerel token.json =====================================
        token_file = "token.json"
        if os.path.exists(token_file):
            print("[Uploader] Strateji 3: Yerel token.json ile auth deneniyor...", flush=True)
            try:
                creds = Credentials.from_authorized_user_file(token_file, self.scopes)
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                if creds.valid:
                    print("[Uploader] token.json ile basariyla auth alindi.", flush=True)
                    _save_token_self_healing(creds)
                    return build("youtube", "v3", credentials=creds)
            except Exception as e:
                print(f"[Uploader] WARN Strateji 3 basarisiz: {e}", flush=True)

        # == CI ortaminda tum stratejiler basarisiz ============================
        if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
            print("[Uploader] CI: Tum auth stratejileri basarisiz!", flush=True)
            print("[Uploader]    YOUTUBE_TOKEN_JSON, YOUTUBE_REFRESH_TOKEN veya token.json gerekli.", flush=True)
            return None

        # == Strateji 4: Lokal OAuth flow (browser) ===========================
        if not self.client_secrets_file or not os.path.exists(self.client_secrets_file):
            print(f"[Uploader] client_secrets_file bulunamadi: {self.client_secrets_file}", flush=True)
            return None
        print("[Uploader] Strateji 4: Tarayici uzerinden OAuth baslatiliyor...", flush=True)
        flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_file, self.scopes)
        creds = flow.run_local_server(port=0)
        if creds:
            _save_token_self_healing(creds)
            return build("youtube", "v3", credentials=creds)
        return None

    def upload_video(self, file_path, title, description, tags, category_id="28", max_retries=3,
                  playlist_name: str = None, thumbnail_path: str = None, topic: str = "", is_long: bool = False):
        """Videoyu YouTube'a yÃ¼kler.
        Category 28 = Science & Technology (EV + AI iÃ§eriÄŸi iÃ§in en uygun)
        503/500 transient sunucu hatalarÄ±nda exponential backoff ile retry yapar.
        """
        from googleapiclient.errors import ResumableUploadError
        # KURAL 2: Title sanitization
        clean_title = title.replace("&amp;", "&").replace("&AMP;", "&").strip()
        if clean_title.isupper():
            clean_title = clean_title.title()
        if len(clean_title) > 100:
            clean_title = clean_title[:97] + "..."

        # KURAL 3: Universal Tag List + Long/Short Tag Rules
        UNIVERSAL_TAGS = [
            "electric vehicle", "EV", "battery technology", "EV range", "electric car",
            "Evcarix", "EV data", "EV future", "fast charging", "EV charging",
            "ev range loss", "EV technology", "clean energy", "sustainable energy",
            "electric vehicle data", "battery degradation", "EV market", "lfp battery",
            "solid state battery", "electric car range", "EV industry", "ev battery",
            "EV data analysis", "electric vehicles 2026", "EV vs gas", "battery cost"
        ]

        # Tag haznesi oluÅŸtur
        final_tags = list(UNIVERSAL_TAGS)
        if tags:
            for t in tags:
                if t and t not in final_tags:
                    final_tags.append(t)

        # Video sÃ¼resi / Tipi 60sn Ã¼stÃ¼ndeyse Shorts/EVShorts YASAK (KURAL 3)
        if is_long or playlist_name == "EV Data Reports":
            forbidden_short_tags = {"shorts", "evshorts", "#shorts", "#evshorts", "shortsvideo"}
            final_tags = [t for t in final_tags if str(t).lower() not in forbidden_short_tags]
            # AÃ§Ä±klamadan da #Shorts / #EVShorts temizle
            description = re.sub(r'#(Shorts|EVShorts|shorts|evshorts)\b', '', description).strip()
        elif playlist_name == "Short Video" or not is_long:
            for must_have in ["Shorts", "EVShorts"]:
                if must_have not in final_tags:
                    final_tags.append(must_have)

        # YouTube tag gereksinimleri: Her tag max 30 char, toplam max 500 char
        cleaned_tags = []
        for tag in final_tags:
            # 1. Newline ve tab'larÄ± boÅŸluÄŸa Ã§evir
            clean = re.sub(r'[\r\n\t]', ' ', str(tag))
            # 2. Sadece harf, rakam, boÅŸluk ve tireye izin ver (virgÃ¼l, <, > vs sil)
            clean = re.sub(r'[^a-zA-Z0-9 \-]', '', clean)
            # 3. Birden fazla boÅŸluÄŸu teke dÃ¼ÅŸÃ¼r ve saÄŸ/sol boÅŸluklarÄ± sil
            clean = re.sub(r'\s+', ' ', clean).strip()
            
            if len(clean) >= 2 and len(clean) <= 30:
                # KÃ¼Ã§Ã¼k harfe Ã§evirerek mÃ¼kerrer kontrolÃ¼ yap
                if clean.lower() not in [t.lower() for t in cleaned_tags]:
                    cleaned_tags.append(clean)

        # Toplam karakter limiti kontrol (max 500 char)
        # YouTube virgÃ¼ller de dahil olmak Ã¼zere toplam uzunluÄŸu sayar
        while cleaned_tags:
            total_chars = sum(len(t) for t in cleaned_tags) + len(cleaned_tags) - 1
            if total_chars > 495:
                cleaned_tags.pop()
            else:
                break

        # YouTube bazen fazla veya belirli tag kombinasyonlarina invalidTags 400 verir.
        # Guvenlik icin temiz ve az sayida (max 12) tag kullanalim.
        final_tags = cleaned_tags[:12]

        body = {
            "snippet": {
                "title": clean_title,
                "description": description,
                "tags": final_tags,
                "categoryId": category_id,
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,   # Zorunlu: YPP baÅŸvurusu iÃ§in False olmalÄ±
                "madeForKids": False,                # Zorunlu: YPP baÅŸvurusu iÃ§in False olmalÄ±
                "embeddable": True,                  # Videolar gÃ¶mÃ¼lebilsin (izlenme artÄ±rÄ±r)
                "publicStatsViewable": True,         # Ä°zlenme sayÄ±sÄ± herkese gÃ¶rÃ¼nsÃ¼n
                "notifySubscribers": True,           # Abone bildirimi (engagement artÄ±rÄ±r)
            }
        }

        for attempt in range(1, max_retries + 1):
            try:
                print(f"Video yÃ¼kleniyor (deneme {attempt}/{max_retries}): {file_path}...")
                media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
                request = self.youtube.videos().insert(
                    part="snippet,status",
                    body=body,
                    media_body=media
                )
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        print(f"YÃ¼kleniyor: %{int(status.progress() * 100)}")
                print(f"YÃ¼kleme TamamlandÄ±! Video ID: {response['id']}")
                video_id = response['id']
                
                # Gizlilik ve yÃ¼kleme durumu kontrolÃ¼
                status_info = response.get("status", {})
                privacy = status_info.get("privacyStatus", "unknown")
                upload_status = status_info.get("uploadStatus", "unknown")
                print(f"[Uploader] ğŸ“Œ Gizlilik Durumu: {privacy}", flush=True)
                print(f"[Uploader] ğŸ“Œ YÃ¼kleme Durumu : {upload_status}", flush=True)

                if privacy == "private":
                    print("âš ï¸ UYARI: YouTube bu videoyu 'Gizli' (Private) olarak kilitledi!", flush=True)
                    print("   Neden: Google Cloud Console'da OAuth Consent Screen 'Testing' modunda olduÄŸu", flush=True)
                    print("   veya API uygulamasÄ± henÃ¼z doÄŸrulanmadÄ±ÄŸÄ± iÃ§in YouTube API yÃ¼klemeleri otomatik Gizli'ye Ã§eker.", flush=True)
                    print(f"   ğŸ‘‰ Videoyu yayÄ±na almak iÃ§in: https://studio.youtube.com/video/{video_id}/edit -> Gizlilik -> Herkese AÃ§Ä±k yapÄ±n.", flush=True)
                
                # Add to playlist if specified
                if playlist_name and video_id:
                    try:
                        playlist_id = self._get_or_create_playlist(playlist_name)
                        if playlist_id:
                            self.youtube.playlistItems().insert(
                                part="snippet",
                                body={
                                    "snippet": {
                                        "playlistId": playlist_id,
                                        "resourceId": {
                                            "kind": "youtube#video",
                                            "videoId": video_id,
                                        }
                                    }
                                }
                            ).execute()
                            print(f"[Uploader] OK Playlist'e eklendi: {playlist_name}")
                    except Exception as e:
                        print(f"[Uploader] WARN Playlist hatasi (devam ediliyor): {e}")
                
                # Upload thumbnail if specified
                if thumbnail_path and video_id and os.path.exists(thumbnail_path):
                    self.set_thumbnail(video_id, thumbnail_path)

                # Post first comment for engagement signal
                self.post_first_comment(video_id, topic=topic, is_long=is_long)
                
                return video_id
            except (HttpError, ResumableUploadError) as e:
                err_str = str(e)
                if "invalidTags" in err_str or "invalid video keywords" in err_str:
                    print("[Uploader] WARN: YouTube tagleri reddetti (invalidTags). Tagler sadelestirilerek tekrar deneniyor...", flush=True)
                    body["snippet"]["tags"] = ["EV", "Electric Vehicles", "Evcarix"]
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                if "503" in err_str or "500" in err_str or "Service Unavailable" in err_str:
                    if attempt < max_retries:
                        wait = 30 * (2 ** (attempt - 1))
                        print(f"YouTube 503/500 hatasÄ±, {wait}s sonra tekrar deneniyor...")
                        time.sleep(wait)
                    else:
                        raise
                else:
                    raise

    def _get_or_create_playlist(self, playlist_name: str) -> str | None:
        """Return playlist_id for given name, creating it if it doesn't exist."""
        try:
            # Search existing playlists
            response = self.youtube.playlists().list(
                part="snippet",
                mine=True,
                maxResults=50
            ).execute()
            for item in response.get("items", []):
                if item["snippet"]["title"] == playlist_name:
                    return item["id"]
            # Not found â€” create it
            created = self.youtube.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": playlist_name,
                        "description": f"Evcarix â€” {playlist_name}",
                    },
                    "status": {"privacyStatus": "public"}
                }
            ).execute()
            pid = created["id"]
            print(f"[Uploader] OK Yeni playlist olusturuldu: {playlist_name} ({pid})")
            return pid
        except Exception as e:
            print(f"[Uploader] WARN Playlist bulunamadi/olusturulamadi: {e}")
            return None

    def post_first_comment(self, video_id: str, topic: str = "", is_long: bool = False) -> bool:
        """Upload sonrasi videonun altina ilk yorum yap. Engagement sinyali uretir.
        Konu bazli, dikkat cekici ve yorum almaya optimize edilmis yorumlar kullanir.
        """
        import random
        import time
        clean_topic = topic.replace("_", " ").title() if topic else "this EV topic"

        if is_long:
            # Uzun videolar icin: derinlemesine, tartisma yaratan yorumlar
            COMMENTS = [
                f"ğŸ”¥ Hot take: {clean_topic} is the most misunderstood topic in EVs right now. What do YOU think is the biggest misconception? Drop it below â€” best comment gets pinned! ğŸ‘‡",
                f"ğŸ“Š We spent days analyzing the real data behind {clean_topic}. One stat completely changed our perspective. Did any number in this video surprise YOU? Tell us below! ğŸ’¬",
                f"âš¡ EV owners & enthusiasts: after watching this deep-dive on {clean_topic} â€” what's your verdict? Game-changer or overhyped? Reply below, we read EVERY comment! ğŸ”½",
                f"ğŸŒ USA vs Europe vs China: where do you think the {clean_topic} situation is heading in the next 3 years? Cast your vote in the comments! We'll feature the top responses. ğŸ‘‡",
                f"ğŸ’¡ This video took weeks of data research to produce. If {clean_topic} affects your EV buying decision â€” HOW? Share your real-world experience below! ğŸš—âš¡",
                f"ğŸ¤” Controversial question: Is {clean_topic} actually GOOD or BAD for EV adoption long-term? Serious answers only â€” best argument gets featured in our next video! ğŸ“Œ",
                f"ğŸ“Œ PINNED: What's the ONE thing about {clean_topic} that most people completely ignore? Drop your insight below â€” we genuinely want to know what our community thinks! ğŸ’¬",
                f"ğŸš€ If you watched until the end â€” you're already ahead of 99% of EV discussions happening online. What was YOUR biggest takeaway about {clean_topic}? Comment below! â¬‡ï¸",
            ]
        else:
            # Shorts icin: hizli, kisa, aninda yorum ceken sorular
            COMMENTS = [
                f"âš¡ Which number about {clean_topic} shocked you the most? Comment fast â€” we pin the best replies! ğŸ‘‡",
                f"ğŸ”¥ Did you know THIS about {clean_topic}? Comment your reaction â€” we read everything! ğŸ’¬",
                f"ğŸš— EV owners: is the {clean_topic} data accurate to YOUR real experience? Tell us in 1 sentence! ğŸ‘‡",
                f"ğŸ“Š Agree or disagree with these {clean_topic} numbers? Drop your take below! Best comment gets pinned ğŸ“Œ",
                f"ğŸ’¡ Quick poll: Does the {clean_topic} data change how you see EVs? YES or NO below! ğŸ‘‡",
                f"ğŸŒ USA, Europe, or China â€” who handles {clean_topic} best? Comment your answer! â¬‡ï¸",
                f"âš¡ What's the ONE thing about {clean_topic} that most people get WRONG? Drop it below! ğŸ”½",
                f"ğŸ”‹ Real talk â€” is {clean_topic} a dealbreaker for YOUR EV decision? Comment your honest take! ğŸ’¬",
            ]

        comment_text = random.choice(COMMENTS)
        try:
            time.sleep(12)  # YouTube'un video indeksleme suresi icin kisa bekleme
            self.youtube.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {
                            "snippet": {"textOriginal": comment_text}
                        }
                    }
                }
            ).execute()
            print(f"[Uploader] âœ… First comment posted: {comment_text[:80]}...")
            return True
        except Exception as e:
            print(f"[Uploader] Comment skipped (non-fatal): {e}")
            return False

    def set_thumbnail(self, video_id, thumbnail_path, max_retries=4):
        """Video iÃ§in kapak gÃ¶rselini yÃ¼kler â€” YouTube processing sÃ¼resi iÃ§in exponential backoff retry."""
        if not os.path.exists(thumbnail_path):
            print(f"Hata: Thumbnail dosyasÄ± bulunamadÄ±: {thumbnail_path}")
            return False

        for attempt in range(1, max_retries + 1):
            try:
                print(f"Thumbnail yÃ¼kleniyor (deneme {attempt}/{max_retries}): {thumbnail_path}...")
                request = self.youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path)
                )
                request.execute()
                print("Thumbnail basariyla guncellendi!")
                return True
            except HttpError as e:
                status = e.resp.status
                error_details = e._get_reason() if hasattr(e, '_get_reason') else str(e)
                print(f"Thumbnail yÃ¼kleme hatasÄ± HTTP {status}: {error_details}")
                if status == 403 and "insufficientPermissions" in str(e):
                    print("  -> youtube.force-ssl scope eksik olabilir. Token'i yenileyin.")
                    print("  -> refresh_token.py calistirip yeni token.json uretin.")
                    return False
                # 400 Bad Request = video henuz islenmemis olabilir
                if status == 400:
                    print("  -> Video henuz YouTube tarafindan islenmemis olabilir.")
                if attempt < max_retries:
                    # Exponential backoff: 30, 60, 120, 240 saniye
                    wait = 30 * (2 ** (attempt - 1))
                    print(f"  -> {wait} saniye sonra tekrar deneniyor...")
                    time.sleep(wait)
                else:
                    print("  -> Tum denemeler basarisiz. Thumbnail yuklenemedi.")
            except Exception as e:
                print(f"Thumbnail yÃ¼kleme hatasÄ± (deneme {attempt}): {e}")
                if attempt < max_retries:
                    wait = 30 * (2 ** (attempt - 1))
                    print(f"  -> {wait} saniye sonra tekrar deneniyor...")
                    time.sleep(wait)
        return False

if __name__ == "__main__":
    # uploader = YouTubeUploader("client_secret.json")
    # uploader.upload_video("output/test.mp4", "Test BaÅŸlÄ±k", "Test AÃ§Ä±klama", ["ev", "car"])
    pass
