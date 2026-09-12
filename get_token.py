"""
get_token.py — YouTube OAuth Token Al (Basit)
Tarayıcıyı otomatik açar, izin ver, token.json kaydeder.
"""
import json
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

print("=" * 60)
print("  Evcarix — YouTube Token Yenileme")
print("=" * 60)
print()
print("Tarayici aciliyor... Google hesabinizla giris yapin.")
print("Hesap: mrt1122336@gmail.com")
print()

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)

# Tarayıcıyı otomatik aç, rastgele port kullan
creds = flow.run_local_server(port=0, prompt="consent")

# token.json kaydet
with open("token.json", "w") as f:
    f.write(creds.to_json())

print()
print("=" * 60)
print("  BASARI! token.json kaydedildi.")
print("=" * 60)
print()
print("GitHub Secret icin token.json icerigi:")
print("-" * 40)
with open("token.json", "r") as f:
    content = f.read()
    print(content)
print("-" * 40)
print()
print("Simdi yapman gerekenler:")
print("1. Yukaridaki JSON'u kopyala")
print("2. GitHub -> Settings -> Secrets -> YOUTUBE_TOKEN_JSON -> guncelle")
print("3. CHANNEL_ID = UCxu6aSGjzpGZfiYcxFGYKkw olarak ayarla")
print()
print("Bitti!")
