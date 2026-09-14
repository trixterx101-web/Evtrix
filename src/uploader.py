import os
import re
import time
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

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

        # ── CI/GitHub Actions: refresh_token secret'tan kimlik doğrula ───────
        # Bu yöntem token.json'a bağımlı değil, access token süresi dolsa bile çalışır
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
        client_id     = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")

        if (os.getenv("CI") or os.getenv("GITHUB_ACTIONS")) and refresh_token and client_id and client_secret:
            print("[Uploader] CI mode: refresh_token secret kullanılıyor...", flush=True)
            try:
                creds = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=self.scopes,
                )
                # Token'ı hemen yenile (access token al)
                creds.refresh(Request())
                print("[Uploader] ✅ Token refresh_token ile başarıyla alındı.", flush=True)
                return build("youtube", "v3", credentials=creds)
            except Exception as e:
                print(f"[Uploader] WARN refresh_token ile kimlik doğrulama başarısız: {e}", flush=True)
                print("[Uploader] token.json ile devam deneniyor...", flush=True)

        # ── Yerel / token.json tabanlı kimlik doğrulama ──────────────────────
        creds      = None
        token_file = "token.json"

        if os.path.exists(token_file):
            try:
                creds = Credentials.from_authorized_user_file(token_file, self.scopes)
            except Exception as e:
                print(f"[Uploader] WARN token.json okunamadı: {e}", flush=True)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[Uploader] Token süresi dolmuş, yenileniyor...", flush=True)
                try:
                    creds.refresh(Request())
                    print("[Uploader] ✅ Token başarıyla yenilendi.", flush=True)
                except Exception as e:
                    print(f"[Uploader] WARN Token yenileme hatası: {e}", flush=True)
                    if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
                        print("[Uploader] ❌ CI: Yeni token.json üretin ve GitHub Secret'a ekleyin.", flush=True)
                        return None
                    creds = None

            if not creds or not creds.valid:
                if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
                    print("[Uploader] ❌ CI: Geçerli kimlik bilgisi yok. YOUTUBE_REFRESH_TOKEN secret'ını kontrol edin.", flush=True)
                    return None
                print("[Uploader] Tarayıcı üzerinden giriş bekleniyor...", flush=True)
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_file, self.scopes)
                creds = flow.run_local_server(port=0)

        if not creds:
            return None

        try:
            with open(token_file, "w") as token:
                token.write(creds.to_json())
        except Exception as e:
            print(f"[Uploader] WARN token.json yazılamadı: {e}", flush=True)

        try:
            return build("youtube", "v3", credentials=creds)
        except Exception as e:
            print(f"[Uploader] ❌ YouTube servisi oluşturulamadı: {e}", flush=True)
            return None


    def upload_video(self, file_path, title, description, tags, category_id="28", max_retries=3,
                  playlist_name: str = None, thumbnail_path: str = None, topic: str = "", is_long: bool = False):
        """Videoyu YouTube'a yükler.
        Category 28 = Science & Technology (EV + AI içeriği için en uygun)
        503/500 transient sunucu hatalarında exponential backoff ile retry yapar.
        """
        from googleapiclient.errors import ResumableUploadError
        # Title shortening if needed
        shorts_title = title[:97] if len(title) > 97 else title
        
        # Tags listesine Shorts ekle (Sadece Shorts playlisti ise)
        final_tags = list(tags) if tags else []
        if playlist_name == "Short Video":
            for must_have in ["Shorts", "EVShorts", "ElectricCarShorts"]:
                if must_have not in final_tags:
                    final_tags.append(must_have)

        # YouTube tag gereksinimleri:
        # - Her tag en az 2 karakter, max 30 karakter
        # - Toplam max 500 karakter
        cleaned_tags = []
        for tag in final_tags:
            # Boşluklara ve tirelere izin ver (SEO için önemli), diğer özel karakterleri temizle
            clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', str(tag)).strip()
            if len(clean) >= 2 and len(clean) <= 30:
                cleaned_tags.append(clean)

        # Toplam karakter limiti kontrol
        total_chars = sum(len(t) + 1 for t in cleaned_tags)
        while total_chars > 500 and cleaned_tags:
            cleaned_tags.pop()
            total_chars = sum(len(t) + 1 for t in cleaned_tags)

        final_tags = cleaned_tags[:40]  # Max 40 tag (YouTube limiti ~500 char)

        body = {
            "snippet": {
                "title": shorts_title,
                "description": description,
                "tags": final_tags,
                "categoryId": category_id,
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,   # Zorunlu: YPP başvurusu için False olmalı
                "madeForKids": False,                # Zorunlu: YPP başvurusu için False olmalı
                "embeddable": True,                  # Videolar gömülebilsin (izlenme artırır)
                "publicStatsViewable": True,         # İzlenme sayısı herkese görünsün
                "notifySubscribers": True,           # Abone bildirimi (engagement artırır)
            }
        }

        for attempt in range(1, max_retries + 1):
            try:
                print(f"Video yükleniyor (deneme {attempt}/{max_retries}): {file_path}...")
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
                        print(f"Yükleniyor: %{int(status.progress() * 100)}")
                print(f"Yükleme Tamamlandı! Video ID: {response['id']}")
                video_id = response['id']
                
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
                if "503" in err_str or "500" in err_str or "Service Unavailable" in err_str:
                    if attempt < max_retries:
                        wait = 30 * (2 ** (attempt - 1))
                        print(f"YouTube 503/500 hatası, {wait}s sonra tekrar deneniyor...")
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
            # Not found — create it
            created = self.youtube.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": playlist_name,
                        "description": f"Evcarix — {playlist_name}",
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
                f"🔥 Hot take: {clean_topic} is the most misunderstood topic in EVs right now. What do YOU think is the biggest misconception? Drop it below — best comment gets pinned! 👇",
                f"📊 We spent days analyzing the real data behind {clean_topic}. One stat completely changed our perspective. Did any number in this video surprise YOU? Tell us below! 💬",
                f"⚡ EV owners & enthusiasts: after watching this deep-dive on {clean_topic} — what's your verdict? Game-changer or overhyped? Reply below, we read EVERY comment! 🔽",
                f"🌍 USA vs Europe vs China: where do you think the {clean_topic} situation is heading in the next 3 years? Cast your vote in the comments! We'll feature the top responses. 👇",
                f"💡 This video took weeks of data research to produce. If {clean_topic} affects your EV buying decision — HOW? Share your real-world experience below! 🚗⚡",
                f"🤔 Controversial question: Is {clean_topic} actually GOOD or BAD for EV adoption long-term? Serious answers only — best argument gets featured in our next video! 📌",
                f"📌 PINNED: What's the ONE thing about {clean_topic} that most people completely ignore? Drop your insight below — we genuinely want to know what our community thinks! 💬",
                f"🚀 If you watched until the end — you're already ahead of 99% of EV discussions happening online. What was YOUR biggest takeaway about {clean_topic}? Comment below! ⬇️",
            ]
        else:
            # Shorts icin: hizli, kisa, aninda yorum ceken sorular
            COMMENTS = [
                f"⚡ Which number about {clean_topic} shocked you the most? Comment fast — we pin the best replies! 👇",
                f"🔥 Did you know THIS about {clean_topic}? Comment your reaction — we read everything! 💬",
                f"🚗 EV owners: is the {clean_topic} data accurate to YOUR real experience? Tell us in 1 sentence! 👇",
                f"📊 Agree or disagree with these {clean_topic} numbers? Drop your take below! Best comment gets pinned 📌",
                f"💡 Quick poll: Does the {clean_topic} data change how you see EVs? YES or NO below! 👇",
                f"🌍 USA, Europe, or China — who handles {clean_topic} best? Comment your answer! ⬇️",
                f"⚡ What's the ONE thing about {clean_topic} that most people get WRONG? Drop it below! 🔽",
                f"🔋 Real talk — is {clean_topic} a dealbreaker for YOUR EV decision? Comment your honest take! 💬",
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
            print(f"[Uploader] ✅ First comment posted: {comment_text[:80]}...")
            return True
        except Exception as e:
            print(f"[Uploader] Comment skipped (non-fatal): {e}")
            return False

    def set_thumbnail(self, video_id, thumbnail_path, max_retries=4):
        """Video için kapak görselini yükler — YouTube processing süresi için exponential backoff retry."""
        if not os.path.exists(thumbnail_path):
            print(f"Hata: Thumbnail dosyası bulunamadı: {thumbnail_path}")
            return False

        for attempt in range(1, max_retries + 1):
            try:
                print(f"Thumbnail yükleniyor (deneme {attempt}/{max_retries}): {thumbnail_path}...")
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
                print(f"Thumbnail yükleme hatası HTTP {status}: {error_details}")
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
                print(f"Thumbnail yükleme hatası (deneme {attempt}): {e}")
                if attempt < max_retries:
                    wait = 30 * (2 ** (attempt - 1))
                    print(f"  -> {wait} saniye sonra tekrar deneniyor...")
                    time.sleep(wait)
        return False

if __name__ == "__main__":
    # uploader = YouTubeUploader("client_secret.json")
    # uploader.upload_video("output/test.mp4", "Test Başlık", "Test Açıklama", ["ev", "car"])
    pass
