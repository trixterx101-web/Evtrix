"""
Evcarix — Baslik Dogrulayici
Kullanim: python3 validators/validate_title.py "Baslik buraya"
"""

import sys
import re

FORBIDDEN = [
    "health costs", "GBM", "neural network", "survival predict",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "An Accurate and Interpretable", "Hyper Graph", "&amp;"
]
EV_WORDS = [
    "ev", "electric", "vehicle", "battery", "charging", "range",
    "hybrid", "tesla", "nissan", "v2g", "v2h", "fsd", "solid state",
    "depreciation", "lease", "buy", "car", "motor", "engine", "fuel"
]

def validate(title):
    errors = []
    warnings = []

    if len(title) > 100:
        errors.append(f"HATA: Baslik cok uzun: {len(title)} karakter (max 100)")

    title_lower = title.lower()
    for word in FORBIDDEN:
        if word.lower() in title_lower:
            errors.append(f"HATA: Yasak kelime bulundu: '{word}'")

    # Non-ASCII (Hintce, Almanca, Arapca vs.) karakter kontrolu
    if re.search(r'[^\x00-\x7F]', title):
        errors.append("HATA: Ingilizce disi karakter tespit edildi")

    if "&amp;" in title:
        errors.append("HATA: '&amp;' bulundu — '&' ile degistir")

    words = title.split()
    upper_count = sum(1 for w in words if w.isupper() and len(w) > 2)
    if upper_count > len(words) * 0.6:
        warnings.append("UYARI: Cok fazla buyuk harf — karisik kullan")

    has_ev = any(w in title_lower for w in EV_WORDS)
    if not has_ev:
        errors.append("HATA: EV ile ilgili kelime yok — EV kanali icin gecersiz")

    if errors:
        print("BASLIK GECERSIZ:")
        for e in errors:
            print(f"  {e}")
    if warnings:
        print("UYARILAR:")
        for w in warnings:
            print(f"  {w}")
    if not errors and not warnings:
        print("Baslik gecerli!")
    return len(errors) == 0

if __name__ == "__main__":
    title = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Baslik: ")
    validate(title)
