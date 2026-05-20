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


# ── 20 Premium YouTube-Style Thumbnail Palettes (4 Themes × 5 Variations) ──────
# theme key maps directly to one of the 4 YouTube-style layout functions.

PREMIUM_PALETTES = [
    # ══════════════════════════════════════════════════════════════════════
    # THEME 1: "shocking" — Purple/AI/Prediction (bkz. Image 1)
    # ══════════════════════════════════════════════════════════════════════
    {
        "theme": "shocking",
        "bg": (15, 0, 30), "bg_top": (22, 0, 42), "bg_bot": (8, 0, 14),
        "left_bg": (25, 0, 45), "right_bg": (10, 0, 20),
        "accent1": (180, 0, 255), "accent2": (255, 215, 0),
        "label": "AI ANALYSIS", "badge_icon": "* ", "icon": "AI",
        "badge_color": (75, 0, 155),
        "stat1": "289mi", "stat2": "53mi",
    },
    {
        "theme": "shocking",
        "bg": (10, 0, 25), "bg_top": (16, 0, 36), "bg_bot": (5, 0, 12),
        "left_bg": (20, 0, 40), "right_bg": (5, 0, 15),
        "accent1": (210, 0, 255), "accent2": (255, 200, 0),
        "label": "SHOCKING", "badge_icon": "!! ", "icon": "!!",
        "badge_color": (100, 0, 175),
        "stat1": "342mi", "stat2": "78mi",
    },
    {
        "theme": "shocking",
        "bg": (20, 0, 20), "bg_top": (28, 0, 28), "bg_bot": (8, 0, 8),
        "left_bg": (35, 0, 35), "right_bg": (10, 0, 10),
        "accent1": (220, 50, 255), "accent2": (0, 255, 200),
        "label": "PREDICTION", "badge_icon": "~ ", "icon": "PREDICT",
        "badge_color": (90, 20, 140),
        "stat1": "415mi", "stat2": "62mi",
    },
    {
        "theme": "shocking",
        "bg": (15, 0, 40), "bg_top": (22, 0, 55), "bg_bot": (6, 0, 18),
        "left_bg": (30, 0, 60), "right_bg": (10, 0, 20),
        "accent1": (130, 50, 255), "accent2": (0, 255, 100),
        "label": "DEEP DIVE", "badge_icon": "# ", "icon": "DATA",
        "badge_color": (50, 20, 120),
        "stat1": "198mi", "stat2": "44mi",
    },
    {
        "theme": "shocking",
        "bg": (25, 0, 15), "bg_top": (36, 0, 22), "bg_bot": (10, 0, 6),
        "left_bg": (40, 0, 25), "right_bg": (15, 0, 5),
        "accent1": (255, 0, 200), "accent2": (255, 200, 0),
        "label": "WARNING", "badge_icon": "! ", "icon": "ALERT",
        "badge_color": (120, 0, 80),
        "stat1": "521mi", "stat2": "95mi",
    },

    # ══════════════════════════════════════════════════════════════════════
    # THEME 2: "crash" — Dark Teal/Navy, Prices Crashed (bkz. Image 2)
    # ══════════════════════════════════════════════════════════════════════
    {
        "theme": "crash",
        "bg": (0, 5, 25), "bg_top": (0, 10, 35), "bg_bot": (0, 3, 12),
        "left_bg": (0, 15, 45), "right_bg": (0, 5, 15),
        "accent1": (0, 200, 140), "accent2": (220, 40, 40),
        "label": "REALITY?", "icon": "SCAM?",
        "price_high": "$1,100/kWh", "price_low": "$200/kWh",
        "big_stat": "82%", "subtitle": "WHAT HAPPENS NEXT?",
    },
    {
        "theme": "crash",
        "bg": (0, 10, 30), "bg_top": (0, 15, 42), "bg_bot": (0, 5, 15),
        "left_bg": (0, 20, 50), "right_bg": (0, 5, 20),
        "accent1": (0, 220, 180), "accent2": (240, 60, 60),
        "label": "BREAKDOWN", "icon": "TECH",
        "price_high": "$800/kWh", "price_low": "$150/kWh",
        "big_stat": "75%", "subtitle": "WHO PROFITS?",
    },
    {
        "theme": "crash",
        "bg": (0, 5, 20), "bg_top": (0, 8, 28), "bg_bot": (0, 2, 10),
        "left_bg": (0, 15, 35), "right_bg": (0, 2, 10),
        "accent1": (50, 230, 200), "accent2": (255, 100, 0),
        "label": "REAL DATA", "icon": "TEST",
        "price_high": "$600/kWh", "price_low": "$130/kWh",
        "big_stat": "65%", "subtitle": "THE REAL NUMBERS",
    },
    {
        "theme": "crash",
        "bg": (0, 15, 35), "bg_top": (0, 22, 48), "bg_bot": (0, 8, 18),
        "left_bg": (0, 30, 60), "right_bg": (0, 10, 25),
        "accent1": (0, 255, 150), "accent2": (255, 50, 50),
        "label": "REVIEW", "icon": "EV",
        "price_high": "$950/kWh", "price_low": "$180/kWh",
        "big_stat": "90%", "subtitle": "WHO GETS LEFT BEHIND?",
    },
    {
        "theme": "crash",
        "bg": (5, 5, 30), "bg_top": (8, 8, 42), "bg_bot": (2, 2, 15),
        "left_bg": (10, 10, 50), "right_bg": (0, 0, 15),
        "accent1": (0, 180, 130), "accent2": (200, 50, 50),
        "label": "EXPOSED", "icon": "DOC",
        "price_high": "$1,200/kWh", "price_low": "$120/kWh",
        "big_stat": "88%", "subtitle": "EXPERTS WARNED US",
    },

    # ══════════════════════════════════════════════════════════════════════
    # THEME 3: "nextgen" — Dark Amber/Gold, Next-Gen EVs (bkz. Image 3)
    # ══════════════════════════════════════════════════════════════════════
    {
        "theme": "nextgen",
        "bg": (15, 10, 0), "bg_top": (22, 15, 0), "bg_bot": (6, 4, 0),
        "left_bg": (30, 20, 0), "right_bg": (10, 5, 0),
        "accent1": (255, 215, 0), "accent2": (240, 240, 240),
        "label": "NEXT-GEN", "icon": "RANGE",
        "badge_text": "500 MILE RANGE", "badge_color": (100, 60, 0),
    },
    {
        "theme": "nextgen",
        "bg": (20, 15, 0), "bg_top": (30, 22, 0), "bg_bot": (8, 6, 0),
        "left_bg": (40, 30, 0), "right_bg": (10, 5, 0),
        "accent1": (255, 180, 0), "accent2": (225, 225, 225),
        "label": "500 MILES", "icon": "*",
        "badge_text": "SOLID STATE", "badge_color": (90, 55, 0),
    },
    {
        "theme": "nextgen",
        "bg": (25, 10, 0), "bg_top": (36, 15, 0), "bg_bot": (10, 4, 0),
        "left_bg": (50, 20, 0), "right_bg": (15, 5, 0),
        "accent1": (255, 160, 0), "accent2": (255, 255, 255),
        "label": "UPGRADE", "icon": "SELL",
        "badge_text": "1000 MILES", "badge_color": (110, 50, 0),
    },
    {
        "theme": "nextgen",
        "bg": (12, 10, 2), "bg_top": (18, 14, 4), "bg_bot": (5, 4, 1),
        "left_bg": (28, 22, 5), "right_bg": (6, 4, 0),
        "accent1": (255, 200, 0), "accent2": (205, 205, 205),
        "label": "RANGE", "icon": "MAX",
        "badge_text": "800 KM RANGE", "badge_color": (80, 65, 0),
    },
    {
        "theme": "nextgen",
        "bg": (15, 5, 0), "bg_top": (22, 8, 0), "bg_bot": (6, 2, 0),
        "left_bg": (30, 10, 0), "right_bg": (5, 0, 0),
        "accent1": (255, 130, 0), "accent2": (255, 220, 0),
        "label": "IMMEDIATELY", "icon": "NOW",
        "badge_text": "NEXT YEAR EV", "badge_color": (100, 40, 0),
    },

    # ══════════════════════════════════════════════════════════════════════
    # THEME 4: "scam" — Dark Navy/Cyan, Reality-or-Scam (bkz. Image 4)
    # ══════════════════════════════════════════════════════════════════════
    {
        "theme": "scam",
        "bg": (0, 8, 28), "bg_top": (0, 12, 38), "bg_bot": (0, 3, 14),
        "left_bg": (0, 15, 45), "right_bg": (0, 5, 20),
        "accent1": (0, 200, 255), "accent2": (255, 200, 0),
        "label": "FULL BREAKDOWN", "badge_icon": "* ", "icon": "DOC",
        "badge_color": (0, 28, 88),
        "badge1_text": "+ REALITY", "badge2_text": "x OR SCAM?",
        "btn_text": ">> REAL DATA INSIDE",
    },
    {
        "theme": "scam",
        "bg": (0, 5, 22), "bg_top": (0, 8, 30), "bg_bot": (0, 2, 10),
        "left_bg": (0, 12, 38), "right_bg": (0, 4, 16),
        "accent1": (0, 220, 255), "accent2": (255, 215, 0),
        "label": "DEBUNKED", "badge_icon": "~ ", "icon": "EXPOSED",
        "badge_color": (0, 22, 78),
        "badge1_text": "+ PROVEN", "badge2_text": "x MYTH?",
        "btn_text": ">> SEE THE DATA",
    },
    {
        "theme": "scam",
        "bg": (0, 10, 35), "bg_top": (0, 15, 48), "bg_bot": (0, 4, 16),
        "left_bg": (0, 20, 55), "right_bg": (0, 6, 22),
        "accent1": (50, 180, 255), "accent2": (255, 210, 0),
        "label": "TRUTH REVEALED", "badge_icon": "# ", "icon": "SCAN",
        "badge_color": (8, 32, 95),
        "badge1_text": "+ WORKS", "badge2_text": "x SCAM?",
        "btn_text": ">> REAL TESTS",
    },
    {
        "theme": "scam",
        "bg": (0, 5, 30), "bg_top": (0, 8, 42), "bg_bot": (0, 2, 14),
        "left_bg": (0, 10, 52), "right_bg": (0, 4, 22),
        "accent1": (0, 240, 255), "accent2": (255, 185, 0),
        "label": "REAL REVIEW", "badge_icon": "* ", "icon": "DATA",
        "badge_color": (0, 18, 72),
        "badge1_text": "+ LEGIT", "badge2_text": "x FRAUD?",
        "btn_text": ">> BATTERY FACTS",
    },
    {
        "theme": "scam",
        "bg": (5, 5, 30), "bg_top": (8, 8, 42), "bg_bot": (2, 2, 14),
        "left_bg": (10, 10, 50), "right_bg": (0, 0, 18),
        "accent1": (30, 200, 255), "accent2": (255, 200, 50),
        "label": "EXPOSED", "badge_icon": "~ ", "icon": "PROOF",
        "badge_color": (12, 22, 82),
        "badge1_text": "+ TRUTH", "badge2_text": "x LIE?",
        "btn_text": ">> DATA INSIDE",
    },
]

LAYOUTS = ["split", "versus", "shock", "data",
           "neon", "minimal", "alert", "cinematic", "grid", "bold"]

# ── Global stats pool ─────────────────────────────────────────────────────────
# Each entry: (display_value, short_label, RGB_color)
# Layouts that render stat cards pick 1-3 entries via random.sample().
GLOBAL_STATS_POOL = [
    # Range / mileage stats
    ("289 mi",  "MAX RANGE",        (0,   200, 140)),
    ("400 mi",  "REAL RANGE",       (0,   220, 180)),
    ("500 mi",  "CLAIMED RANGE",    (50,  230, 200)),
    ("127 mi",  "WINTER RANGE",     (255, 160,  0 )),
    ("342 mi",  "EPA RANGE",        (0,   200, 255)),
    # Charging stats
    ("18 min",  "0→80% CHARGE",     (180,   0, 255)),
    ("22 min",  "FAST CHARGE",      (210,   0, 255)),
    ("45 min",  "DC FAST",          (130,  50, 255)),
    ("8 h",     "HOME CHARGE",      (0,   180, 130)),
    # Cost / savings stats
    ("$45K",    "AVG EV PRICE",     (255, 215,   0)),
    ("$120",    "MONTHLY FUEL SAVE",(0,   255, 150)),
    ("$2.8¢",   "PER MILE COST",    (255, 200,   0)),
    ("$9K",     "5-YR SAVINGS",     (0,   220, 180)),
    # Battery / tech stats
    ("82%",     "AFTER 5 YRS",      (220,  40,  40)),
    ("90%",     "CAPACITY 8 YR",    (0,   200, 140)),
    ("100 kWh", "BATTERY SIZE",     (0,   200, 255)),
    ("150 kWh", "MEGA PACK",        (50,  180, 255)),
    # Market stats
    ("14M",     "EVs ON ROAD",      (255, 180,   0)),
    ("38%",     "MARKET SHARE",     (0,   200, 140)),
    ("2.5×",    "GROWTH RATE",      (180,   0, 255)),
    ("60%",     "COST DROP 10 YR",  (255, 215,   0)),
    # Performance stats
    ("1.9 s",   "0-60 MPH",         (255,  90,   0)),
    ("2.3 s",   "0-100 KPH",        (255, 120,   0)),
    ("670 hp",  "PEAK POWER",       (220,  40,  40)),
    ("1,020 hp","LUDICROUS MODE",   (180,   0, 255)),
]


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


# ── YouTube Premium Drawing Helpers ──────────────────────────────────────────

def _draw_car_silhouette(draw, cx, cy, scale=1.0,
                         body_color=(20, 25, 45), detail_color=(40, 50, 70)):
    """Simple EV side-profile silhouette drawn with PIL polygons."""
    w   = int(320 * scale)
    hb  = int(48  * scale)   # body rectangle height
    hc  = int(44  * scale)   # cabin height above body
    wr  = int(24  * scale)   # wheel radius

    # Positions: cy = wheel-bottom / ground line
    wcy     = cy - wr                   # wheel centre Y
    body_y2 = wcy - int(wr * 0.25)     # body bottom (slightly above wheel centre)
    body_y1 = body_y2 - hb             # body top

    # Main body rectangle
    draw.rectangle([cx - w // 2, body_y1, cx + w // 2, body_y2], fill=body_color)

    # Cabin trapezoid
    cl = cx - int(w * 0.36)
    cr = cx + int(w * 0.23)
    cabin_pts = [
        (cx - int(w * 0.43), body_y1),
        (cl, body_y1 - hc),
        (cr, body_y1 - hc),
        (cx + int(w * 0.32), body_y1),
    ]
    draw.polygon(cabin_pts, fill=body_color)

    # Windows (slightly lighter)
    wt = body_y1 - hc + 5
    wb = body_y1 - 4
    wm = (cl + cr) // 2
    draw.rectangle([cl + 5,  wt, wm - 3, wb], fill=detail_color)
    draw.rectangle([wm + 3,  wt, cr - 5, wb], fill=detail_color)

    # Wheels
    for wx in [cx - int(w * 0.29), cx + int(w * 0.24)]:
        draw.ellipse([wx - wr, wcy - wr, wx + wr, wcy + wr], fill=(15, 15, 22))
        rim = int(wr * 0.50)
        draw.ellipse([wx - rim, wcy - rim, wx + rim, wcy + rim], fill=body_color)

    # Tail-light
    tl_x = cx + w // 2 - 5
    draw.rectangle([tl_x - 6, body_y1 + hb // 3,
                    tl_x,     body_y1 + hb * 2 // 3], fill=(220, 30, 30))


def _draw_crosshair_circle(draw, cx, cy, radius, color):
    """Targeting-circle / radar ring used in the 'shocking' layout."""
    for r in [radius, int(radius * 0.65), int(radius * 0.35)]:
        draw.arc([cx - r, cy - r, cx + r, cy + r], 0, 360, fill=color, width=1)
    gap = int(radius * 0.11)
    # Horizontal
    draw.line([cx - radius, cy, cx - gap, cy], fill=color, width=1)
    draw.line([cx + gap,    cy, cx + radius, cy], fill=color, width=1)
    # Vertical
    draw.line([cx, cy - radius, cx, cy - gap], fill=color, width=1)
    draw.line([cx, cy + gap,    cx, cy + radius], fill=color, width=1)


def _draw_line_chart(draw, bx, by, bw, bh, line_col, font_func):
    """Declining price chart drawn inside an already-rendered box."""
    cx0 = bx + 22
    cy0 = by + 22
    cw  = bw - 44
    ch  = bh - 55

    # 8 data points describing a steep downward curve
    ts = [0.00, 0.10, 0.22, 0.36, 0.52, 0.67, 0.83, 1.00]
    vs = [0.01, 0.08, 0.18, 0.33, 0.52, 0.68, 0.82, 0.96]
    pts = [(cx0 + int(cw * t), cy0 + int(ch * v)) for t, v in zip(ts, vs)]

    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=line_col, width=3)

    # End-point dot
    r = 6
    draw.ellipse([pts[-1][0] - r, pts[-1][1] - r,
                  pts[-1][0] + r, pts[-1][1] + r], fill=(40, 185, 80))
    draw.ellipse([pts[0][0] - r, pts[0][1] - r,
                  pts[0][0] + r, pts[0][1] + r], fill=(200, 50, 50))

    # Year labels on x-axis
    years = ["2010", "2015", "2020", "2024"]
    f_s = font_func(13, False)
    for i, yr in enumerate(years):
        xi = cx0 + int(cw * i / (len(years) - 1))
        draw.text((xi - 16, cy0 + ch + 8), yr, font=f_s, fill=(110, 135, 148))


def _draw_wireless_pad(draw, cx, cy, color):
    """Concentric ellipses simulating a wireless charging glow pad."""
    steps = 6
    for i in range(steps, 0, -1):
        intensity = i / steps
        col = tuple(min(255, int(c * intensity * 0.70)) for c in color)
        ew = i * 38
        eh = i * 10
        draw.ellipse([cx - ew, cy - eh, cx + ew, cy + eh], outline=col, width=2)


# ── YouTube Style Layout 1: SHOCKING (Purple/AI, Image 1) ─────────────────────
def _layout_yt_shocking(W, H, lines, st, bg_image=None):
    """
    Matches Image 1 design:
    * Very dark purple gradient background
    * Left side: 4-tier stacked text (purple | silver | purple | gold)
    * Right side: faded crosshair circle + EV car silhouette + ground glow
    * Bottom-left: coloured badge with icon and label
    * Stat annotations near crosshair (e.g. '289mi ACTUAL')
    """
    a1 = st["accent1"]   # purple/violet
    a2 = st["accent2"]   # gold

    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)

    if not bg_image:
        for y in range(H):
            t = y / H
            c = _mix(st.get("bg_top", (20, 0, 42)), st.get("bg_bot", (8, 0, 14)), t)
            draw.line([(0, y), (W, y)], fill=c)

    img = _radial_glow(img, 120, H // 2, 480, a1, 0.28)
    img = _radial_glow(img, W - 80, H // 2, 380, a2, 0.09)
    draw = ImageDraw.Draw(img)

    # ── RIGHT: crosshair + car + ground glow ──
    cross_cx = int(W * 0.735)
    cross_cy = int(H * 0.40)
    cross_r  = int(H * 0.355)
    cross_col = tuple(min(255, int(c * 0.72)) for c in a1)
    _draw_crosshair_circle(draw, cross_cx, cross_cy, cross_r, cross_col)

    car_cx = int(W * 0.730)
    car_cy = int(H * 0.735)
    for r in range(5, 0, -1):
        col = tuple(min(255, int(c * (r / 5) * 0.35)) for c in a1)
        draw.ellipse([car_cx - r * 42, car_cy - r * 7,
                      car_cx + r * 42, car_cy + r * 7], fill=col)
    _draw_car_silhouette(draw, car_cx, car_cy, scale=1.0,
                         body_color=(18, 12, 32), detail_color=(38, 28, 55))

    # Stat annotations (e.g. "289mi ACTUAL" / "53mi DIFF")
    stat1 = st.get("stat1", "289mi")
    stat2 = st.get("stat2", "53mi")
    sf = _fnt(22)
    lf = _fnt(13, False)
    sx = cross_cx + int(cross_r * 0.14)
    sy = cross_cy - int(H * 0.085)
    draw.text((sx, sy), stat1, font=sf, fill=(215, 215, 235))
    draw.text((sx + int(draw.textlength(stat1, font=sf)) + 5, sy + 5),
              "ACTUAL", font=lf, fill=(145, 145, 175))
    sy2 = sy + 32
    draw.text((sx, sy2), stat2, font=sf, fill=(215, 215, 235))
    draw.text((sx + int(draw.textlength(stat2, font=sf)) + 5, sy2 + 5),
              "DIFF", font=lf, fill=(145, 145, 175))

    # ── LEFT: 4-tier text stack ──
    text_x     = 44
    zone_w     = int(W * 0.57)

    line_a = lines[0]                                # small purple (top label)
    line_b = lines[1]                                # huge silver (main subject)
    line_c_words = lines[2].split() if lines[2] else []
    if len(line_c_words) >= 2:
        line_c = " ".join(line_c_words[:-1])
        line_d = line_c_words[-1]
    elif len(line_c_words) == 1:
        line_c = ""
        line_d = line_c_words[0]
    else:
        line_c = ""
        line_d = st.get("label", "SHOCKING")

    color_a = a1
    color_b = (208, 210, 228)
    color_c = tuple(min(255, int(c * 0.78)) for c in a1)
    color_d = a2

    fa = _auto_font(draw, line_a, zone_w, 42)
    fb = _auto_font(draw, line_b, zone_w, 108)
    fc = _auto_font(draw, line_c, zone_w, 36) if line_c else None
    fd = _auto_font(draw, line_d, zone_w, 108)

    GAP = 6
    total_h = (
        _text_h(draw, line_a, fa) + GAP
        + _text_h(draw, line_b, fb) + GAP
        + (_text_h(draw, line_c, fc) + GAP if (fc and line_c) else 0)
        + _text_h(draw, line_d, fd)
    )
    y = _block_top(total_h, 28, H - 80)

    draw.text((text_x, y), line_a, font=fa, fill=color_a)
    y += _text_h(draw, line_a, fa) + GAP

    for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        draw.text((text_x + ox, y + oy), line_b, font=fb,
                  fill=tuple(c // 5 for c in color_b))
    draw.text((text_x, y), line_b, font=fb, fill=color_b)
    y += _text_h(draw, line_b, fb) + GAP

    if fc and line_c:
        draw.text((text_x, y), line_c, font=fc, fill=color_c)
        y += _text_h(draw, line_c, fc) + GAP

    for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        draw.text((text_x + ox, y + oy), line_d, font=fd,
                  fill=tuple(c // 4 for c in color_d))
    draw.text((text_x, y), line_d, font=fd, fill=color_d)

    # ── BOTTOM-LEFT BADGE ──
    badge_icon  = st.get("badge_icon", "* ")
    badge_label = st.get("label", "AI ANALYSIS")
    badge_txt   = f"{badge_icon}{badge_label}"
    bf = _fnt(21)
    bw_px = int(draw.textlength(badge_txt, font=bf))
    bx, by = 28, H - 64
    badge_bg = st.get("badge_color", (72, 0, 148))
    draw.rectangle([bx, by, bx + bw_px + 22, by + 34], fill=badge_bg)
    draw.text((bx + 10, by + 7), badge_txt, font=bf, fill=(255, 255, 255))

    return img


# ── YouTube Style Layout 2: CRASH (Dark Teal, Image 2) ────────────────────────
def _layout_yt_crash(W, H, lines, st, bg_image=None):
    """
    Matches Image 2 design:
    * Dark navy/teal gradient background
    * Left: title line | huge teal keyword | huge silver % stat | teal sub-line
    * Right: rounded chart box with declining line graph + price annotations
    * Bottom-left: subtitle question text
    """
    a1 = st["accent1"]   # teal / green
    a2 = st["accent2"]   # red / contrast

    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)

    if not bg_image:
        for y in range(H):
            t = y / H
            c = _mix(st.get("bg_top", (0, 12, 36)), st.get("bg_bot", (0, 4, 14)), t)
            draw.line([(0, y), (W, y)], fill=c)

    img = _radial_glow(img, 90, H // 3, 380, a1, 0.18)
    draw = ImageDraw.Draw(img)

    # ── RIGHT: chart box ──
    cx = int(W * 0.545)
    cy = int(H * 0.095)
    cw = int(W * 0.415)
    ch = int(H * 0.725)

    # Box outline
    draw.rectangle([cx, cy, cx + cw, cy + ch],
                   fill=(4, 16, 26),
                   outline=tuple(max(0, c // 3) for c in a1),
                   width=1)

    # Line chart
    _draw_line_chart(draw, cx, cy, cw, ch, a1, _fnt)

    # High-price label (red badge, top-left of chart)
    ph_txt = st.get("price_high", "$1,100/kWh")
    ph_f   = _fnt(17)
    ph_w   = int(draw.textlength(ph_txt, font=ph_f))
    ph_x   = cx + 14
    ph_y   = cy + 14
    draw.rectangle([ph_x, ph_y, ph_x + ph_w + 12, ph_y + 28], fill=(175, 40, 40))
    draw.text((ph_x + 6, ph_y + 6), ph_txt, font=ph_f, fill=(255, 255, 255))

    # Down arrow
    ax = cx + cw - 48
    ay = cy + 18
    draw.polygon([(ax, ay), (ax + 28, ay), (ax + 14, ay + 38)], fill=a1)

    # Low-price label (green badge, bottom-right of chart)
    pl_txt = st.get("price_low", "$200/kWh")
    pl_f   = _fnt(17)
    pl_w   = int(draw.textlength(pl_txt, font=pl_f))
    pl_x   = cx + cw - pl_w - 20
    pl_y   = cy + ch - 36
    draw.rectangle([pl_x, pl_y, pl_x + pl_w + 12, pl_y + 26], fill=(28, 148, 58))
    draw.text((pl_x + 6, pl_y + 5), pl_txt, font=pl_f, fill=(255, 255, 255))

    # ── LEFT: text stack ──
    tx    = 36
    zone  = int(W * 0.505)

    line1 = lines[0]                                        # e.g. "BATTERY PRICES"
    line2 = lines[1]                                        # e.g. "CRASHED"  (huge teal)
    stat  = st.get("big_stat", "82%")                      # huge silver
    line4 = lines[2] if lines[2] else "IN 10 YEARS"        # teal sub-line
    sub   = st.get("subtitle", "WHAT HAPPENS NEXT?")       # bottom question

    f1   = _auto_font(draw, line1, zone, 46)
    f2   = _auto_font(draw, line2, zone, 110)
    f3   = _auto_font(draw, stat,  zone, 110)
    f4   = _auto_font(draw, line4, zone, 42)
    f_sb = _fnt(22, False)

    GAP  = 4
    h1   = _text_h(draw, line1, f1)
    h2   = _text_h(draw, line2, f2)
    h3   = _text_h(draw, stat,  f3)
    h4   = _text_h(draw, line4, f4)
    tot  = h1 + GAP + h2 + GAP + h3 + GAP + h4
    y    = _block_top(tot, 28, H - 58)

    # Line 1 – white
    draw.text((tx, y), line1, font=f1, fill=(218, 220, 232))
    y += h1 + GAP

    # Line 2 – huge teal (with faint outline shadow)
    for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        draw.text((tx + ox, y + oy), line2, font=f2,
                  fill=tuple(c // 4 for c in a1))
    draw.text((tx, y), line2, font=f2, fill=a1)
    y += h2 + GAP

    # Vertical accent bar beside stat
    draw.rectangle([tx - 2, y + 2, tx + 8, y + h3 - 2], fill=a2)

    # Stat – huge silver
    for ox, oy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
        draw.text((tx + 14 + ox, y + oy), stat, font=f3, fill=(38, 38, 48))
    draw.text((tx + 14, y), stat, font=f3, fill=(196, 200, 212))
    y += h3 + GAP

    # Line 4 – teal
    draw.text((tx, y), line4, font=f4, fill=a1)

    # Subtitle at bottom
    draw.text((tx, H - 52), sub, font=f_sb, fill=(175, 188, 198))

    return img


# ── YouTube Style Layout 3: NEXTGEN (Dark Amber, Image 3) ─────────────────────
def _layout_yt_nextgen(W, H, lines, st, bg_image=None):
    """
    Matches Image 3 design:
    * Dark amber/warm gradient background
    * Left: multi-line gold/white/gold stacked text
    * Lightning bolt icons scattered upper-right area
    * Right: EV car silhouette with warm ground glow
    * Top-right: rounded badge (e.g. '500 MILE RANGE')
    """
    a1 = st["accent1"]   # gold / amber
    a2 = st["accent2"]   # white / silver

    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)

    if not bg_image:
        for y in range(H):
            t = y / H
            c = _mix(st.get("bg_top", (22, 15, 0)), st.get("bg_bot", (6, 4, 0)), t)
            draw.line([(0, y), (W, y)], fill=c)

    img = _radial_glow(img, int(W * 0.72), H // 2, 500, a1, 0.20)
    img = _radial_glow(img, 100, H // 2, 380, a1, 0.13)
    draw = ImageDraw.Draw(img)

    # ── Lightning bolts ──
    def _bolt(bx, by, sz, col):
        pts = [
            (bx + sz // 2, by),
            (bx, by + sz // 2),
            (bx + sz // 3, by + sz // 2),
            (bx - sz // 3, by + sz),
            (bx + sz, by + sz // 2),
            (bx + sz * 2 // 3, by + sz // 2),
        ]
        draw.polygon(pts, fill=col)

    bc = tuple(min(255, int(c * 0.55)) for c in a1)
    _bolt(int(W * 0.505), int(H * 0.048), 26, bc)
    _bolt(int(W * 0.565), int(H * 0.125), 19, bc)
    _bolt(int(W * 0.618), int(H * 0.028), 21, bc)

    # ── RIGHT: car + warm ground glow ──
    car_cx = int(W * 0.745)
    car_cy = int(H * 0.695)
    for r in range(6, 0, -1):
        col = tuple(min(255, int(c * (r / 6) * 0.42)) for c in a1)
        ew, eh = r * 40, r * 9
        draw.ellipse([car_cx - ew, car_cy + 8 - eh // 2,
                      car_cx + ew, car_cy + 8 + eh // 2], fill=col)
    _draw_car_silhouette(draw, car_cx, car_cy, scale=1.08,
                         body_color=(10, 8, 2), detail_color=(22, 18, 4))

    # ── TOP-RIGHT BADGE ──
    badge_txt = st.get("badge_text", "500 MILE RANGE")
    badge_bg  = st.get("badge_color", (98, 58, 0))
    bf        = _fnt(19)
    bw_px     = int(draw.textlength(badge_txt, font=bf))
    brx = W - bw_px - 34
    bry = 14
    draw.rectangle([brx, bry, brx + bw_px + 18, bry + 34], fill=badge_bg)
    draw.text((brx + 9, bry + 8), badge_txt, font=bf, fill=a1)

    # ── LEFT: text stack ──
    tx    = 30
    zone  = int(W * 0.545)

    line1 = lines[0]                       # e.g. "NEXT-GEN EVs" – gold
    line2 = lines[1]                       # e.g. "WILL MAKE YOU" – white
    words3 = lines[2].split() if lines[2] else []
    if len(words3) >= 3:
        line3a = " ".join(words3[:2])
        line3b = " ".join(words3[2:])
    elif len(words3) == 2:
        line3a, line3b = words3[0], words3[1]
    elif len(words3) == 1:
        line3a, line3b = "", words3[0]
    else:
        line3a, line3b = "", st.get("label", "IMMEDIATELY")

    f1  = _auto_font(draw, line1,  zone, 82)
    f2  = _auto_font(draw, line2,  zone, 52)
    f3a = _auto_font(draw, line3a, zone, 62) if line3a else None
    f3b = _auto_font(draw, line3b, zone, 82) if line3b else None

    GAP   = 8
    h1    = _text_h(draw, line1, f1)
    h2    = _text_h(draw, line2, f2)
    h3a   = _text_h(draw, line3a, f3a) if (f3a and line3a) else 0
    h3b   = _text_h(draw, line3b, f3b) if (f3b and line3b) else 0
    tot   = h1 + GAP + h2 + GAP + (h3a + GAP if h3a else 0) + h3b
    y     = _block_top(tot, 22, H - 26)

    # Line 1 – gold
    for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        draw.text((tx + ox, y + oy), line1, font=f1,
                  fill=tuple(c // 4 for c in a1))
    draw.text((tx, y), line1, font=f1, fill=a1)
    y += h1 + GAP

    # Line 2 – white/silver
    draw.text((tx, y), line2, font=f2, fill=a2)
    y += h2 + GAP

    # Line 3a – gold
    if f3a and line3a:
        draw.text((tx, y), line3a, font=f3a, fill=a1)
        y += h3a + GAP

    # Line 3b – gold (bigger, "IMMEDIATELY")
    if f3b and line3b:
        for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((tx + ox, y + oy), line3b, font=f3b,
                      fill=tuple(c // 4 for c in a1))
        draw.text((tx, y), line3b, font=f3b, fill=a1)

    return img


# ── YouTube Style Layout 4: SCAM (Dark Navy/Cyan, Image 4) ───────────────────
def _layout_yt_scam(W, H, lines, st, bg_image=None):
    """
    Matches Image 4 design:
    * Dark navy gradient background
    * Left: white title | huge cyan keyword | gold question
    * Top-right: dual pill badges (green + red)
    * Right: EV car with wireless charging pad glow underneath
    * Bottom-left: blue badge with icon + label
    * Bottom-center: outlined button with data label
    """
    a1 = st["accent1"]   # cyan / blue
    a2 = st["accent2"]   # gold / amber

    img = _get_base_image(W, H, st, bg_image)
    draw = ImageDraw.Draw(img)

    if not bg_image:
        for y in range(H):
            t = y / H
            c = _mix(st.get("bg_top", (0, 12, 40)), st.get("bg_bot", (0, 3, 16)), t)
            draw.line([(0, y), (W, y)], fill=c)

    img = _radial_glow(img, int(W * 0.66), H // 2, 540, a1, 0.16)
    draw = ImageDraw.Draw(img)

    # ── TOP-RIGHT: dual badge buttons ──
    bf_b  = _fnt(19)
    b1_txt = st.get("badge1_text", "+ REALITY")
    b2_txt = st.get("badge2_text", "x OR SCAM?")
    b1_w = int(draw.textlength(b1_txt, font=bf_b))
    b2_w = int(draw.textlength(b2_txt, font=bf_b))

    # Place badges so they end 16 px from right edge
    total_badge_w = b1_w + 14 + b2_w + 14 + 8  # widths + internal padding + gap
    b1_x = W - 16 - total_badge_w
    b1_y, b_h = 14, 34
    draw.rectangle([b1_x, b1_y, b1_x + b1_w + 14, b1_y + b_h], fill=(28, 135, 50))
    draw.text((b1_x + 7, b1_y + 8), b1_txt, font=bf_b, fill=(255, 255, 255))

    b2_x = b1_x + b1_w + 14 + 8
    draw.rectangle([b2_x, b1_y, b2_x + b2_w + 14, b1_y + b_h], fill=(185, 35, 35))
    draw.text((b2_x + 7, b1_y + 8), b2_txt, font=bf_b, fill=(255, 255, 255))

    # ── RIGHT: car + wireless charging pad ──
    car_cx = int(W * 0.730)
    car_cy = int(H * 0.600)
    _draw_car_silhouette(draw, car_cx, car_cy, scale=1.04,
                         body_color=(9, 13, 32), detail_color=(18, 28, 58))
    _draw_wireless_pad(draw, car_cx, car_cy + 38, a1)

    # ── LEFT: text stack ──
    tx   = 36
    zone = int(W * 0.545)

    line1 = lines[0]                                         # white, large
    line2 = lines[1]                                         # huge cyan
    line3 = lines[2] if lines[2] else "REALITY OR SCAM?"    # gold question

    f1 = _auto_font(draw, line1, zone, 68)
    f2 = _auto_font(draw, line2, zone, 114)
    f3 = _auto_font(draw, line3, zone, 46)

    GAP  = 8
    h1   = _text_h(draw, line1, f1)
    h2   = _text_h(draw, line2, f2)
    h3   = _text_h(draw, line3, f3)
    tot  = h1 + GAP + h2 + GAP + h3
    y    = _block_top(tot, 55, H - 98)

    # Line 1 – white
    draw.text((tx, y), line1, font=f1, fill=(228, 232, 245))
    y += h1 + GAP

    # Line 2 – huge cyan
    for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        draw.text((tx + ox, y + oy), line2, font=f2,
                  fill=tuple(c // 4 for c in a1))
    draw.text((tx, y), line2, font=f2, fill=a1)
    y += h2 + GAP

    # Line 3 – gold
    draw.text((tx, y), line3, font=f3, fill=a2)

    # ── BOTTOM-LEFT BADGE ──
    badge_icon  = st.get("badge_icon", "* ")
    badge_label = st.get("label", "FULL BREAKDOWN")
    badge_txt   = f"{badge_icon}{badge_label}"
    bf2   = _fnt(20)
    bw_px = int(draw.textlength(badge_txt, font=bf2))
    bx, by = 20, H - 62
    badge_bg = st.get("badge_color", (0, 26, 84))
    draw.rectangle([bx, by, bx + bw_px + 20, by + 34], fill=badge_bg)
    draw.text((bx + 9, by + 7), badge_txt, font=bf2, fill=(255, 255, 255))

    # ── BOTTOM-CENTER BUTTON ──
    btn_txt = st.get("btn_text", ">> REAL DATA INSIDE")
    btn_f   = _fnt(18)
    btn_w   = int(draw.textlength(btn_txt, font=btn_f))
    btn_x   = car_cx - btn_w // 2 - 10
    btn_y   = H - 56
    btn_bg  = tuple(max(0, c // 7) for c in a1)
    draw.rectangle([btn_x, btn_y, btn_x + btn_w + 20, btn_y + 32],
                   fill=btn_bg, outline=a1, width=2)
    draw.text((btn_x + 10, btn_y + 7), btn_txt, font=btn_f, fill=a1)

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
                topic_words = set(topic.split("_"))
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
            # ── YouTube Premium tema-based dispatch ──
            _YT_LAYOUTS = {
                "shocking": _layout_yt_shocking,
                "crash":    _layout_yt_crash,
                "nextgen":  _layout_yt_nextgen,
                "scam":     _layout_yt_scam,
            }

            theme = st.get("theme", "")
            if theme in _YT_LAYOUTS:
                img = _YT_LAYOUTS[theme](W, H, lines, st, bg_image=video_frame_img)
            else:
                # Legacy fallback for any palette without a theme key
                _legacy = {
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
                layout = random.choice(LAYOUTS)
                img = _legacy[layout](W, H, lines, st, bg_image=video_frame_img)

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
