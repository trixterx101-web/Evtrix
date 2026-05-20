import os
import re
import json
import logging
import hashlib
import random
import subprocess
from PIL import Image, ImageDraw, ImageFont
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

logger = logging.getLogger("ThumbnailGenerator")

OUTPUT_DIR = "output/thumbnails"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BOLD    = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
REGULAR = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

# Windows / macOS / fallback font arama listesi
_BOLD_CANDIDATES = [
    BOLD,
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "C:/Windows/Fonts/verdanab.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
_REGULAR_CANDIDATES = [
    REGULAR,
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/Arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/verdana.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _find_font(candidates):
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


_BOLD_PATH    = _find_font(_BOLD_CANDIDATES)
_REGULAR_PATH = _find_font(_REGULAR_CANDIDATES)


def _fnt(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    path = _BOLD_PATH if bold else _REGULAR_PATH
    try:
        if path:
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    # Son çare: PIL'in load_default() fontu (PIL>=10 size parametresi alır)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _auto_font(draw, text: str, max_w: int, start_size: int, bold: bool = True):
    """max_w piksel içine sığana kadar font boyutunu küçültür (min 18)."""
    size = start_size
    while size > 18:
        f = _fnt(size, bold)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _fnt(18, bold)


def _text_h(draw, text: str, font) -> int:
    """Gerçek pixel yüksekliğini (textbbox tabanlı) döndürür."""
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _block_top(total_h: int, area_top: int, area_bot: int) -> int:
    """Metin bloğunu area_top..area_bot arasında dikey ortalar."""
    avail = area_bot - area_top
    return area_top + max(0, (avail - total_h) // 2)

def _hex(h: str) -> tuple:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(c1, c2, t):
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


# ── Premium 20 Thumbnail Styles ────────────────────────────────────────────────
GLOBAL_STATS_POOL = [
    ("+300%", "EV SALES GROWTH", (0, 212, 255)),
    ("$0", "GAS CAR FUTURE VALUE", (255, 34, 0)),
    ("500MI", "NEW EV RANGE RECORD", (255, 204, 0)),
    ("800V", "ULTRA FAST CHARGING", (0, 255, 136)),
    ("2.1s", "0-60 MPH TIME RECORD", (255, 0, 128)),
    ("150K+", "EV CHARGERS PLANNED", (0, 212, 255)),
    ("-45%", "BATTERY COST REDUCTION", (0, 255, 136)),
    ("350KW", "MAX CHARGING SPEED", (255, 107, 0)),
    ("10 MIN", "CHARGE TIME TARGET", (0, 212, 255)),
    ("99%", "MOTOR EFFICIENCY", (255, 204, 0)),
    ("1M KM", "LFP LIFESPAN", (255, 107, 0)),
    ("500 WH", "SOLID STATE DENSITY", (255, 204, 0)),
    ("15 YRS", "BATTERY DEGRADATION", (255, 107, 0)),
    ("SODIUM", "NEXT-GEN CELL TECH", (0, 255, 136)),
    ("10x", "SPEED VS HUMAN", (139, 0, 255)),
    ("2030", "AGI PREDICTION", (0, 212, 255)),
    ("40%", "JOBS AUTOMATED", (0, 255, 136)),
    ("FUSION", "NET ENERGY GAIN", (255, 0, 255)),
    ("QUANTUM", "COMPUTING ADVANCE", (0, 212, 255))
]

PREMIUM_PALETTES = [
    # 1. Koyu Lacivert + Cyan (Tesla vs BYD tarzı)
    {"bg": (0,0,0), "left_bg": (0,10,30), "right_bg": (0,5,15), "accent1": (0,212,255), "accent2": (255,255,255), "label": "EV DATA", "icon": "EV"},
    # 2. Koyu Mor + Neon Cyan (Solid State)
    {"bg": (0,0,0), "left_bg": (20,0,40), "right_bg": (10,0,20), "accent1": (139,0,255), "accent2": (0,255,136), "label": "BATTERY", "icon": "[B]"},
    # 3. Koyu Teal + Altın (Cost Comparison)
    {"bg": (0,0,0), "left_bg": (0,30,30), "right_bg": (0,15,15), "accent1": (0,255,200), "accent2": (255,204,0), "label": "FINANCE", "icon": "$$"},
    # 4. Koyu Kırmızı + Beyaz (Battery Degradation)
    {"bg": (0,0,0), "left_bg": (40,0,0), "right_bg": (20,0,0), "accent1": (255,34,0), "accent2": (255,255,255), "label": "WARNING", "icon": "!!"},
    # 5. Altın Sarısı + Siyah (Free Charging)
    {"bg": (0,0,0), "left_bg": (40,30,0), "right_bg": (20,15,0), "accent1": (255,204,0), "accent2": (255,255,255), "label": "HACK", "icon": ">>"},
    # 6. Koyu Mavi + Turuncu (Tax Credits)
    {"bg": (0,0,0), "left_bg": (0,20,50), "right_bg": (0,10,25), "accent1": (255,107,0), "accent2": (0,212,255), "label": "POLICY", "icon": "GOV"},
    # 7. Turuncu Amber + Sarı (Fast Charging)
    {"bg": (0,0,0), "left_bg": (40,20,0), "right_bg": (20,10,0), "accent1": (255,140,0), "accent2": (255,220,0), "label": "SPEED", "icon": "⚡"},
    # 8. Buz Mavisi + Koyu Mavi (Winter Survival)
    {"bg": (0,0,0), "left_bg": (0,40,60), "right_bg": (0,20,30), "accent1": (100,200,255), "accent2": (255,255,255), "label": "TEST", "icon": "❄️"},
    # 9. Koyu Mor + Kırmızı (Hidden Costs)
    {"bg": (0,0,0), "left_bg": (30,0,40), "right_bg": (15,0,20), "accent1": (255,0,100), "accent2": (150,0,255), "label": "SECRET", "icon": "X"},
    # 10. Neon Cyan + Magenta (AI Designed)
    {"bg": (0,0,0), "left_bg": (0,20,30), "right_bg": (0,10,15), "accent1": (0,255,255), "accent2": (255,0,255), "label": "AI TECH", "icon": "AI"},
    # 11. Koyu Mavi + Gümüş (Self Driving)
    {"bg": (0,0,0), "left_bg": (0,10,40), "right_bg": (0,5,20), "accent1": (0,150,255), "accent2": (200,200,200), "label": "AUTONOMY", "icon": "FSD"},
    # 12. Koyu Amber + Beyaz (Electric Trucks)
    {"bg": (0,0,0), "left_bg": (40,25,0), "right_bg": (20,10,0), "accent1": (255,160,0), "accent2": (255,255,255), "label": "TRUCK", "icon": "[T]"},
    # 13. Mavi Gradient + Sarı (EV Change Everything)
    {"bg": (0,0,0), "left_bg": (0,30,80), "right_bg": (0,15,40), "accent1": (0,100,255), "accent2": (255,255,0), "label": "FUTURE", "icon": "2025"},
    # 14. Koyu Kırmızı + Siyah (Regret)
    {"bg": (0,0,0), "left_bg": (50,0,0), "right_bg": (25,0,0), "accent1": (255,0,0), "accent2": (200,200,200), "label": "TRUTH", "icon": "!!"},
    # 15. Koyu Teal + Neon Yeşil (Home Charging)
    {"bg": (0,0,0), "left_bg": (0,40,40), "right_bg": (0,20,20), "accent1": (0,255,150), "accent2": (255,255,255), "label": "HOME", "icon": "HOME"},
    # 16. Koyu Turuncu + Kırmızı (Road Trip)
    {"bg": (0,0,0), "left_bg": (50,20,0), "right_bg": (25,10,0), "accent1": (255,80,0), "accent2": (255,200,0), "label": "TRIP", "icon": "MAP"},
    # 17. Koyu Mor + Pembe (Battery Tech 10x)
    {"bg": (0,0,0), "left_bg": (30,0,50), "right_bg": (15,0,25), "accent1": (200,0,255), "accent2": (255,100,200), "label": "10X", "icon": "UP"},
    # 18. Koyu Yeşil + Altın (EVs Cheaper)
    {"bg": (0,0,0), "left_bg": (0,40,10), "right_bg": (0,20,5), "accent1": (0,200,50), "accent2": (255,215,0), "label": "DATA", "icon": "CHART"},
    # 19. Bordo + Siyah (Toyota Secret)
    {"bg": (0,0,0), "left_bg": (40,5,10), "right_bg": (20,2,5), "accent1": (200,20,40), "accent2": (255,255,255), "label": "LEAK", "icon": "TOP"},
    # 20. Gece Laciverti + Buz Mavisi (Real Reason taking over)
    {"bg": (0,0,0), "left_bg": (0,5,20), "right_bg": (0,2,10), "accent1": (50,150,255), "accent2": (0,255,200), "label": "REPORT", "icon": "DOC"},
]

LAYOUTS = ["split", "versus", "shock", "data",
           "neon", "minimal", "alert", "cinematic", "grid", "bold"]


def _extract_video_frame(video_path: str, output_image_path: str) -> bool:
    """FFmpeg kullanarak videonun 2. saniyesinden 1 adet kare cikarir."""
    try:
        cmd = [
            "ffmpeg", "-y",
            "-ss", "00:00:02",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_image_path
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=15)
        return res.returncode == 0 and os.path.exists(output_image_path)
    except Exception as e:
        logger.error(f"[Thumbnail] Frame extraction failed: {e}")
        return False


def _get_base_image(W, H, st, bg_image=None):
    """Kapak arkasi icin base gorsel uretir. Video karesi varsa uzerine %65 karartma filtresi uygular."""
    if bg_image:
        mask = Image.new("RGB", (W, H), (0, 0, 0))
        img = Image.blend(bg_image, mask, 0.65)
        return img
    else:
        return Image.new("RGB", (W, H), st["bg"])


def _safe(text: str, max_len: int = 25) -> str:
    text = re.sub(r"[^\w\s%\-\+\?!.,:/]", "", text)
    return text[:max_len].strip()


def _split_title(title: str):
    words = title.upper().split()
    fillers = {"IN", "THE", "A", "AN", "AND", "OR", "OF", "FOR",
               "TO", "IS", "ARE", "WAS", "BUT", "WITH"}
    if len(words) > 9:
        words = [w for w in words if w not in fillers]
    lines, chunk = [], []
    for word in words:
        chunk.append(word)
        if len(chunk) == 3:
            lines.append(" ".join(chunk))
            chunk = []
            if len(lines) == 3:
                break
    if chunk and len(lines) < 3:
        lines.append(" ".join(chunk))
    while len(lines) < 3:
        lines.append("")
    return [_safe(ln) for ln in lines[:3]]


def _gradient(draw, W, H, top_c, bot_c):
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=_mix(top_c, bot_c, t))


def _radial_glow(img, cx, cy, radius, color, strength=0.45):
    glow = Image.new("RGB", img.size, (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(radius, 0, -4):
        t = (1 - r / radius) * strength
        col = tuple(min(255, int(color[i] * t)) for i in range(3))
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    return Image.blend(img, glow, 0.7)


def _brand_bar(draw, W, H, a1, a2, label):
    by = H - 72
    draw.rectangle([0, by, W, H], fill=(0, 0, 0))
    draw.rectangle([0, by, W, by + 3], fill=a1)
    draw.text((50, by + 18), "* EVTRIX", font=_fnt(34), fill=(255, 255, 255))
    tag = f"{label} & INSIGHTS"
    tw = int(draw.textlength(tag, font=_fnt(20, False)))
    draw.text((W - tw - 40, by + 24), tag, font=_fnt(20, False), fill=(120, 140, 155))


def _corners(draw, a1, a2):
    W, H = 1280, 720
    s, t, m, mb = 50, 5, 15, 83
    draw.rectangle([m, m, m + s, m + t],          fill=a1)
    draw.rectangle([m, m, m + t, m + s],          fill=a1)
    draw.rectangle([W - m - s, m, W - m, m + t],  fill=a2)
    draw.rectangle([W - m - t, m, W - m, m + s],  fill=a2)
    draw.rectangle([m, H - mb, m + s, H - mb + t],         fill=a1)
    draw.rectangle([m, H - mb - s, m + t, H - mb],         fill=a1)
    draw.rectangle([W - m - s, H - mb, W - m, H - mb + t], fill=a2)
    draw.rectangle([W - m - t, H - mb - s, W - m, H - mb], fill=a2)


# ── LAYOUT: split ─────────────────────────────────────────────────────────────
def _layout_split(W, H, lines, st, bg_image=None):
    a1, a2 = st["accent1"], st["accent2"]
    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)

    if not bg_image:
        # Left / right gradient panels
        for x in range(W // 2 + 80):
            t = x / (W // 2 + 80)
            draw.line([(x, 0), (x, H)], fill=_mix(st["left_bg"], st["bg"], t))
        for x in range(W // 2 - 80, W):
            t = (x - (W // 2 - 80)) / (W - (W // 2 - 80))
            draw.line([(x, 0), (x, H)], fill=_mix(st["bg"], st["right_bg"], t))

    img = _radial_glow(img, 200, H // 2, 500, a1, 0.35)
    img = _radial_glow(img, W - 200, H // 2, 450, a2, 0.28)
    draw = ImageDraw.Draw(img)

    # Diagonal divider lines (RGB only – no alpha channel needed)
    for i in range(6):
        x = W // 2 - 30 + i * 10
        col = a1 if i < 3 else a2
        draw.line([(x, 0), (x + 100, H)], fill=col, width=1)

    # Left accent bar
    draw.rectangle([0, 0, 14, H], fill=a1)

    # Badge top-left
    lbl = f"* {st['label']}"
    bf = _fnt(24)
    bw = int(draw.textlength(lbl, font=bf))
    draw.rectangle([18, 16, bw + 54, 54], fill=a1)
    draw.text((26, 20), lbl, font=bf, fill=(0, 0, 0))

    # Badge top-right
    rt = "EV TECH >"
    rf = _fnt(22)
    rtw = int(draw.textlength(rt, font=rf))
    draw.rectangle([W - rtw - 36, 16, W - 14, 54], fill=(0, 180, 220))
    draw.text((W - rtw - 20, 20), rt, font=rf, fill=(0, 0, 10))

    # L1 – auto-fit to left half width, vertically centered in usable area
    x_l, max_w = 20, W // 2 - 30
    f1 = _auto_font(draw, lines[0], max_w, 110)
    f2 = _auto_font(draw, lines[1], max_w, 80)
    f3 = _auto_font(draw, lines[2], max_w, 52, False) if lines[2] else None
    GAP = 14
    total_h = (_text_h(draw, lines[0], f1) + GAP
               + _text_h(draw, lines[1], f2) + GAP
               + (_text_h(draw, lines[2], f3) + GAP if f3 else 0))
    y1 = _block_top(total_h, 60, H - 72)
    for ox, oy in [(-2,0),(2,0),(0,-2),(0,2)]:
        draw.text((x_l+ox, y1+oy), lines[0], font=f1, fill=tuple(c//2 for c in a1))
    draw.text((x_l, y1), lines[0], font=f1, fill=a1)

    h1 = _text_h(draw, lines[0], f1)
    y2 = y1 + h1 + GAP
    draw.text((x_l, y2), lines[1], font=f2, fill=(255, 255, 255))

    h2 = _text_h(draw, lines[1], f2)
    sy = y2 + h2 + 6
    draw.rectangle([x_l-8, sy-3, x_l+int(draw.textlength(lines[1],font=f2))+8, sy+3], fill=a1)

    if f3:
        y3 = sy + 10
        draw.text((x_l, y3), lines[2], font=f3, fill=(185,185,185))

    # Right side: "EV" big
    ev_f = _fnt(int(H * 0.38))
    ev_x = W - 30 - int(draw.textlength("EV", font=ev_f))
    ev_y = int(H * 0.08)
    for ox, oy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
        draw.text((ev_x + ox, ev_y + oy), "EV", font=ev_f,
                  fill=tuple(c // 3 for c in a2))
    draw.text((ev_x, ev_y), "EV", font=ev_f, fill=a2)

    pf = _fnt(int(H * 0.07))
    pw = int(draw.textlength("DATA INSIDE", font=pf))
    draw.text((W - 30 - pw, ev_y + int(H * 0.42)), "DATA INSIDE",
              font=pf, fill=(255, 255, 255))

    # Center star marker
    lf = _fnt(90)
    lw = int(draw.textlength("*", font=lf))
    draw.text((W // 2 - lw // 2, H // 2 - 55), "*", font=lf,
              fill=(255, 220, 0))

    _brand_bar(draw, W, H, a1, a2, st["label"])
    _corners(draw, a1, a2)
    return img


# ── LAYOUT: versus ────────────────────────────────────────────────────────────
def _layout_versus(W, H, lines, st, bg_image=None):
    a1, a2 = st["accent1"], st["accent2"]
    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)

    if not bg_image:
        for y in range(H):
            t = y / H
            draw.line([(0, y), (W, y)], fill=_mix((0, 5, 16), (5, 0, 16), t))

    img = _radial_glow(img, 300, H // 2, 500, a1, 0.35)
    img = _radial_glow(img, W - 200, H // 2, 400, a2, 0.28)
    draw = ImageDraw.Draw(img)

    # Top bar
    draw.rectangle([0, 0, W, 78], fill=(0, 0, 0))
    draw.rectangle([0, 75, W, 78], fill=a1)
    sf = _fnt(22)
    shock_label = "! SHOCKING"
    shock_w = int(draw.textlength(shock_label, font=sf))
    draw.rectangle([14, 14, shock_w + 50, 62], fill=(255, 90, 0))
    draw.text((22, 18), shock_label, font=sf, fill=(255, 255, 255))
    draw.text((shock_w + 60, 18), "GAS CAR OWNERS MUST SEE THIS",
              font=_fnt(20, False), fill=(200, 200, 200))

    # Left content – vertically centered
    vx_tmp = W - 348
    max_w_v = vx_tmp - 55
    draw.text((38, 95), "THE", font=_fnt(32), fill=(140, 185, 220))
    f_l1 = _auto_font(draw, lines[0], max_w_v, 100)
    f_l2 = _auto_font(draw, lines[1], max_w_v, 100)
    GAP = 12
    total_h = (_text_h(draw, lines[0], f_l1) + GAP
               + _text_h(draw, lines[1], f_l2))
    y_m = _block_top(total_h, 135, H - 72)
    for line, mf in [(lines[0], f_l1), (lines[1], f_l2)]:
        if not line:
            continue
        for ox, oy in [(-2,0),(2,0),(0,-2),(0,2)]:
            draw.text((38+ox, y_m+oy), line, font=mf, fill=tuple(c//3 for c in a1))
        draw.text((38, y_m), line, font=mf, fill=a1)
        y_m += _text_h(draw, line, mf) + GAP
    if lines[2] and y_m < H - 85:
        f3 = _auto_font(draw, f"!! {lines[2]}", max_w_v, 26)
        draw.text((42, y_m + 4), f"!! {lines[2]}", font=f3, fill=a2)

    # Vertical divider
    vx = W - 348
    for y in range(82, H - 74):
        draw.point((vx, y), fill=a1)

    # Right: stat cards
    cx, cy, cw = vx + 18, 90, W - vx - 36
    for val, lbl_text, col in st.get("stats", []):
        cr, cg, cb = col
        draw.rectangle(
            [cx, cy, cx + cw, cy + 90],
            fill=(max(0, cr // 8), max(0, cg // 8), max(0, cb // 8 + 6)),
        )
        draw.rectangle([cx, cy, cx + 6, cy + 90], fill=col)
        draw.text((cx + 14, cy + 6),  val,      font=_fnt(46),       fill=col)
        draw.text((cx + 14, cy + 58), lbl_text, font=_fnt(18, False), fill=(165, 180, 195))
        cy += 104

    _brand_bar(draw, W, H, a1, a2, st["label"])
    _corners(draw, a1, a2)
    return img


# ── LAYOUT: shock ─────────────────────────────────────────────────────────────
def _layout_shock(W, H, lines, st, bg_image=None):
    a1, a2 = st["accent1"], st["accent2"]
    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)
    if not bg_image:
        _gradient(draw, W, H, st["left_bg"], (0, 0, 0))

    img = _radial_glow(img, W // 2, int(H * 0.45), 550, a1, 0.4)
    img = _radial_glow(img, W // 2, int(H * 0.45), 400, a2, 0.25)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, 12, H], fill=a1)
    draw.rectangle([W - 12, 0, W, H], fill=a2)

    # Icon
    ico_f = _fnt(88)
    iw = int(draw.textlength(st["icon"], font=ico_f))
    draw.text((W // 2 - iw // 2, int(H * 0.06)), st["icon"],
              font=ico_f, fill=(255, 220, 0))
    # Main text – centered, vertically centered in usable area
    max_w_s = W - 80
    f1 = _auto_font(draw, lines[0], max_w_s, 100)
    f2 = _auto_font(draw, lines[1], max_w_s, 72)
    f3 = _auto_font(draw, lines[2], max_w_s, 52) if lines[2] else None
    GAP = 14
    total_h = (_text_h(draw, lines[0], f1) + GAP
               + _text_h(draw, lines[1], f2)
               + (GAP + _text_h(draw, lines[2], f3) if f3 else 0))
    y1 = _block_top(total_h, int(H * 0.24), H - 72)
    lw = int(draw.textlength(lines[0], font=f1))
    for ox, oy in [(-3,0),(3,0),(0,-3),(0,3)]:
        draw.text((W//2-lw//2+ox, y1+oy), lines[0], font=f1, fill=tuple(c//2 for c in a1))
    draw.text((W//2-lw//2, y1), lines[0], font=f1, fill=a1)
    y2 = y1 + _text_h(draw, lines[0], f1) + GAP
    lw2 = int(draw.textlength(lines[1], font=f2))
    draw.text((W//2-lw2//2, y2), lines[1], font=f2, fill=(255, 255, 255))
    if f3:
        y3 = y2 + _text_h(draw, lines[1], f2) + GAP
        lw3 = int(draw.textlength(lines[2], font=f3))
        draw.text((W//2-lw3//2, y3), lines[2], font=f3, fill=a2)


    _brand_bar(draw, W, H, a1, a2, st["label"])
    _corners(draw, a1, a2)
    return img


# ── LAYOUT: data ──────────────────────────────────────────────────────────────
def _layout_data(W, H, lines, st, bg_image=None):
    a1, a2 = st["accent1"], st["accent2"]
    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)
    if not bg_image:
        _gradient(draw, W, H, st["left_bg"], st["right_bg"])

    img = _radial_glow(img, 100, H // 2, 450, a1, 0.32)
    img = _radial_glow(img, W - 100, H // 2, 400, a2, 0.26)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, 8, H], fill=a1)

    # Header badge
    lbl = f"{st['icon']} {st['label']}"
    bf = _fnt(24)
    bw = int(draw.textlength(lbl, font=bf))
    draw.rectangle([30, 28, bw + 68, 66], fill=a1)
    draw.text((38, 32), lbl, font=bf, fill=(0, 0, 0))

    ico_f = _fnt(60)
    draw.text((W - 90, 20), st["icon"], font=ico_f, fill=a1)

    # Main text – left side, vertically centered
    max_w_d = W // 2 + 40
    f1 = _auto_font(draw, lines[0], max_w_d, 100)
    f2 = _auto_font(draw, lines[1], max_w_d, 72)
    f3 = _auto_font(draw, lines[2], max_w_d, 52) if lines[2] else None
    GAP = 14
    total_h = (_text_h(draw, lines[0], f1) + GAP
               + _text_h(draw, lines[1], f2)
               + (GAP + _text_h(draw, lines[2], f3) if f3 else 0))
    # clamp so we don't enter stat box area (H-148)
    y1 = _block_top(total_h, 82, H - 148 - 10)
    for ox, oy in [(-2,0),(2,0),(0,-2),(0,2)]:
        draw.text((36+ox, y1+oy), lines[0], font=f1, fill=tuple(c//3 for c in a1))
    draw.text((36, y1), lines[0], font=f1, fill=a1)
    y2 = y1 + _text_h(draw, lines[0], f1) + GAP
    draw.text((36, y2), lines[1], font=f2, fill=(255, 255, 255))
    if f3:
        y3 = y2 + _text_h(draw, lines[1], f2) + GAP
        draw.rectangle([36, y3-4, 42, y3 + _text_h(draw, lines[2], f3) + 4], fill=a2)
        draw.text((50, y3), lines[2], font=f3, fill=a2)

    # Stat boxes at bottom
    bx, by_s = 36, H - 148
    bw_s = (W - 72 - 40) // 3
    for i, (val, lbl_text, col) in enumerate(st.get("stats", [])):
        x = bx + i * (bw_s + 20)
        cr, cg, cb = col
        draw.rectangle(
            [x, by_s, x + bw_s, by_s + 68],
            fill=(max(0, cr // 7), max(0, cg // 7), max(0, cb // 7 + 5)),
        )
        draw.rectangle([x, by_s, x + bw_s, by_s + 4], fill=col)
        draw.text((x + 12, by_s + 10), val,          font=_fnt(36),       fill=col)
        draw.text((x + 12, by_s + 48), lbl_text[:14], font=_fnt(14, False), fill=(150, 165, 178))

    _brand_bar(draw, W, H, a1, a2, st["label"])
    _corners(draw, a1, a2)
    return img


# ── LAYOUT: neon ──────────────────────────────────────────────────────────────
def _layout_neon(W, H, lines, st, bg_image=None):
    a1, a2 = st["accent1"], st["accent2"]
    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)
    if not bg_image:
        for i, y in enumerate(range(0, H, 36)):
            intensity = 8 if i % 3 == 0 else 3
            draw.line([(0, y), (W, y)], fill=(intensity, 0, intensity * 2))
    img = _radial_glow(img, W // 2, H // 2, 600, a1, 0.5)
    img = _radial_glow(img, W // 2, H // 2, 350, a2, 0.3)
    draw = ImageDraw.Draw(img)
    for offset in range(0, 18, 6):
        c = max(0, 255 - offset * 10)
        col = tuple(min(255, int(a1[i] * c / 255)) for i in range(3))
        draw.rectangle([offset, offset, W - offset, H - 75 - offset], outline=col, width=1)
    draw.rectangle([0, 0, W, 50], fill=(0, 0, 0))
    lbl_txt = f"[ {st['label']} REPORT ]"
    lf = _fnt(26)
    lw = int(draw.textlength(lbl_txt, font=lf))
    draw.text((W // 2 - lw // 2, 12), lbl_txt, font=lf, fill=a2)
    max_w_n = W - 60
    f1 = _auto_font(draw, lines[0], max_w_n, 90)
    f2 = _auto_font(draw, lines[1], max_w_n, 68)
    f3 = _auto_font(draw, lines[2], max_w_n, 50, False) if lines[2] else None
    GAP = 16
    h1 = _text_h(draw, lines[0], f1)
    total_h = h1 + 9 + GAP + _text_h(draw, lines[1], f2) + (GAP + _text_h(draw, lines[2], f3) if f3 else 0)
    y1 = _block_top(total_h, 52, H - 72)
    tw1 = int(draw.textlength(lines[0], font=f1))
    for ox, oy in [(-4,0),(4,0),(0,-4),(0,4)]:
        draw.text((W//2-tw1//2+ox, y1+oy), lines[0], font=f1, fill=tuple(min(255,c*2) for c in a1))
    draw.text((W//2-tw1//2, y1), lines[0], font=f1, fill=(255,255,255))
    draw.rectangle([W//2-tw1//2-8, y1+h1+4, W//2+tw1//2+8, y1+h1+9], fill=a1)
    y2 = y1 + h1 + 9 + GAP
    tw2 = int(draw.textlength(lines[1], font=f2))
    draw.text((W//2-tw2//2, y2), lines[1], font=f2, fill=a1)
    if f3:
        y3 = y2 + _text_h(draw, lines[1], f2) + GAP
        tw3 = int(draw.textlength(lines[2], font=f3))
        draw.text((W//2-tw3//2, y3), lines[2], font=f3, fill=a2)
    for offset in range(3):
        draw.line([(8 + offset * 4, 50), (8 + offset * 4, H - 75)], fill=a1, width=2)
        draw.line([(W - 8 - offset * 4, 50), (W - 8 - offset * 4, H - 75)], fill=a2, width=2)
    _brand_bar(draw, W, H, a1, a2, st["label"])
    return img


# ── LAYOUT: minimal ───────────────────────────────────────────────────────────
def _layout_minimal(W, H, lines, st, bg_image=None):
    a1, a2 = st["accent1"], st["accent2"]
    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)
    if not bg_image:
        for x in range(W):
            draw.line([(x, 0), (x, H)], fill=_mix((8, 8, 12), st["right_bg"], x / W * 0.15))
    draw.rectangle([0, 0, 16, H], fill=a1)
    draw.rectangle([0, 0, W, 6], fill=a1)
    draw.text((30, 20), f"EVTRIX  //  {st['label']}", font=_fnt(20, False), fill=(100, 110, 125))
    # Left text zone: x=20..W//2-20  Right zone: W//2+10..W-20 (big stat)
    max_w_m = W // 2 - 40
    f1 = _auto_font(draw, lines[0], max_w_m, 90)
    f2 = _auto_font(draw, lines[1], max_w_m, 65)
    f3 = _auto_font(draw, lines[2], max_w_m, 46, False) if lines[2] else None
    GAP = 14
    h1 = _text_h(draw, lines[0], f1)
    total_h = h1 + 7 + GAP + _text_h(draw, lines[1], f2) + (GAP + _text_h(draw, lines[2], f3) if f3 else 0)
    y1 = _block_top(total_h, 36, H - 72)
    draw.text((30, y1), lines[0], font=f1, fill=(240,240,240))
    line_y = y1 + h1 + 4
    draw.rectangle([30, line_y, 30+int(draw.textlength(lines[0],font=f1)), line_y+7], fill=a1)
    y2 = line_y + 7 + GAP
    draw.text((30, y2), lines[1], font=f2, fill=a2)
    if f3:
        y3 = y2 + _text_h(draw, lines[1], f2) + GAP
        draw.text((30, y3), lines[2], font=f3, fill=(160,165,175))
    # Big stat — strictly right half, no overlap
    big_txt = st["stats"][0][0] if st.get("stats") else st["icon"]
    big_zone_w = W // 2 - 30
    big_f = _auto_font(draw, big_txt, big_zone_w, 200)
    bw_px = int(draw.textlength(big_txt, font=big_f))
    bx = W - bw_px - 30
    by = int(H * 0.18)
    draw.text((bx+3, by+3), big_txt, font=big_f, fill=tuple(c//6 for c in a1))
    draw.text((bx, by), big_txt, font=big_f, fill=a1)
    if st.get("stats"):
        desc = st["stats"][0][1]
        sf = _fnt(18, False)
        sw_px = int(draw.textlength(desc, font=sf))
        draw.text((W-sw_px-30, by+_text_h(draw,big_txt,big_f)+8), desc, font=sf, fill=(130,140,150))
    draw.rectangle([0, H - 72, W, H - 69], fill=a1)
    draw.text((30, H - 58), "* EVTRIX", font=_fnt(30), fill=(255, 255, 255))
    draw.text((W - 200, H - 52), st["label"], font=_fnt(22, False), fill=(80, 90, 100))
    return img


# ── LAYOUT: alert ─────────────────────────────────────────────────────────────
def _layout_alert(W, H, lines, st, bg_image=None):
    a1, a2 = st["accent1"], st["accent2"]
    dark1 = tuple(min(20, c // 4) for c in a1)
    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)
    if not bg_image:
        _gradient(draw, W, H, dark1, (0, 0, 0))
    img = _radial_glow(img, W // 4, H // 2, 600, a1, 0.45)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 22, H], fill=a1)
    draw.rectangle([22, 0, W, 68], fill=a1)
    af = _fnt(38)
    draw.text((36, 14), ">> ALERT:", font=af, fill=(0, 0, 0))
    sub_x = 36 + int(draw.textlength(">> ALERT:", font=af)) + 20
    draw.text((sub_x, 20), st["label"], font=_fnt(28, False), fill=(0, 0, 0))
    draw.rectangle([W - 180, 0, W, 68], fill=(0, 0, 0))
    draw.text((W - 165, 16), st["icon"], font=_fnt(36), fill=a1)
    # Left zone: x=36..W-320 (stat cards start at W-320)
    max_w_a = W - 340 - 36
    f1 = _auto_font(draw, lines[0], max_w_a, 90)
    f2 = _auto_font(draw, lines[1], max_w_a, 68)
    f3 = _auto_font(draw, lines[2], max_w_a, 50, False) if lines[2] else None
    GAP = 14
    h1 = _text_h(draw, lines[0], f1)
    total_h = h1 + 7 + GAP + _text_h(draw, lines[1], f2) + (GAP + _text_h(draw, lines[2], f3) if f3 else 0)
    y1 = _block_top(total_h, 74, H - 72)
    draw.text((36, y1), lines[0], font=f1, fill=(255,255,255))
    draw.rectangle([36, y1+h1+2, 36+int(draw.textlength(lines[0],font=f1)), y1+h1+9], fill=a2)
    y2 = y1 + h1 + 9 + GAP
    draw.text((36, y2), lines[1], font=f2, fill=a2)
    if f3:
        y3 = y2 + _text_h(draw, lines[1], f2) + GAP
        draw.text((36, y3), lines[2], font=f3, fill=(200,200,200))
    rx, ry = W - 320, 80
    for val, lbl_text, col in st.get("stats", []):
        cr, cg, cb = col
        draw.rectangle([rx, ry, rx + 300, ry + 88],
                       fill=(max(0, cr // 9), max(0, cg // 9), max(0, cb // 9 + 4)))
        draw.rectangle([rx, ry, rx + 8, ry + 88], fill=col)
        draw.text((rx + 18, ry + 8),  val,      font=_fnt(42),        fill=col)
        draw.text((rx + 18, ry + 56), lbl_text, font=_fnt(16, False), fill=(160, 175, 185))
        ry += 100
    _brand_bar(draw, W, H, a1, a2, st["label"])
    return img


# ── LAYOUT: cinematic ─────────────────────────────────────────────────────────
def _layout_cinematic(W, H, lines, st, bg_image=None):
    a1, a2 = st["accent1"], st["accent2"]
    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)
    img = _radial_glow(img, W // 2, H // 2, 700, a1, 0.38)
    img = _radial_glow(img, W // 2, H // 2, 400, a2, 0.18)
    draw = ImageDraw.Draw(img)
    bar_h = int(H * 0.13)
    draw.rectangle([0, 0, W, bar_h], fill=(0, 0, 0))
    draw.rectangle([0, H - bar_h, W, H], fill=(0, 0, 0))
    draw.text((40, H - bar_h + 14), "* EVTRIX", font=_fnt(26), fill=(200, 200, 200))
    tag = f"{st['label']} & INSIGHTS"
    tw_tag = int(draw.textlength(tag, font=_fnt(18, False)))
    draw.text((W - tw_tag - 40, H - bar_h + 18), tag, font=_fnt(18, False), fill=(90, 100, 110))
    lbl_txt = f"[ {st['label']} ]"
    lf = _fnt(22)
    lw = int(draw.textlength(lbl_txt, font=lf))
    draw.text((W // 2 - lw // 2, bar_h // 2 - 12), lbl_txt, font=lf, fill=a2)
    mid_y = H // 2
    draw.rectangle([60, mid_y - 3, W - 60, mid_y + 3], fill=a1)
    # Text above center line
    max_w_c = W - 140
    f1 = _auto_font(draw, lines[0], max_w_c, 85)
    f2 = _auto_font(draw, lines[1], max_w_c, 65)
    f3 = _auto_font(draw, lines[2], max_w_c, 50, False) if lines[2] else None
    GAP = 12
    h1 = _text_h(draw, lines[0], f1)
    total_h = h1 + GAP + _text_h(draw, lines[1], f2) + (GAP + _text_h(draw, lines[2], f3) if f3 else 0)
    # center text block between bar_h and mid_y (above the center divider line)
    y1 = _block_top(total_h, bar_h + 12, mid_y - 8)
    tw1 = int(draw.textlength(lines[0], font=f1))
    for ox, oy in [(-3,0),(3,0)]:
        draw.text((W//2-tw1//2+ox, y1+oy), lines[0], font=f1, fill=tuple(c//3 for c in a1))
    draw.text((W//2-tw1//2, y1), lines[0], font=f1, fill=(240,240,240))
    y2 = y1 + h1 + GAP
    tw2 = int(draw.textlength(lines[1], font=f2))
    draw.text((W//2-tw2//2, y2), lines[1], font=f2, fill=a1)
    if f3:
        y3 = y2 + _text_h(draw, lines[1], f2) + GAP
        tw3 = int(draw.textlength(lines[2], font=f3))
        if y3 + _text_h(draw, lines[2], f3) < mid_y:
            draw.text((W//2-tw3//2, y3), lines[2], font=f3, fill=a2)
    for offset in [60, 68, 76]:
        draw.line([(offset, bar_h), (offset, H - bar_h)], fill=a1, width=1)
        draw.line([(W - offset, bar_h), (W - offset, H - bar_h)], fill=a2, width=1)
    return img


# ── LAYOUT: grid ──────────────────────────────────────────────────────────────
def _layout_grid(W, H, lines, st, bg_image=None):
    a1, a2 = st["accent1"], st["accent2"]
    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)
    if not bg_image:
        for x in range(0, W, 60):
            draw.line([(x, 0), (x, H)], fill=(12, 12, 18), width=1)
        for y in range(0, H, 60):
            draw.line([(0, y), (W, y)], fill=(12, 12, 18), width=1)
        _gradient(draw, W, H, st["left_bg"], (0, 0, 0))
    img = _radial_glow(img, 200, H // 2, 550, a1, 0.35)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 20, H], fill=a1)
    draw.rectangle([0, 0, W // 2 + 20, 6], fill=a1)
    ef = _fnt(22)
    ew = int(draw.textlength(st["label"], font=ef))
    draw.rectangle([30, 18, ew + 58, 54], fill=a1)
    draw.text((38, 22), st["label"], font=ef, fill=(0, 0, 0))
    # Left text zone: x=30..gx-10
    max_w_g = W // 2 - 30
    f1 = _auto_font(draw, lines[0], max_w_g, 90)
    f2 = _auto_font(draw, lines[1], max_w_g, 68)
    f3 = _auto_font(draw, lines[2], max_w_g, 46, False) if lines[2] else None
    GAP = 14
    h1 = _text_h(draw, lines[0], f1)
    h2 = _text_h(draw, lines[1], f2)
    total_h = h1 + GAP + h2 + 9 + (GAP + _text_h(draw, lines[2], f3) if f3 else 0)
    y1 = _block_top(total_h, 60, H - 72)
    for ox, oy in [(-2,0),(2,0)]:
        draw.text((30+ox, y1+oy), lines[0], font=f1, fill=tuple(c//3 for c in a1))
    draw.text((30, y1), lines[0], font=f1, fill=a1)
    y2 = y1 + h1 + GAP
    draw.text((30, y2), lines[1], font=f2, fill=(230,230,230))
    draw.rectangle([30, y2+h2+4, 30+int(draw.textlength(lines[1],font=f2)), y2+h2+9], fill=a2)
    if f3:
        y3 = y2 + h2 + 9 + GAP
        draw.text((30, y3), lines[2], font=f3, fill=(155,165,175))
    gx = W // 2 + 30
    gy = 20
    gw = W - gx - 30
    for i, (val, lbl_text, col) in enumerate(st.get("stats", [])):
        card_h = (H - 100) // 3 - 8
        cy_card = gy + i * (card_h + 10)
        cr, cg, cb = col
        draw.rectangle([gx, cy_card, gx + gw, cy_card + card_h],
                       fill=(max(0, cr // 9), max(0, cg // 9), max(0, cb // 9 + 6)))
        draw.rectangle([gx, cy_card, gx + 10, cy_card + card_h], fill=col)
        vf = _fnt(int(card_h * 0.60))
        draw.text((gx + 22, cy_card + 4), val, font=vf, fill=col)
        draw.text((gx + 22, cy_card + card_h - 26), lbl_text, font=_fnt(16, False), fill=(155, 170, 185))
    _brand_bar(draw, W, H, a1, a2, st["label"])
    _corners(draw, a1, a2)
    return img


# ── LAYOUT: bold ──────────────────────────────────────────────────────────────
def _layout_bold(W, H, lines, st, bg_image=None):
    a1, a2 = st["accent1"], st["accent2"]
    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)
    if not bg_image:
        tri_pts = [(W // 2, 0), (W, 0), (W, H), (W // 2 + 80, H)]
        draw.polygon(tri_pts, fill=tuple(c // 5 for c in a1))
        for i in range(12):
            x_start = W // 2 - 40 + i * 30
            draw.line([(x_start, 0), (x_start + 200, H)], fill=tuple(c // 3 for c in a1), width=2)
    img = _radial_glow(img, W // 4, H // 2, 580, a1, 0.42)
    img = _radial_glow(img, W - 100, H // 4, 400, a2, 0.30)
    draw = ImageDraw.Draw(img)
    for i, w in enumerate([20, 6, 3]):
        x = [0, 28, 40][i]
        draw.rectangle([x, 0, x + w, H], fill=a1 if i == 0 else tuple(c // 2 for c in a1))
    draw.rectangle([0, 0, W, 58], fill=(0, 0, 0))
    draw.rectangle([0, 55, W, 58], fill=a1)
    draw.text((54, 15), f"EVTRIX  |  {st['label']} SERIES", font=_fnt(24), fill=(200, 200, 200))
    # Left text zone: x=50..W//2
    max_w_b = W // 2 - 20
    f1 = _auto_font(draw, lines[0], max_w_b, 95)
    f2 = _auto_font(draw, lines[1], max_w_b, 68)
    f3 = _auto_font(draw, lines[2], max_w_b, 50, False) if lines[2] else None
    GAP = 14
    h1 = _text_h(draw, lines[0], f1)
    h2 = _text_h(draw, lines[1], f2)
    total_h = h1 + GAP + h2 + (GAP + _text_h(draw, lines[2], f3) if f3 else 0)
    y1 = _block_top(total_h, 70, H - 72)
    draw.text((50, y1+4), lines[0], font=f1, fill=tuple(c//5 for c in a1))
    draw.text((50, y1), lines[0], font=f1, fill=(255,255,255))
    y2 = y1 + h1 + GAP
    draw.text((50, y2), lines[1], font=f2, fill=a1)
    lw2 = int(draw.textlength(lines[1], font=f2))
    draw.rectangle([50, y2+h2+4, 50+lw2, y2+h2+11], fill=a2)
    if f3:
        y3 = y2 + h2 + GAP
        draw.text((50, y3), lines[2], font=f3, fill=(170,180,190))
    # Big stat — strictly right half
    big_val = st["stats"][0][0] if st.get("stats") else st["icon"]
    big_zone_w = W // 2 - 30
    big_f = _auto_font(draw, big_val, big_zone_w, 200)
    bw_px = int(draw.textlength(big_val, font=big_f))
    bx = W - bw_px - 40
    by = int(H * 0.12)
    draw.text((bx+4, by+4), big_val, font=big_f, fill=tuple(c//6 for c in a2))
    draw.text((bx, by), big_val, font=big_f, fill=a2)
    if st.get("stats"):
        desc = st["stats"][0][1]
        sf = _fnt(20, False)
        sw_px = int(draw.textlength(desc, font=sf))
        draw.text((W-sw_px-40, by+_text_h(draw,big_val,big_f)+8), desc, font=sf, fill=(120,130,140))
    _brand_bar(draw, W, H, a1, a2, st["label"])
    _corners(draw, a1, a2)
    return img


# ── Public class ──────────────────────────────────────────────────────────────
class ThumbnailGenerator:

    def create(
        self,
        title: str,
        topic: str = "default",
        stat: str = "",
        category: str = "default",
        output_path: str = "",
        is_short: bool = False,
    ) -> str:
        # Short video → thumbnail oluşturma, hiçbir şey yapma
        if is_short:
            logger.info("[Thumbnail] Short video - thumbnail atlanıyor.")
            return ""

        W, H = 1280, 720
        
        # 20 PREMIUM stilden rastgele birini seçiyoruz (Tam Çeşitlilik)
        base_st = random.choice(PREMIUM_PALETTES)
        st = {k: v for k, v in base_st.items()}
        
        # Sınırsız çeşitlilik için GLOBAL_STATS_POOL'dan 3 istatistik seçiyoruz
        st["stats"] = random.sample(GLOBAL_STATS_POOL, min(3, len(GLOBAL_STATS_POOL)))

        # Sınırsız çeşitlilik için layout'u tamamen rastgele seçelim
        layout = random.choice(LAYOUTS)

        # Arka plan için assets/footage altındaki videolardan rastgele bir kare çıkarma
        video_frame_img = None
        temp_frame_path = f"assets/temp/temp_thumb_bg_{random.randint(1000, 9999)}.jpg"
        
        try:
            footage_dirs = ["assets/footage", "assets/free_footage", "assets/videos", "assets/temp_videos", "assets"]
            all_files = []
            for d in footage_dirs:
                if os.path.exists(d):
                    for f in os.listdir(d):
                        if f.lower().endswith(".mp4"):
                            all_files.append(os.path.join(d, f))
            
            if all_files:
                # Konuyla ilgili video aramayı deneyelim (basit filtreleme)
                topic_words = set(topic_key.split("_"))
                relevant_files = []
                for f in all_files:
                    f_lower = os.path.basename(f).lower()
                    if any(w in f_lower for w in topic_words if len(w) > 2):
                        relevant_files.append(f)
                
                # Eşleşen video varsa oradan, yoksa rastgele herhangi bir videodan kare al
                chosen_video = None
                if relevant_files:
                    chosen_video = random.choice(relevant_files)
                else:
                    chosen_video = random.choice(all_files)
                
                if chosen_video:
                    os.makedirs("assets/temp", exist_ok=True)
                    if _extract_video_frame(chosen_video, temp_frame_path):
                        video_frame_img = Image.open(temp_frame_path).resize((W, H))
                        logger.info(f"[Thumbnail] Arka plan görseli videodan çıkarıldı: {chosen_video}")
        except Exception as ve:
            logger.error(f"[Thumbnail] Arka plan görseli çıkarma hatası: {ve}")

        lines = _split_title(title)
        try:
            dispatch = {
                "split":     _layout_split,
                "versus":    _layout_versus,
                "shock":     _layout_shock,
                "data":      _layout_data,
                "neon":      _layout_neon,
                "minimal":   _layout_minimal,
                "alert":     _layout_alert,
                "cinematic": _layout_cinematic,
                "grid":      _layout_grid,
                "bold":      _layout_bold,
            }
            
            # bg_image parametresini geçiyoruz
            img = dispatch[layout](W, H, lines, st, bg_image=video_frame_img)

            if not output_path:
                safe_t = re.sub(r"[^\w]", "_", title[:30])
                output_path = os.path.join(OUTPUT_DIR, f"thumb_{safe_t}_{layout}.jpg")
            os.makedirs(
                os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
                exist_ok=True,
            )

            img.save(output_path, "JPEG", quality=95)
            size = os.path.getsize(output_path) // 1024
            logger.info(f"[Thumbnail] OK {layout} - {size}KB -> {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"[Thumbnail] ERROR create(): {e}")
            return output_path or ""
        finally:
            # Geçici dosyayı temizle
            if video_frame_img:
                try:
                    video_frame_img.close()
                except:
                    pass
            if os.path.exists(temp_frame_path):
                try:
                    os.remove(temp_frame_path)
                except Exception as re_err:
                    logger.warning(f"[Thumbnail] Geçici dosya silinemedi: {re_err}")

    def upload_thumbnail(self, video_id: str, thumbnail_path: str) -> bool:
        try:
            token_json  = os.getenv("YOUTUBE_TOKEN_JSON")
            secret_json = os.getenv("YOUTUBE_CLIENT_SECRET_JSON")
            if not token_json or not secret_json:
                logger.warning("[Thumbnail] Missing YouTube credentials")
                return False
            token_data  = json.loads(token_json)
            secret_data = json.loads(secret_json)
            client_id   = secret_data["installed"]["client_id"]
            client_sec  = secret_data["installed"]["client_secret"]
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_sec,
                scopes=["https://www.googleapis.com/auth/youtube.force-ssl"],
            )
            youtube = build("youtube", "v3", credentials=creds)
            media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
            logger.info(f"[Thumbnail] Uploaded to YouTube: {video_id}")
            return True
        except Exception as e:
            logger.error(f"[Thumbnail] Upload failed: {e}")
            return False


def generate_and_upload(video_id: str, title: str, topic: str) -> bool:
    gen = ThumbnailGenerator()
    path = gen.create(title=title, topic=topic)
    if path and os.path.exists(path):
        return gen.upload_thumbnail(video_id, path)
    return False
