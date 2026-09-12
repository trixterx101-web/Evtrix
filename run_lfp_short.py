"""
FAST Short Video Generator — LFP Battery Topic
Bypasses heavy pipeline modules. Uses direct FFmpeg commands.
Target: produce + upload in under 2 minutes.
"""
import os, sys, glob, random, subprocess, asyncio, datetime, tempfile

# ── CONFIG ──────────────────────────────────────────────────────────
SCRIPT = (
    "They told you LFP batteries survive a million miles. "
    "Then you lose ten percent overnight. Why? "
    "It's not chemical decay. It's the voltage blind zone. "
    "LFP voltage curves are flat between eighty and thirty percent. "
    "The BMS gets confused and guesses wrong. "
    "When the battery finally balances, the lost range reappears. "
    "It's not dying faster. It's just honest. "
    "Subscribe to EVTRIX for real EV data."
)
TITLE       = "The Truth About LFP Battery 'Sudden' Drops"
DESCRIPTION = (
    "Why do LFP batteries seem to drop range overnight? It's not what you think.\n"
    "We explain the voltage blind zone. No hype. Just numbers.\n\n"
    "#EVTRIX #ElectricVehicles #LFP #BatteryTech #EVData #Shorts #EVShorts"
)
TAGS = ["ev", "electric vehicle", "lfp battery", "nmc vs lfp",
        "battery degradation", "ev range", "evtrix", "shorts", "evshorts"]

W, H         = 1080, 1920  # YouTube Shorts resolution (9:16)
CLIP_SECONDS = 5           # Each clip segment duration

def log(msg):
    print(msg, flush=True)

# ── STEP 1: TTS ─────────────────────────────────────────────────────
async def generate_audio(output_path: str) -> float:
    import edge_tts
    log("🎙️ [1/4] Generating audio...")
    comm = edge_tts.Communicate(SCRIPT, "en-US-JennyNeural")
    await asyncio.wait_for(comm.save(output_path), timeout=45)
    # get duration
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", output_path],
        capture_output=True, text=True
    )
    dur = float(r.stdout.strip())
    log(f"   ✅ Audio ready: {dur:.1f}s")
    return dur

# ── STEP 2: Get local clips ─────────────────────────────────────────
def get_clips(count: int) -> list[str]:
    log(f"🎬 [2/4] Selecting {count} local clips...")
    all_mp4 = glob.glob("assets/footage/pexels_*.mp4") + glob.glob("assets/footage/pixabay_*.mp4")
    if not all_mp4:
        log("❌ No footage clips found in assets/footage/")
        sys.exit(1)
    random.shuffle(all_mp4)
    selected = all_mp4[:count]
    log(f"   ✅ Using {len(selected)} clips")
    return selected

# ── STEP 3: Assemble video with ONE ffmpeg call ─────────────────────
def assemble_video(clips: list[str], audio_path: str, duration: float, output_path: str):
    log("🎞️ [3/4] Assembling video (single FFmpeg pass)...")
    
    clip_dur = max(3.0, duration / len(clips))
    
    # Build inputs
    inputs = []
    for clip in clips:
        inputs += ["-stream_loop", "-1", "-i", os.path.abspath(clip)]
    # Add audio as last input
    audio_idx = len(clips)
    inputs += ["-i", os.path.abspath(audio_path)]
    
    # Build filter: scale+crop each clip, concat, then pad to 9:16
    scale_parts = []
    for i in range(len(clips)):
        scale_parts.append(
            f"[{i}:v]trim=duration={clip_dur:.2f},setpts=PTS-STARTPTS,"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fps=24[v{i}]"
        )
    
    concat_in = "".join(f"[v{i}]" for i in range(len(clips)))
    
    filter_complex = (
        ";".join(scale_parts) + ";" +
        f"{concat_in}concat=n={len(clips)}:v=1:a=0[vout]"
    )
    
    cmd = (
        ["ffmpeg", "-y"] + inputs +
        ["-filter_complex", filter_complex,
         "-map", "[vout]", "-map", f"{audio_idx}:a",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
         "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k",
         "-t", f"{duration:.2f}",
         "-shortest",
         output_path]
    )
    
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log(f"❌ FFmpeg failed:\n{r.stderr[-500:]}")
        sys.exit(1)
    
    size_mb = os.path.getsize(output_path) / (1024*1024)
    log(f"   ✅ Video assembled: {output_path} ({size_mb:.1f} MB)")

# ── STEP 4: Upload ──────────────────────────────────────────────────
def upload_to_youtube(video_path: str):
    log("⬆️ [4/4] Uploading to YouTube...")
    from src.uploader import YouTubeUploader
    
    secret = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
    if not os.path.exists(secret):
        log(f"⚠️ {secret} not found. Skipping upload.")
        return
    
    uploader = YouTubeUploader(secret)
    if not uploader.youtube:
        log("⚠️ YouTube auth failed. Skipping upload.")
        return
    
    video_id = uploader.upload_video(
        file_path=video_path,
        title=TITLE,
        description=DESCRIPTION,
        tags=TAGS,
        playlist_name="Short Video",
        topic="LFP Batteries"
    )
    if video_id:
        log(f"   ✅ Uploaded! Video ID: {video_id}")
        log(f"   🔗 https://www.youtube.com/watch?v={video_id}")
    else:
        log("   ⚠️ Upload returned no video ID.")

# ── MAIN ─────────────────────────────────────────────────────────────
async def main():
    t0 = datetime.datetime.now()
    log("🚀 EVTRIX Fast Short Pipeline — START")
    
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("output", exist_ok=True)
    os.makedirs("assets/audio", exist_ok=True)
    
    audio_path  = f"assets/audio/lfp_short_{ts}.mp3"
    output_path = f"output/evtrix_lfp_short_{ts}.mp4"
    
    # 1. Audio
    duration = await generate_audio(audio_path)
    
    # 2. Clips
    clip_count = max(4, int(duration / CLIP_SECONDS))
    clips = get_clips(clip_count)
    
    # 3. Assemble
    assemble_video(clips, audio_path, duration, output_path)
    
    # 4. Upload
    upload_to_youtube(output_path)
    
    elapsed = (datetime.datetime.now() - t0).total_seconds()
    log(f"\n🏁 DONE in {elapsed:.0f} seconds. Output: {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
