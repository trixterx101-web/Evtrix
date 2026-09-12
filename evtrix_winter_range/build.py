"""
EVTRIX — Winter Range Video Builder
Produces:
  long/output/evtrix_winter_range_long.mp4   (1920x1080, ~5:30-6:00)
  short/output/evtrix_winter_range_short.mp4 (1080x1920, ~45-55s)
"""
import os, sys, asyncio, subprocess, datetime, glob, random
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# ── Brand Colors ─────────────────────────────────────────────────────
BG_DARK   = (3, 8, 20)
BG_MID    = (10, 20, 40)
CYAN      = (0, 210, 230)
GOLD      = (255, 200, 0)
RED_WARN  = (220, 30, 30)
GREEN_OK  = (0, 200, 120)
WHITE     = (255, 255, 255)
GREY_BLUE = (138, 160, 184)

W_LONG, H_LONG   = 1920, 1080
W_SHORT, H_SHORT = 1080, 1920

FOOTAGE_DIR = Path("assets/footage")

# ── SCRIPTS ──────────────────────────────────────────────────────────
LONG_SCENES = [
    {
        "id": 1,
        "narration": "Last year, the global EV fleet grew by a third — past fifty-five million cars on the road. And every winter, the same question floods every EV forum on earth: Why is my range disappearing? Almost everyone gives the same wrong answer.",
        "headline": "55.8M EVs",
        "subtext": "GLOBAL EV FLEET — 2024",
        "accent": CYAN,
    },
    {
        "id": 2,
        "narration": "The battery gets cold. True, but incomplete. The real villain barely gets mentioned: thermal inertia. By the end of this video, you'll know exactly why your range can drop by nearly half in winter — and a fifteen-minute rule that can claw back up to thirty percent of it, even at minus ten.",
        "headline": "THERMAL INERTIA",
        "subtext": "THE REAL VILLAIN",
        "accent": RED_WARN,
    },
    {
        "id": 3,
        "narration": "Every EV heats its cabin one of two ways. The PTC heater works exactly like a space heater — electricity in, heat out, instantly. Simple, immediate, and inefficient. The heat pump is the opposite: a compressor, a condenser, valves moving refrigerant — closer to your home's AC running backward. The number that separates them is COP, coefficient of performance. A PTC heater is stuck at a COP of 1. A well-built heat pump can hit a COP of 5.",
        "headline": "PTC  vs  HEAT PUMP",
        "subtext": "COP 1x  vs  COP 5x",
        "accent": CYAN,
    },
    {
        "id": 4,
        "narration": "Here's the chart that explains everything. Horizontal axis: minutes since you started driving. Vertical axis: outside temperature. The percentages show heat pump efficiency relative to a PTC heater. Watch what happens as we drop the temperature scenario by scenario.",
        "headline": "EFFICIENCY CHART",
        "subtext": "DRIVE TIME  ×  OUTSIDE TEMP",
        "accent": GOLD,
    },
    {
        "id": 5,
        "narration": "At fifteen degrees, this isn't even a contest. The air outside is full of usable heat, the battery is sitting near its happy zone of fifteen to thirty-five degrees, and the heat pump pulls ahead within ten minutes. By the thirty-minute mark, it's running over three-hundred-fifty percent more efficient than a PTC heater.",
        "headline": "+15°C",
        "subtext": "350%+ EFFICIENCY ADVANTAGE",
        "accent": GREEN_OK,
    },
    {
        "id": 6,
        "narration": "Now zero degrees — the line where everything gets interesting. For the first ten minutes, the PTC heater actually wins. It just dumps instant heat with no startup cost. Past that ten-minute mark, the heat pump takes over hard, climbing toward two-hundred percent efficiency. Cars without a heat pump never escape that one-to-one inefficient zone — for the entire drive.",
        "headline": "0°C — CROSSOVER POINT",
        "subtext": "HEAT PUMP WINS AFTER 10 MIN",
        "accent": GOLD,
    },
    {
        "id": 7,
        "narration": "Drop to minus ten, and physics starts pushing back harder. The break-even point slides out to about fifteen minutes — the compressor has to work much harder to pull any usable heat from that cold air. But stick with a trip past fifteen, especially past thirty minutes, and the heat pump can still deliver up to a ninety percent efficiency edge.",
        "headline": "-10°C",
        "subtext": "90% ADVANTAGE AFTER 15 MIN",
        "accent": CYAN,
    },
    {
        "id": 8,
        "narration": "At minus twenty-five, the heat pump hits a wall. Pulling heat from air that cold becomes brutally hard, and its COP collapses back toward 1 — basically a PTC heater with extra steps. This is where manufacturers switch strategies entirely: PTC first, heat pump second, or routing current through the motors themselves just to generate waste heat.",
        "headline": "-25°C — PHYSICAL LIMIT",
        "subtext": "COP COLLAPSES TO ≈ 1",
        "accent": RED_WARN,
    },
    {
        "id": 9,
        "narration": "Here's the core problem nobody puts on a spec sheet. Before a heat pump warms your cabin, it first has to warm itself — the coolant, the metal pipes, every heat exchanger in the loop. That thermal mass can carry roughly one hundred thousand joules per kelvin of pure inertia. This is exactly why a five-minute grocery run feels colder and less efficient than a forty-minute highway drive — even in the same car.",
        "headline": "100,000 J/K",
        "subtext": "THERMAL MASS — THE REAL DRAIN",
        "accent": RED_WARN,
    },
    {
        "id": 10,
        "narration": "After about fifteen minutes, something shifts. Motors and battery packs start throwing off real waste heat — and the system starts harvesting it instead of fighting the cold air outside. Combine that with a heat pump, and one kilowatt of electricity can put out up to four kilowatts of cabin heat. This single mechanism is a huge part of why EVs hold their range on longer winter drives.",
        "headline": "1 kW IN → 4 kW OUT",
        "subtext": "WASTE HEAT RECOVERY",
        "accent": GREEN_OK,
    },
    {
        "id": 11,
        "narration": "Three things you can actually use. One: precondition while you're still plugged in — let the grid pay for that startup energy, not your pack. Two: lean on seat and steering wheel heaters for short trips — heating a person costs a fraction of heating the whole cabin. Three: if you've got a garage, a gentle preheat there cuts the temperature gap the heat pump has to fight from the very first minute.",
        "headline": "3 WINTER TIPS",
        "subtext": "PRECONDITION  ·  SEAT HEAT  ·  GARAGE",
        "accent": GOLD,
    },
    {
        "id": 12,
        "narration": "Your winter range was never just about battery size. It's about the thermal inertia of everything wrapped around it. That's the data. No hype, just numbers. Subscribe to EVTRIX — there's a lot more thermal inertia left to unpack.",
        "headline": "EVTRIX",
        "subtext": "NO HYPE. JUST NUMBERS.",
        "accent": CYAN,
    },
]

SHORT_SCENES = [
    {
        "id": 1,
        "narration": "Your EV doesn't lose range because it's cold.",
        "headline": "NOT THE COLD",
        "subtext": "",
        "accent": WHITE,
    },
    {
        "id": 2,
        "narration": "It loses range because the heating system has to warm ITSELF up first — pipes, coolant, metal — before you feel a single degree.",
        "headline": "WARMS ITSELF FIRST",
        "subtext": "PIPES · COOLANT · METAL",
        "accent": CYAN,
    },
    {
        "id": 3,
        "narration": "At zero Celsius, your heat pump is actually WORSE than a basic heater... for the first ten minutes.",
        "headline": "WORSE FOR 10 MIN",
        "subtext": "AT 0°C",
        "accent": RED_WARN,
    },
    {
        "id": 4,
        "narration": "Push past that ten-minute mark, and it flips — climbing toward 200% efficiency.",
        "headline": "200% EFFICIENCY",
        "subtext": "AFTER THE CROSSOVER",
        "accent": GREEN_OK,
    },
    {
        "id": 5,
        "narration": "The fix: precondition while you're still plugged in. Let the grid eat that startup cost, not your battery.",
        "headline": "PRECONDITION\nWHILE PLUGGED IN",
        "subtext": "GRID PAYS, NOT YOUR PACK",
        "accent": GOLD,
    },
    {
        "id": 6,
        "narration": "Full breakdown — link in bio. EVTRIX. No hype. Just numbers.",
        "headline": "EVTRIX",
        "subtext": "NO HYPE. JUST NUMBERS.",
        "accent": CYAN,
    },
]

# ── HELPERS ──────────────────────────────────────────────────────────
def log(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'), flush=True)

def get_clips(count):
    all_clips = (
        glob.glob(str(FOOTAGE_DIR / "pexels_*.mp4")) +
        glob.glob(str(FOOTAGE_DIR / "pixabay_*.mp4"))
    )
    if not all_clips:
        log("[ERROR] No footage clips found in assets/footage/")
        sys.exit(1)
    random.shuffle(all_clips)
    return (all_clips * ((count // len(all_clips)) + 2))[:count]

def ffprobe_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())

# ── TTS ──────────────────────────────────────────────────────────────
async def tts(text, out_path, rate="-5%"):
    import edge_tts
    comm = edge_tts.Communicate(text, "en-US-AndrewNeural", rate=rate)
    await asyncio.wait_for(comm.save(out_path), timeout=60)

# ── FRAME GENERATION ─────────────────────────────────────────────────
def make_frame(scene, w, h, out_path):
    try:
        from PIL import Image, ImageDraw, ImageFont
        import math

        img = Image.new("RGB", (w, h), BG_DARK)
        draw = ImageDraw.Draw(img)

        # Gradient overlay
        for y in range(h):
            t = y / h
            r = int(BG_DARK[0] + (BG_MID[0] - BG_DARK[0]) * t)
            g = int(BG_DARK[1] + (BG_MID[1] - BG_DARK[1]) * t)
            b = int(BG_DARK[2] + (BG_MID[2] - BG_DARK[2]) * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # Snow/ice particles
        import random as rnd
        rnd.seed(scene["id"])
        accent = scene["accent"]
        for _ in range(60):
            px = rnd.randint(0, w)
            py = rnd.randint(0, h)
            size = rnd.randint(1, 3)
            alpha_color = tuple(int(c * 0.15) for c in accent)
            draw.ellipse([px-size, py-size, px+size, py+size], fill=alpha_color)

        # Accent top bar
        draw.rectangle([0, 0, w, 6], fill=accent)

        # EVTRIX badge (top-left)
        badge_w, badge_h = 160, 40
        draw.rectangle([24, 20, 24+badge_w, 20+badge_h], fill=BG_MID)
        draw.rectangle([24, 20, 24+badge_w, 20+badge_h], outline=accent, width=2)
        try:
            font_badge = ImageFont.truetype("fonts/Poppins-Bold.ttf", 18)
        except:
            font_badge = ImageFont.load_default()
        draw.text((24 + badge_w//2, 20 + badge_h//2), "EVTRIX",
                  font=font_badge, fill=accent, anchor="mm")

        # Scene number badge (top-right)
        scene_label = f"SCENE {scene['id']:02d}"
        try:
            font_num = ImageFont.truetype("fonts/Poppins-Bold.ttf", 16)
        except:
            font_num = ImageFont.load_default()
        draw.text((w - 30, 38), scene_label, font=font_num, fill=GREY_BLUE, anchor="rm")

        # Main headline
        headline = scene.get("headline", "")
        try:
            fs = 100 if w == 1920 else 80
            # Reduce font size for long headlines
            if len(headline) > 18:
                fs = 72 if w == 1920 else 60
            font_h = ImageFont.truetype("fonts/Poppins-Bold.ttf", fs)
        except:
            font_h = ImageFont.load_default()

        cy = h // 2 - (80 if h == 1080 else 120)
        # Glow effect (draw slightly offset in accent color)
        for dx, dy in [(-2, -2), (2, 2), (-2, 2), (2, -2)]:
            draw.text((w//2 + dx, cy + dy), headline,
                      font=font_h, fill=tuple(int(c*0.3) for c in accent), anchor="mm")
        draw.text((w//2, cy), headline, font=font_h, fill=WHITE, anchor="mm")

        # Subtext
        subtext = scene.get("subtext", "")
        if subtext:
            try:
                font_s = ImageFont.truetype("fonts/Poppins-Bold.ttf", 36 if w == 1920 else 32)
            except:
                font_s = ImageFont.load_default()
            draw.text((w//2, cy + (85 if w == 1920 else 75)), subtext,
                      font=font_s, fill=accent, anchor="mm")

        # Bottom tagline
        try:
            font_tag = ImageFont.truetype("fonts/Poppins-Bold.ttf", 22 if w == 1920 else 26)
        except:
            font_tag = ImageFont.load_default()
        draw.text((w//2, h - 40), "NO HYPE. JUST NUMBERS.",
                  font=font_tag, fill=GREY_BLUE, anchor="mm")

        # Bottom accent bar
        draw.rectangle([0, h-6, w, h], fill=accent)

        img.save(out_path)
    except ImportError:
        log("[WARN] Pillow not available -- creating color placeholder frame")
        _make_ffmpeg_frame(scene, w, h, out_path)

def _make_ffmpeg_frame(scene, w, h, out_path):
    """Fallback: solid color PNG via ffmpeg."""
    hex_col = "#{:02x}{:02x}{:02x}".format(*scene["accent"])
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=0x030814:size={w}x{h}:rate=1",
        "-vframes", "1", out_path
    ], capture_output=True)

# ── VIDEO ASSEMBLY ────────────────────────────────────────────────────
def assemble_video(scene_audio_pairs, w, h, output_path, crossfade=True):
    """scene_audio_pairs: list of (frame_png_path, audio_mp3_path, duration_sec)"""
    log(f"   [ASSEMBLE] {len(scene_audio_pairs)} scenes -> {output_path}")

    # Build a concat input file using ffmpeg concat demuxer
    tmp_clips = []
    for i, (frame, audio, dur) in enumerate(scene_audio_pairs):
        clip_path = str(output_path).replace(".mp4", f"_clip{i}.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", frame,
            "-i", audio,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-t", f"{dur:.3f}",
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
            "-r", "24",
            clip_path
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            log(f"   [ERROR] clip {i} failed: {r.stderr[-300:]}")
            sys.exit(1)
        tmp_clips.append(clip_path)

    # Concat list
    concat_file = str(output_path).replace(".mp4", "_concat.txt")
    with open(concat_file, "w") as f:
        for c in tmp_clips:
            f.write(f"file '{os.path.abspath(c)}'\n")

    # Merge
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        output_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        log(f"   [ERROR] Concat failed: {r.stderr[-400:]}")
        sys.exit(1)

    # Cleanup temp clips
    for c in tmp_clips:
        try: os.remove(c)
        except: pass
    try: os.remove(concat_file)
    except: pass

    size_mb = os.path.getsize(output_path) / (1024*1024)
    dur = ffprobe_duration(output_path)
    log(f"   [OK] {output_path}  |  {dur:.1f}s  |  {size_mb:.1f} MB")
    return dur

# ── MAIN ─────────────────────────────────────────────────────────────
async def build_video(scenes, w, h, out_dir, tts_rate, label):
    log(f"\n{'='*55}")
    log(f"  Building {label}  ({w}×{h})")
    log(f"{'='*55}")

    audio_dir  = Path(out_dir) / "audio"
    assets_dir = Path(out_dir) / "assets"
    output_dir = Path(out_dir) / "output"
    for d in [audio_dir, assets_dir, output_dir]:
        d.mkdir(parents=True, exist_ok=True)

    pairs = []
    total = 0

    for scene in scenes:
        sid = scene["id"]
        audio_path = str(audio_dir / f"scene_{sid:02d}.mp3")
        frame_path = str(assets_dir / f"frame_{sid:02d}.png")

        log(f"\n  [Scene {sid}] TTS...")
        await tts(scene["narration"], audio_path, rate=tts_rate)
        dur = ffprobe_duration(audio_path)
        total += dur
        log(f"           → {dur:.1f}s")

        log(f"  [Scene {sid}] Frame…")
        make_frame(scene, w, h, frame_path)

        pairs.append((frame_path, audio_path, dur + 0.3))  # 0.3s buffer

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "long" if w == 1920 else "short"
    out_mp4 = str(output_dir / f"evtrix_winter_range_{suffix}_{ts}.mp4")

    video_dur = assemble_video(pairs, w, h, out_mp4, crossfade=(w == 1920))
    log(f"\n  [{label}] Summary:")
    log(f"     Scenes   : {len(scenes)}")
    log(f"     Duration : {video_dur:.1f}s  ({video_dur/60:.1f} min)")
    log(f"     Output   : {out_mp4}")

    # Print timestamps
    t = 0
    for scene in scenes:
        ap = str(audio_dir / f"scene_{scene['id']:02d}.mp3")
        d = ffprobe_duration(ap)
        mm, ss = divmod(t, 60)
        log(f"     Scene {scene['id']:02d}  {int(mm):02d}:{int(ss):02d} — {scene['headline']}")
        t += d + 0.3

    return out_mp4


def upload_to_youtube(video_path: str, title: str, description: str,
                      tags: list, playlist_name: str, topic: str):
    """Upload a single video using the existing EVTRIX YouTubeUploader."""
    import sys
    sys.path.insert(0, os.path.abspath("."))  # make sure src/ is importable
    try:
        from src.uploader import YouTubeUploader
    except ImportError as e:
        log(f"[UPLOAD] Could not import uploader: {e}")
        return None

    secret = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
    if not os.path.exists(secret):
        log(f"[UPLOAD] {secret} not found — skipping upload.")
        return None

    log(f"[UPLOAD] Authenticating...")
    uploader = YouTubeUploader(secret)
    if not uploader.youtube:
        log("[UPLOAD] YouTube auth failed — skipping.")
        return None

    log(f"[UPLOAD] Uploading: {video_path}")
    log(f"[UPLOAD] Title: {title}")
    video_id = uploader.upload_video(
        file_path=video_path,
        title=title,
        description=description,
        tags=tags,
        playlist_name=playlist_name,
        topic=topic,
    )
    if video_id:
        log(f"[UPLOAD] SUCCESS  ->  https://www.youtube.com/watch?v={video_id}")
    else:
        log("[UPLOAD] Upload returned no video ID.")
    return video_id


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true",
                        help="Upload finished videos to YouTube")
    parser.add_argument("--upload-only", action="store_true",
                        help="Skip build, only upload already-rendered files")
    args = parser.parse_args()

    t0 = datetime.datetime.now()
    log("[START] EVTRIX Winter Range -- BUILD + UPLOAD")

    if not args.upload_only:
        long_mp4  = await build_video(LONG_SCENES,  W_LONG,  H_LONG,
                                      "evtrix_winter_range/long",  "-5%",  "LONG VIDEO")
        short_mp4 = await build_video(SHORT_SCENES, W_SHORT, H_SHORT,
                                      "evtrix_winter_range/short", "+5%",  "SHORT VIDEO")
    else:
        # Find latest rendered files
        import glob as _glob
        long_files  = sorted(_glob.glob("evtrix_winter_range/long/output/*.mp4"))
        short_files = sorted(_glob.glob("evtrix_winter_range/short/output/*.mp4"))
        if not long_files or not short_files:
            log("[ERROR] No rendered files found. Run without --upload-only first.")
            return
        long_mp4  = long_files[-1]
        short_mp4 = short_files[-1]
        log(f"[UPLOAD-ONLY] Using long  -> {long_mp4}")
        log(f"[UPLOAD-ONLY] Using short -> {short_mp4}")

    elapsed_build = (datetime.datetime.now() - t0).total_seconds()
    log(f"\n[DONE] Build finished in {elapsed_build:.0f}s")
    log(f"   Long  -> {long_mp4}")
    log(f"   Short -> {short_mp4}")

    if args.upload or args.upload_only:
        log("\n[UPLOAD] Starting YouTube uploads...")

        # ── Long video metadata ──────────────────────────────────
        long_title = "Why Your EV Loses 50% Range in Winter (It's Not the Cold)"
        long_desc = (
            "Your winter EV range loss has almost nothing to do with battery size. "
            "The real culprit is thermal inertia — and once you understand it, "
            "a simple 15-minute rule can recover up to 30% of your lost range even at -10C.\n\n"
            "We break down:\n"
            "- PTC heater vs Heat Pump (COP 1x vs 5x)\n"
            "- The 0C crossover point: why your heat pump loses for the first 10 minutes\n"
            "- Thermal mass: 100,000 J/K of pure inertia\n"
            "- Waste heat recovery: 1kW in, 4kW out\n"
            "- 3 actionable winter tips\n\n"
            "#EVTRIX #ElectricVehicles #EVRange #WinterEV #HeatPump #EVData #BatteryTech"
        )
        long_tags = [
            "ev", "electric vehicle", "ev range", "winter ev range",
            "heat pump ev", "ptc heater", "thermal inertia", "ev battery cold",
            "ev winter tips", "evtrix", "ev data", "cop heat pump",
            "electric car winter", "ev range loss", "battery cold weather"
        ]

        # ── Short video metadata ─────────────────────────────────
        short_title = "Why Your EV Loses Range in Winter #Shorts"
        short_desc = (
            "It's NOT the cold. It's thermal inertia.\n"
            "At 0C your heat pump is WORSE for the first 10 minutes.\n"
            "Fix: precondition while plugged in.\n\n"
            "Full breakdown: link in bio\n\n"
            "#EVTRIX #EVRange #WinterEV #ElectricVehicles #EVTips #Shorts #EVShorts"
        )
        short_tags = [
            "ev", "electric vehicle", "ev range", "winter ev",
            "heat pump", "ev tips", "evtrix", "shorts", "evshorts",
            "ev winter", "thermal inertia", "precondition ev"
        ]

        long_id  = upload_to_youtube(long_mp4,  long_title,  long_desc,
                                     long_tags,  "EV Data Reports",  "EV Winter Range")
        short_id = upload_to_youtube(short_mp4, short_title, short_desc,
                                     short_tags, "Short Video",      "EV Winter Range")

        total = (datetime.datetime.now() - t0).total_seconds()
        log(f"\n[COMPLETE] Total time: {total:.0f}s")
        if long_id:
            log(f"   Long  -> https://www.youtube.com/watch?v={long_id}")
        if short_id:
            log(f"   Short -> https://www.youtube.com/watch?v={short_id}")

if __name__ == "__main__":
    asyncio.run(main())
