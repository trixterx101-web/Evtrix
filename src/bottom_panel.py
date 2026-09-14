import os
import re
import subprocess
import logging
import textwrap
import tempfile
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("BottomPanel")

FONT_DIR     = "/usr/share/fonts/truetype/liberation"
FONT_BOLD    = os.path.join(FONT_DIR, "LiberationSans-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "LiberationSans-Regular.ttf")

def _fnt(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)
    except:
        return ImageFont.load_default()

THEME = {
    "electric_vehicle":        ((0, 13, 26),   (0, 212, 255)),
    "artificial_intelligence": ((13, 0, 26),   (139, 0, 255)),
    "robotics":                ((0, 26, 0),    (0, 255, 136)),
    "battery_tech":            ((26, 8, 0),    (255, 107, 0)),
    "future_tech":             ((10, 0, 16),   (255, 0, 255)),
    "default":                 ((0, 13, 26),   (0, 212, 255)),
}

STATS = {
    "electric_vehicle": [
        ("+300%", "EV SALES GROWTH",     (0, 212, 255)),
        ("500 MI", "NEW RANGE RECORD",    (255, 107, 0)),
        ("$0",     "GAS CAR FUTURE VALUE",(0, 255, 136)),
    ],
    "battery_tech": [
        ("1M KM",  "LFP LIFESPAN",        (0, 212, 255)),
        ("10 MIN", "FUTURE CHARGE TIME",  (255, 107, 0)),
        ("-45%",   "WINTER RANGE LOSS",   (0, 255, 136)),
    ],
    "artificial_intelligence": [
        ("10x",    "SPEED VS HUMAN",      (139, 0, 255)),
        ("2030",   "AGI PREDICTION",      (0, 212, 255)),
        ("$1T",    "AI MARKET 2030",      (255, 107, 0)),
    ],
    "robotics": [
        ("40%",    "JOBS AUTOMATED",      (0, 255, 136)),
        ("$1.5T",  "ROBOTICS MARKET",     (0, 212, 255)),
        ("24/7",   "ROBOT UPTIME",        (255, 107, 0)),
    ],
    "future_tech": [
        ("2030",   "FLYING CARS ETA",     (255, 0, 255)),
        ("1 TW",   "SOLAR CAPACITY",      (0, 212, 255)),
        ("8B",     "PEOPLE CONNECTED",    (0, 255, 136)),
    ],
    "default": [
        ("+300%",  "EV GROWTH 2026",      (0, 212, 255)),
        ("500 MI", "RANGE RECORD",        (255, 107, 0)),
        ("2030",   "FULL EV TARGET",      (0, 255, 136)),
    ],
}

def _split_into_chunks(text: str, words_per_chunk: int = 5) -> list[str]:
    """Split script into speaking chunks of ~5 words each."""
    clean = re.sub(r"(?i)welcome to ev[-\s]?care[-\s]?icks\.?\s*", "", text)
    clean = re.sub(r"[^a-zA-Z0-9 .,!?%\-]", " ", clean).strip()
    words  = clean.upper().split()
    chunks = []
    for i in range(0, len(words), words_per_chunk):
        chunk = " ".join(words[i:i + words_per_chunk])
        if chunk:
            chunks.append(chunk)
    return chunks if chunks else ["LOADING..."]

def _draw_frame(topic: str, speaking_text: str, W: int, H: int,
                progress: float = 0.5) -> Image.Image:
    """Draw a single panel frame with given speaking_text and progress (0-1)."""
    bg_rgb, acc_rgb = THEME.get(topic, THEME["default"])
    stats = STATS.get(topic, STATS["default"])

    img  = Image.new("RGB", (W, H), bg_rgb)
    draw = ImageDraw.Draw(img)

    # Background gradient
    for y in range(H):
        t = y / H
        r = min(255, int(bg_rgb[0] + 8 * t))
        g = min(255, int(bg_rgb[1] + 12 * t))
        b = min(255, int(bg_rgb[2] + 18 * t))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Top accent line
    draw.rectangle([0, 0, W, 4], fill=acc_rgb)

    brand_h = 44
    body_h  = H - brand_h
    left_w  = int(W * 0.54)
    right_x = left_w + 10

    # ── LEFT: NOW SPEAKING + animated text ───────────────────────────────────
    label_fnt = _fnt(18, bold=True)
    # Center "NOW SPEAKING" label in left panel
    lbl_w = int(draw.textlength("NOW SPEAKING", font=label_fnt))
    lbl_x = (left_w - lbl_w) // 2
    draw.text((lbl_x, 12), "NOW SPEAKING", font=label_fnt,
              fill=tuple(max(0, int(c * 0.55)) for c in acc_rgb))

    lines    = textwrap.wrap(speaking_text, width=14)[:3]
    text_fnt = _fnt(int(left_w * 0.058), bold=True)
    line_gap = int(left_w * 0.072)
    total_h  = len(lines) * line_gap
    y_text   = max(48, (body_h - total_h) // 2 + 4)

    for i, line in enumerate(lines):
        y = y_text + i * line_gap
        # Center each line in left panel
        lw = int(draw.textlength(line, font=text_fnt))
        lx = max(8, (left_w - lw) // 2)
        draw.text((lx + 2, y + 2), line, font=text_fnt, fill=(0, 0, 0))   # shadow
        draw.text((lx, y),         line, font=text_fnt, fill=(255, 255, 255))

    # Subtle vertical divider
    mid_y = body_h // 2
    for dy in range(-mid_y, mid_y):
        alpha = max(0, 60 - abs(dy) * 60 // mid_y)
        draw.point((left_w, mid_y + dy),
                   fill=tuple(min(255, int(c * alpha / 80)) for c in acc_rgb))

    # ── RIGHT: 3 stat cards ───────────────────────────────────────────────────
    card_h = (body_h - 18) // 3 - 5
    card_w = W - right_x - 12
    cy     = 8

    for value, label, color in stats:
        card_bg = tuple(min(255, int(c * 0.12 + bg_rgb[i] * 0.88))
                        for i, c in enumerate(color))
        draw.rounded_rectangle([right_x, cy, right_x + card_w, cy + card_h],
                               radius=7, fill=card_bg)
        draw.rounded_rectangle([right_x, cy, right_x + 5, cy + card_h],
                               radius=3, fill=color)
        val_fnt = _fnt(int(card_h * 0.46), bold=True)
        lbl_fnt = _fnt(int(card_h * 0.22), bold=False)
        draw.text((right_x + 14, cy + 5),
                  value, font=val_fnt, fill=color)
        draw.text((right_x + 14, cy + card_h - int(card_h * 0.30)),
                  label, font=lbl_fnt, fill=(150, 175, 195))
        cy += card_h + 7

    # ── BOTTOM brand bar ──────────────────────────────────────────────────────
    bar_y = H - brand_h
    draw.rectangle([0, bar_y, W, H], fill=(0, 0, 10))
    draw.rectangle([0, bar_y, W, bar_y + 2], fill=acc_rgb)

    # Progress bar (animated)
    prog_w = int((W - 160) * min(max(progress, 0.0), 1.0))
    draw.rectangle([0, bar_y + 2, prog_w, bar_y + 5], fill=acc_rgb)

    brand_fnt = _fnt(22, bold=True)
    draw.text((18, bar_y + 10), "EVCARIX", font=brand_fnt, fill=acc_rgb)

    tag_fnt  = _fnt(14, bold=False)
    tag_text = "EV DATA & INSIGHTS"
    tw = int(draw.textlength(tag_text, font=tag_fnt))
    draw.text((W - tw - 16, bar_y + 14), tag_text,
              font=tag_fnt, fill=(120, 150, 170))

    return img


def generate_bottom_panel(
    topic: str,
    subtitle_text: str,
    duration: float,
    output_path: str,
    panel_size: tuple = (1080, 480)
) -> str | None:
    W, H = panel_size
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    safe_dur    = max(duration, 1.0)
    chunks      = _split_into_chunks(subtitle_text, words_per_chunk=5)
    chunk_dur   = safe_dur / len(chunks)   # seconds per chunk
    fps         = 2                         # 2fps — smooth enough, very light
    frame_dir   = os.path.join(tempfile.gettempdir(), f"bp_frames_{os.getpid()}")
    os.makedirs(frame_dir, exist_ok=True)

    try:
        # Generate one frame per chunk (shown for chunk_dur seconds each)
        frame_paths = []
        for ci, chunk in enumerate(chunks):
            progress   = (ci + 0.5) / len(chunks)
            frame_img  = _draw_frame(topic, chunk, W, H, progress)
            frame_path = os.path.join(frame_dir, f"frame_{ci:04d}.jpg")
            frame_img.save(frame_path, "JPEG", quality=90)
            frame_paths.append((frame_path, chunk_dur))

        # Build a video from frames using ffmpeg concat demuxer
        list_path = os.path.join(frame_dir, "frames.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for fpath, fdur in frame_paths:
                clean_fpath = fpath.replace("\\", "/")
                f.write(f"file '{clean_fpath}'\n")
                f.write(f"duration {fdur:.3f}\n")
            # Repeat last frame once (required by concat demuxer)
            last_clean = frame_paths[-1][0].replace("\\", "/")
            f.write(f"file '{last_clean}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_path,
            "-vf", f"scale={W}:{H},setsar=1,fps={fps}",
            "-c:v", "libx264", "-crf", "26", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-an",
            "-t", str(round(safe_dur, 3)),
            "-threads", "2",
            output_path
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        # Cleanup frames
        import shutil
        try:
            shutil.rmtree(frame_dir)
        except:
            pass

        if r.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path) // 1024
            logger.info(f"[BottomPanel] ✅ {output_path} ({size}KB, {len(chunks)} chunks)")
            return output_path

        logger.error(f"[BottomPanel] FFmpeg error: {r.stderr[-300:]}")

    except Exception as e:
        logger.error(f"[BottomPanel] Exception: {e}")
        import shutil
        try:
            shutil.rmtree(frame_dir)
        except:
            pass

    return _fallback_panel(topic, safe_dur, output_path, W, H)


def _fallback_panel(topic: str, duration: float, output_path: str,
                    W: int, H: int) -> str | None:
    bg_map = {
        "electric_vehicle": "0x001833", "battery_tech": "0x1a0800",
        "artificial_intelligence": "0x0d001a", "robotics": "0x001a00",
        "future_tech": "0x0a0010",
    }
    bg  = bg_map.get(topic, "0x001020")
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c={bg}:size={W}x{H}:rate=2",
        "-t", str(round(max(duration, 1.0), 2)),
        "-c:v", "libx264", "-crf", "30", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-an", output_path
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=60)
    if r.returncode == 0 and os.path.exists(output_path):
        logger.info(f"[BottomPanel] Fallback ok: {output_path}")
        return output_path
    return None
