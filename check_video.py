"""
Evcarix — Video Yayinlama Oncesi Tam Kontrol
Kullanim: python3 check_video.py
"""

import subprocess
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))


def run_validator(script_rel, args=""):
    path = os.path.join(project_root, script_rel)
    result = subprocess.run(
        [sys.executable, path] + (args.split() if args else []),
        capture_output=True, text=True, encoding="utf-8"
    )
    return (result.stdout + result.stderr).strip()


print("=" * 60)
print("  EVCARIX — VIDEO YAYINLAMADAN ONCE TAM KONTROL")
print("=" * 60)

title    = input("\nBaslik: ")
duration = input("Video suresi (saniye): ")
tags     = input("Etiketler (virgülle ayr.): ")
has_desc = input("Aciklama dolu ve sablona uygun mu? (e/h): ")

print("\n-- BASLIK KONTROLU " + "-" * 41)
print(run_validator("validators/validate_title.py", f'"{title}"'))

print("\n-- ETIKET KONTROLU " + "-" * 41)
print(run_validator("validators/validate_tags.py", f'{duration} "{tags}"'))

print("\n-- ACIKLAMA KONTROLU " + "-" * 39)
if has_desc.lower() != "e":
    print("HATA: Aciklama eksik veya sablon kullanilmamis!")
    print("  Kullanim: python3 templates/description_generator.py \\")
    print('    "Hook cumlesi" "Madde1|Madde2|Madde3|Madde4" \\')
    print('    "Bolum1|Bolum2|Bolum3|Bolum4" "tag1,tag2,tag3"')
else:
    print("Aciklama dolu ve sablona uygun.")

print("\n-- KUCUK RESIM KONTROL LISTESI " + "-" * 29)
checks = [
    "'Evcarix' yaziyor mu? (EVTRIX degil)",
    "Ingilizce metin mi? (bozuk karakter yok mu?)",
    "'No hype. Just numbers.' var mi?",
    "Bu videodan once ayni sablon kullanilmadi mi?",
    "1280x720 piksel mi?",
]
for c in checks:
    print(f"  [ ] {c}")

print("\n" + "=" * 60)
print("  Hepsi tamam ise yayinlayabilirsin!")
print("=" * 60)
