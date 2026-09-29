"""
Evcarix — Etiket Dogrulayici + Otomatik Duzeltme
Kullanim: python3 validators/validate_tags.py <video_suresi_saniye> "etiket1, etiket2, ..."
"""

import sys
import re

UNIVERSAL = (
    "electric vehicle, EV, battery technology, EV range, electric car, "
    "Evcarix, EV data, EV future, fast charging, EV charging, "
    "ev range loss, EV technology, clean energy, sustainable energy, "
    "electric vehicle data, battery degradation, EV market, lfp battery, "
    "solid state battery, electric car range, EV industry, ev battery, "
    "EV data analysis, electric vehicles 2026, EV vs gas, battery cost"
)
SHORTS_TAGS = {"shorts", "evshorts", "#shorts", "#evshorts"}


def validate_tags(duration_seconds, tags_str):
    raw_tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    errors = []
    fixed_tags = []

    for tag in raw_tags:
        tag_lower = tag.lower()
        if tag_lower in SHORTS_TAGS:
            if int(duration_seconds) > 60:
                errors.append(f"HATA: '{tag}' kaldirildi — video {duration_seconds}sn, Shorts degil")
                continue
        # Temizle: newline/tab kaldir, sadece harf/rakam/bosluk/tire birak
        clean = re.sub(r'[\r\n\t]', ' ', tag)
        clean = re.sub(r'[^a-zA-Z0-9 \-]', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if 2 <= len(clean) <= 30:
            if clean.lower() not in [t.lower() for t in fixed_tags]:
                fixed_tags.append(clean)

    # 500 karakter siniri
    while fixed_tags:
        total = sum(len(t) for t in fixed_tags) + len(fixed_tags) - 1
        if total > 495:
            fixed_tags.pop()
        else:
            break

    total_chars = sum(len(t) for t in fixed_tags) + max(len(fixed_tags) - 1, 0)
    print(f"\nToplam karakter: {total_chars}/500")
    print(f"Etiket sayisi  : {len(fixed_tags)}")

    print("\nTemizlenmis etiketler:")
    print(", ".join(fixed_tags))

    if errors:
        print("\nHATALAR:")
        for e in errors:
            print(f"  {e}")
    else:
        print("\nEtiketler gecerli!")

    print("\nOneri — Evrensel etiket listesi:")
    print(UNIVERSAL)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        dur = input("Video suresi (saniye): ")
        tags = input("Etiketler (virgülle ayrilmis): ")
    else:
        dur = sys.argv[1]
        tags = " ".join(sys.argv[2:])
    validate_tags(dur, tags)
