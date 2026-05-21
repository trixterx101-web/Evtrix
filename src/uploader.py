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
        
        creds = None
        token_file = "token.json"
        
        # token.json dosyası varsa yükle
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, self.scopes)
        
        # Eğer geçerli kimlik bilgisi yoksa veya süresi dolmuşsa yenile/oluştur
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[Uploader] Token süresi dolmuş, yenileniyor...", flush=True)
                try:
                    creds.refresh(Request())
                    print("[Uploader] ✅ Token başarıyla yenilendi.", flush=True)
                except Exception as e:
                    print(f"[Uploader] ❌ Token yenileme hatası: {e}", flush=True)
                    if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
                        print("[Uploader] 🔑 Lütfen yerelinizde giriş yapıp yeni token.json içeriğini GitHub Secret'a (YOUTUBE_TOKEN_JSON) ekleyin.", flush=True)
                        return None
                    else:
                        print("[Uploader] 🔄 Yenileme başarısız, sıfırdan giriş denenecek...", flush=True)
                        creds = None # Reset creds to trigger flow below
            
            if not creds or not creds.valid:
                # CI/CD ortamında tarayıcı açılamaz
                if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
                    print("[Uploader] ❌ Gerekli token.json bulunamadı veya geçersiz!", flush=True)
                    return None
                
                print("[Uploader] 🔑 Tarayıcı üzerinden giriş yapılması bekleniyor...", flush=True)
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_file, self.scopes)
                creds = flow.run_local_server(port=0)
        
        if not creds:
            return None
            
            # Gelecek kullanım için sakla
        if not creds:
            return None
            
        try:
            with open(token_file, "w") as token:
                token.write(creds.to_json())
        except Exception as e:
            print(f"[Uploader] ⚠️ token.json yazılamadı: {e}", flush=True)
        
        try:
            return build("youtube", "v3", credentials=creds)
        except Exception as e:
            print(f"[Uploader] ❌ YouTube servisi oluşturulamadı: {e}", flush=True)
            return None

    def upload_video(self, file_path, title, description, tags, category_id="28", max_retries=3,
                  playlist_name: str = None, thumbnail_path: str = None):
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
                "selfDeclaredMadeForKids": False,
                "madeForKids": False
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
                            print(f"[Uploader] ✅ Playlist'e eklendi: {playlist_name}")
                    except Exception as e:
                        print(f"[Uploader] ⚠️ Playlist hatası (devam ediliyor): {e}")
                
                # Upload thumbnail if specified
                if thumbnail_path and video_id and os.path.exists(thumbnail_path):
                    # Use set_thumbnail for reliable retries (important for long videos)
                    self.set_thumbnail(video_id, thumbnail_path)
                
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
                        "description": f"Evtrix — {playlist_name}",
                    },
                    "status": {"privacyStatus": "public"}
                }
            ).execute()
            pid = created["id"]
            print(f"[Uploader] ✅ Yeni playlist oluşturuldu: {playlist_name} ({pid})")
            return pid
        except Exception as e:
            print(f"[Uploader] ⚠️ Playlist bulunamadı/oluşturulamadı: {e}")
            return None

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
                print("Thumbnail başarıyla güncellendi!")
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
                    print("  -> Tüm denemeler başarısız. Thumbnail yüklenemedi.")
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
