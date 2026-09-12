"""
EVTRIX — Winter Range SHORT Video Builder (Footage Edition)
============================================================
Produces: evtrix_winter_range/short/output/evtrix_winter_range_short_<ts>.mp4
  - 1080x1920 (9:16 YouTube Shorts)
  - Real pexels/pixabay footage as background
  - FFmpeg drawtext overlays (headline + subtext + EVTRIX badge)
  - TTS narration via edge-tts
  - Auto-upload to YouTube after build
"""
import os, sys, glob, random, subprocess, asyncio, datetime

# ── Force UTF-8 on Windows ───────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def log(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)

# ── CONFIG ────────────────────────────────────────────────────────────
W, H = 1080, 1920
FOOTAGE_DIR = "assets/footage"
FONT_PATH   = "fonts/Poppins-Bold.ttf"

# Brand colors (hex for drawtext)
CYAN     = "00D2E6"
GOLD     = "FFC800"
RED      = "DC1E1E"
GREEN    = "00C878"
WHITE    = "FFFFFF"
GREY     = "8AA0B8"
DARK_BG  = "03081480"   # semi-transparent dark overlay

# Short scenes
SHORT_SCENES = [
    {
        "id": 1,
        "narration": "Your EV doesn't lose range because it's cold.",
        "headline":  "NOT THE COLD",
        "subtext":   "#Shorts  |  EVTRIX",
        "accent":    WHITE,
    },
    {
        "id": 2,
        "narration": "It loses range because the heating system has to warm ITSELF up first — pipes, coolant, metal — before you feel a single degree.",
        "headline":  "WARMS ITSELF FIRST",
        "subtext":   "PIPES  COOLANT  METAL",
        "accent":    CYAN,
    },
    {
        "id": 3,
        "narration": "At zero Celsius, your heat pump is actually WORSE than a basic heater for the first ten minutes.",
        "headline":  "WORSE FOR 10 MIN",
        "subtext":   "AT 0 CELSIUS",
        "accent":    RED,
    },
    {
        "id": 4,
        "narration": "Push past that ten-minute mark, and it flips — climbing toward 200% efficiency.",
        "headline":  "200% EFFICIENCY",
        "subtext":   "AFTER THE CROSSOVER",
        "accent":    GREEN,
    },
    {
        "id": 5,
        "narration": "The fix: precondition while you're still plugged in. Let the grid eat that startup cost, not your battery.",
        "headline":  "PRECONDITION",
        "subtext":   "WHILE PLUGGED IN",
        "accent":    GOLD,
    },
    {
        "id": 6,
        "narration": "Full breakdown — link in bio. EVTRIX. No hype. Just numbers.",
        "headline":  "EVTRIX",
        "subtext":   "NO HYPE. JUST NUMBERS.",
        "accent":    CYAN,
    },
]

UPLOAD_TITLE = "Why Your EV Loses Range in Winter #Shorts"
UPLOAD_DESC  = (
    "It's NOT the cold. It's thermal inertia.\n"
    "At 0C your heat pump is WORSE for the first 10 minutes.\n"
    "Fix: precondition while plugged in.\n\n"
    "Full breakdown in the long video on our channel.\n\n"
    "#EVTRIX #EVRange #WinterEV #ElectricVehicles #EVTips #Shorts #EVShorts"
)
UPLOAD_TAGS  = [
    "ev", "electric vehicle", "ev range", "winter ev",
    "heat pump", "ev tips", "evtrix", "shorts", "evshorts",
    "ev winter", "thermal inertia", "precondition ev"
]


# ── HELPERS ───────────────────────────────────────────────────────────
def ffprobe_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def get_clips(count):
    all_clips = (
        glob.glob(f"{FOOTAGE_DIR}/pexels_*.mp4") +
        glob.glob(f"{FOOTAGE_DIR}/pixabay_*.mp4")
    )
    if not all_clips:
        log("[ERROR] No footage clips found in assets/footage/")
        sys.exit(1)
    random.shuffle(all_clips)
    # Cycle if not enough clips
    return (all_clips * (count // len(all_clips) + 2))[:count]


def escape_drawtext(text):
    """Escape special characters for FFmpeg drawtext."""
    return (text
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace("%", "\\%"))


# ── TTS ───────────────────────────────────────────────────────────────
async def tts(text, out_path):
    import edge_tts
    # No rate modifier — default speed gives cleanest audio
    comm = edge_tts.Communicate(text, "en-US-AndrewNeural")
    await asyncio.wait_for(comm.save(out_path), timeout=60)


# ── SCENE CLIP BUILDER ────────────────────────────────────────────────
def build_scene_clip(footage_path, audio_path, duration, headline, subtext, accent, out_path):
    """
    Produce one scene clip:
      - footage as background (looped, scaled+cropped to 1080x1920)
      - dark semi-transparent overlay
      - top/bottom accent bars
      - EVTRIX badge top-left
      - centered headline + subtext
    """
    h_text  = escape_drawtext(headline)
    s_text  = escape_drawtext(subtext)
    accent_hex = accent  # already hex string

    # Check font availability
    font_arg = FONT_PATH if os.path.exists(FONT_PATH) else ""

    def font(size):
        if font_arg:
            return f"fontfile={font_arg}:fontsize={size}"
        return f"fontsize={size}"

    # ── Filter graph ─────────────────────────────────────────────────
    # 1) Scale footage to cover 1080x1920, crop center
    # 2) Dark overlay rectangle
    # 3) Top + bottom accent bars
    # 4) EVTRIX badge (top-left)
    # 5) Headline (center)
    # 6) Subtext (below headline)
    # 7) Bottom tagline

    vf_parts = [
        # Scale + crop to 9:16
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H}",
        # Dark overlay (drawbox)
        f"drawbox=x=0:y=0:w={W}:h={H}:color=0x030814@0.60:t=fill",
        # Top accent bar
        f"drawbox=x=0:y=0:w={W}:h=8:color=0x{accent_hex}@1.0:t=fill",
        # Bottom accent bar
        f"drawbox=x=0:y={H-8}:w={W}:h=8:color=0x{accent_hex}@1.0:t=fill",
        # EVTRIX badge background
        f"drawbox=x=24:y=20:w=160:h=44:color=0x0A1428@0.85:t=fill",
        # EVTRIX badge border
        f"drawbox=x=24:y=20:w=160:h=44:color=0x{accent_hex}@1.0:t=2",
        # EVTRIX badge text
        (f"drawtext={font(20)}:text='EVTRIX':"
         f"x=104-text_w/2:y=42-text_h/2:"
         f"fontcolor=0x{accent_hex}:box=0"),
        # Headline (center, bold, white with glow shadow)
        (f"drawtext={font(88)}:text='{h_text}':"
         f"x=(w-text_w)/2+3:y=(h-text_h)/2-120+3:"
         f"fontcolor=0x{accent_hex}@0.35:box=0"),
        (f"drawtext={font(88)}:text='{h_text}':"
         f"x=(w-text_w)/2:y=(h-text_h)/2-120:"
         f"fontcolor=0xFFFFFF:box=0"),
    ]

    if subtext:
        vf_parts.append(
            f"drawtext={font(38)}:text='{s_text}':"
            f"x=(w-text_w)/2:y=(h-text_h)/2-20:"
            f"fontcolor=0x{accent_hex}:box=0"
        )

    # Bottom tagline
    vf_parts.append(
        f"drawtext={font(26)}:text='NO HYPE. JUST NUMBERS.':"
        f"x=(w-text_w)/2:y={H-50}:"
        f"fontcolor=0x{GREY}:box=0"
    )

    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", os.path.abspath(footage_path),
        "-i", os.path.abspath(audio_path),
        "-vf", vf,
        "-af", "aresample=48000,highpass=f=80,lowpass=f=16000",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
        "-t", f"{duration:.3f}",
        "-r", "24",
        out_path
    ]

    log(f"   [FFmpeg] Scene clip -> {os.path.basename(out_path)} ({duration:.1f}s)")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log(f"   [ERROR] {r.stderr[-400:]}")
        sys.exit(1)


# ── CONCAT CLIPS ─────────────────────────────────────────────────────
def concat_clips(clip_paths, output_path):
    concat_file = output_path.replace(".mp4", "_concat.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for c in clip_paths:
            f.write(f"file '{os.path.abspath(c)}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
        output_path
    ]
    log(f"   [FFmpeg] Concat {len(clip_paths)} clips -> {os.path.basename(output_path)}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        log(f"   [ERROR] Concat: {r.stderr[-400:]}")
        sys.exit(1)

    # Cleanup
    try:
        os.remove(concat_file)
    except:
        pass

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    dur = ffprobe_duration(output_path)
    log(f"   [OK] {output_path}  |  {dur:.1f}s  |  {size_mb:.1f} MB")
    return dur


# ── UPLOAD ────────────────────────────────────────────────────────────
def upload_to_youtube(video_path):
    sys.path.insert(0, os.path.abspath("."))
    try:
        from src.uploader import YouTubeUploader
    except ImportError as e:
        log(f"[UPLOAD] Import error: {e}")
        return None

    secret = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
    if not os.path.exists(secret):
        log(f"[UPLOAD] {secret} not found — skipping.")
        return None

    log("[UPLOAD] Authenticating...")
    uploader = YouTubeUploader(secret)
    if not uploader.youtube:
        log("[UPLOAD] Auth failed — skipping.")
        return None

    log(f"[UPLOAD] Uploading: {video_path}")
    video_id = uploader.upload_video(
        file_path=video_path,
        title=UPLOAD_TITLE,
        description=UPLOAD_DESC,
        tags=UPLOAD_TAGS,
        playlist_name="Short Video",
        topic="EV Winter Range",
    )
    if video_id:
        log(f"[UPLOAD] SUCCESS -> https://www.youtube.com/watch?v={video_id}")
    else:
        log("[UPLOAD] No video ID returned.")
    return video_id


# ── MAIN ──────────────────────────────────────────────────────────────
async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-upload", action="store_true", help="Skip YouTube upload")
    args = parser.parse_args()

    t0 = datetime.datetime.now()
    log("=" * 55)
    log("  EVTRIX Winter Range SHORT — Footage Edition")
    log("=" * 55)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_dir = "evtrix_winter_range/short/audio"
    clips_dir = "evtrix_winter_range/short/clips"
    out_dir   = "evtrix_winter_range/short/output"
    for d in [audio_dir, clips_dir, out_dir]:
        os.makedirs(d, exist_ok=True)

    # Get one footage clip per scene
    footage_clips = get_clips(len(SHORT_SCENES))
    scene_clips   = []

    for i, scene in enumerate(SHORT_SCENES):
        sid = scene["id"]
        log(f"\n[Scene {sid}] TTS...")
        audio_path = os.path.join(audio_dir, f"scene_{sid:02d}_{ts}.mp3")
        await tts(scene["narration"], audio_path)  # edge-tts always saves as mp3
        dur = ffprobe_duration(audio_path)
        log(f"         -> {dur:.1f}s")

        clip_path = os.path.join(clips_dir, f"clip_{sid:02d}_{ts}.mp4")
        log(f"[Scene {sid}] Building footage clip...")
        build_scene_clip(
            footage_path=footage_clips[i],
            audio_path=audio_path,
            duration=dur + 0.25,
            headline=scene["headline"],
            subtext=scene["subtext"],
            accent=scene["accent"],
            out_path=clip_path
        )
        scene_clips.append(clip_path)

    # Concat all scenes
    log("\n[CONCAT] Merging all scenes...")
    output_path = os.path.join(out_dir, f"evtrix_winter_range_short_{ts}.mp4")
    total_dur = concat_clips(scene_clips, output_path)

    # Cleanup temp clips
    for c in scene_clips:
        try:
            os.remove(c)
        except:
            pass

    elapsed = (datetime.datetime.now() - t0).total_seconds()
    log(f"\n[DONE] Build completed in {elapsed:.0f}s")
    log(f"   Output : {output_path}")
    log(f"   Duration: {total_dur:.1f}s")

    if not args.no_upload:
        log("\n[UPLOAD] Starting YouTube upload...")
        video_id = upload_to_youtube(output_path)
        total_elapsed = (datetime.datetime.now() - t0).total_seconds()
        log(f"\n[COMPLETE] Total time: {total_elapsed:.0f}s")
        if video_id:
            log(f"   Video -> https://www.youtube.com/watch?v={video_id}")
    else:
        log("\n[SKIP] Upload skipped (--no-upload flag).")
        log(f"   To upload manually: python evtrix_winter_range/build_short_footage.py")

if __name__ == "__main__":
    asyncio.run(main())
