"""
get_token.py — YouTube OAuth Token Al + Kanal Seç
Hesaptaki tüm kanalları listeler, seçim yapmanı sağlar.
"""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

print("=" * 60)
print("  Evcarix — YouTube Token Yenileme + Kanal Seçimi")
print("=" * 60)
print()
print("Tarayici aciliyor... Google hesabinizla giris yapin.")
print()

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0, prompt="consent")

# Tüm kanalları listele
youtube = build("youtube", "v3", credentials=creds)

print("\nHesabinizdaki kanallar aranıyor...\n")

channels = []

# Ana kanal
resp = youtube.channels().list(part="snippet", mine=True).execute()
for item in resp.get("items", []):
    channels.append({
        "id": item["id"],
        "title": item["snippet"]["title"],
        "type": "Ana Kanal"
    })

# Marka hesapları
try:
    resp2 = youtube.channels().list(
        part="snippet", managedByMe=True, maxResults=50
    ).execute()
    for item in resp2.get("items", []):
        if not any(c["id"] == item["id"] for c in channels):
            channels.append({
                "id": item["id"],
                "title": item["snippet"]["title"],
                "type": "Marka Hesabı"
            })
except Exception:
    pass

if not channels:
    print("HATA: Hic kanal bulunamadi!")
    sys.exit(1)

# Kanalları göster
print("-" * 60)
print(f"  {'#':<4} {'Kanal Adı':<30} {'Tür':<15} Kanal ID")
print("-" * 60)
for i, ch in enumerate(channels, 1):
    print(f"  {i:<4} {ch['title']:<30} {ch['type']:<15} {ch['id']}")
print("-" * 60)
print()

# Seçim
if len(channels) == 1:
    selected = channels[0]
    print(f"Tek kanal bulundu, otomatik secildi: {selected['title']}")
else:
    while True:
        try:
            choice = int(input(f"Hangi kanala yuklensin? (1-{len(channels)}): "))
            if 1 <= choice <= len(channels):
                selected = channels[choice - 1]
                break
            else:
                print(f"Lutfen 1 ile {len(channels)} arasinda bir sayi girin.")
        except ValueError:
            print("Gecersiz giris. Bir sayi girin.")

print(f"\nSecilen kanal: {selected['title']} ({selected['id']})")

# token.json kaydet
with open("token.json", "w") as f:
    f.write(creds.to_json())

# .env guncelle
env_path = ".env"
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    import re
    if "CHANNEL_ID=" in content:
        content = re.sub(r"CHANNEL_ID=.*", f"CHANNEL_ID={selected['id']}", content)
    else:
        content += f"\nCHANNEL_ID={selected['id']}\n"
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)

print()
print("=" * 60)
print(f"  BASARI!")
print(f"  Kanal : {selected['title']}")
print(f"  ID    : {selected['id']}")
print("=" * 60)
print()
print("GitHub Secret icin token.json icerigi:")
print("-" * 40)
with open("token.json", "r") as f:
    print(f.read())
print("-" * 40)
print(f"CHANNEL_ID = {selected['id']}")
print()
print("Bitti! GitHub'i guncellememi soyle.")
