"""
refresh_token.py — YouTube kanalı seçimi ve token yenileme aracı.
Aynı Google hesabındaki birden fazla kanal arasından seçim yapmanızı sağlar.
Kullanım: python refresh_token.py
"""

import os
import re
import json
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Opera'yi varsayilan tarayici olarak kaydet
_OPERA_PATH = r"C:\Users\Anonim\AppData\Local\Programs\Opera\opera.exe"
if os.path.exists(_OPERA_PATH):
    webbrowser.register("opera", None, webbrowser.BackgroundBrowser(_OPERA_PATH), preferred=True)

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = "token.json"
ENV_FILE = ".env"


def list_all_channels(youtube):
    """Hesaptaki tüm kanalları (ana + marka hesapları) listeler."""
    channels = []

    # Ana kanal
    resp = youtube.channels().list(part="snippet", mine=True).execute()
    for item in resp.get("items", []):
        channels.append({
            "id": item["id"],
            "title": item["snippet"]["title"],
            "type": "Ana Kanal"
        })

    # Marka hesapları (brand accounts)
    try:
        resp2 = youtube.channels().list(
            part="snippet",
            managedByMe=True,
            maxResults=50
        ).execute()
        for item in resp2.get("items", []):
            if not any(c["id"] == item["id"] for c in channels):
                channels.append({
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "type": "Marka Hesabı"
                })
    except Exception:
        pass  # managedByMe bazı hesaplarda desteklenmez

    return channels


def update_env(channel_id: str):
    """CHANNEL_ID'yi .env dosyasında günceller veya ekler."""
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(f"CHANNEL_ID={channel_id}\n")
        print(f"✅ .env oluşturuldu, CHANNEL_ID={channel_id}")
        return

    with open(ENV_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "CHANNEL_ID=" in content:
        content = re.sub(r"CHANNEL_ID=.*", f"CHANNEL_ID={channel_id}", content)
        print(f"✅ .env güncellendi → CHANNEL_ID={channel_id}")
    else:
        content += f"\nCHANNEL_ID={channel_id}\n"
        print(f"✅ .env'e eklendi → CHANNEL_ID={channel_id}")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    print("=" * 60)
    print("  Evtrix — YouTube Kanal Değiştirme Aracı")
    print("=" * 60)

    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"\n❌ HATA: '{CLIENT_SECRET_FILE}' bulunamadı!")
        print("Google Cloud Console'dan OAuth 2.0 JSON dosyasını indirip")
        print(f"'{CLIENT_SECRET_FILE}' adıyla bu klasöre kaydedin.")
        return

    print(f"\n✅ '{CLIENT_SECRET_FILE}' bulundu.")
    print("🌐 Tarayıcı açılıyor — Google hesabınızla giriş yapın...\n")

    # Eski token.json varsa sil (temiz başlangıç)
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
        print(f"🗑️  Eski '{TOKEN_FILE}' silindi.\n")

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)

    print("\n" + "="*60)
    print("  ADIM 1: Asagidaki URL'yi kopyalayip tarayiciniza yapistirin")
    print("          (Opera, Chrome veya Gizli Sekme kullanabilirsiniz)")
    print("          mrt1122336@gmail.com hesabiyla giris yapin.")
    print("="*60 + "\n")

    creds = flow.run_local_server(
        port=0,
        open_browser=False,
        prompt="consent"
    )


    youtube = build("youtube", "v3", credentials=creds)

    # Kanalları listele
    print("\n📺 Hesabınızdaki kanallar aranıyor...")
    channels = list_all_channels(youtube)

    if not channels:
        print("❌ Hiç kanal bulunamadı!")
        return

    print(f"\n{'─'*50}")
    print(f"  {'#':<4} {'Kanal Adı':<30} {'Tür':<15} {'Kanal ID'}")
    print(f"{'─'*50}")
    for i, ch in enumerate(channels, 1):
        print(f"  {i:<4} {ch['title']:<30} {ch['type']:<15} {ch['id']}")
    print(f"{'─'*50}\n")

    # Kullanıcıdan seçim al
    if len(channels) == 1:
        selected = channels[0]
        print(f"Tek kanal bulundu, otomatik seçildi: {selected['title']}")
    else:
        while True:
            try:
                choice = int(input(f"Hangi kanala yüklensin? (1-{len(channels)}): "))
                if 1 <= choice <= len(channels):
                    selected = channels[choice - 1]
                    break
                else:
                    print(f"Lütfen 1 ile {len(channels)} arasında bir sayı girin.")
            except ValueError:
                print("Geçersiz giriş. Bir sayı girin.")

    print(f"\n✅ Seçilen kanal: {selected['title']} ({selected['id']})")

    # token.json kaydet
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    print(f"✅ '{TOKEN_FILE}' kaydedildi.")

    # .env güncelle
    update_env(selected["id"])

    print("\n" + "=" * 60)
    print("  ✅ Tamamlandı! Artık videolar şu kanala yüklenecek:")
    print(f"     {selected['title']}")
    print(f"     ID: {selected['id']}")
    print("=" * 60)

    print("\n📌 GitHub Actions kullanıyorsanız:")
    print("   1. token.json içeriğini kopyalayın")
    print("   → GitHub repo → Settings → Secrets → YOUTUBE_TOKEN_JSON güncelle")
    print(f"   2. CHANNEL_ID={selected['id']} → Secrets'a ekleyin")

    # token.json içeriğini ekrana bas (GitHub için kopyalamak kolay olsun)
    print("\n📋 token.json içeriği (GitHub Secret için):")
    print("─" * 40)
    with open(TOKEN_FILE, "r") as f:
        print(f.read())
    print("─" * 40)


if __name__ == "__main__":
    main()
