"""
EVTRIX — Winter Range Builder v3
Footage from Pexels API + FFmpeg drawtext overlay
Produces: Long (1920x1080) + Short (1080x1920) + uploads both
"""
import os, sys, glob, random, subprocess, asyncio, datetime, requests, time

# ── UTF-8 fix ─────────────────────────────────────────────────────────
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# ── Load .env ─────────────────────────────────────────────────────────
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
load_env()

PEXELS_KEY  = os.getenv("PEXELS_API_KEY", "")
PIXABAY_KEY = os.getenv("PIXABAY_API_KEY", "")
FOOTAGE_DIR = "assets/footage"
FONT_PATH   = "fonts/Poppins-Bold.ttf"

def log(msg):
    try: print(msg, flush=True)
    except: print(str(msg).encode("ascii","replace").decode(), flush=True)

# ── SCENES ────────────────────────────────────────────────────────────
LONG_SCENES = [
    {"id":1,"narration":"Last year, the global EV fleet grew by a third — past fifty-five million cars on the road. And every winter, the same question floods every EV forum on earth: Why is my range disappearing? Almost everyone gives the same wrong answer.","headline":"55.8M EVs","subtext":"GLOBAL EV FLEET — 2024","accent":"00D2E6","query":"electric car traffic city"},
    {"id":2,"narration":"The battery gets cold. True, but incomplete. The real villain barely gets mentioned: thermal inertia. By the end of this video, you'll know exactly why your range can drop by nearly half in winter — and a fifteen-minute rule that can claw back up to thirty percent of it, even at minus ten.","headline":"THERMAL INERTIA","subtext":"THE REAL VILLAIN","accent":"DC1E1E","query":"winter snow car road"},
    {"id":3,"narration":"Every EV heats its cabin one of two ways. The PTC heater works exactly like a space heater — electricity in, heat out, instantly. Simple, immediate, and inefficient. The heat pump is the opposite: a compressor, a condenser, valves moving refrigerant. The number that separates them is COP. A PTC heater is stuck at a COP of 1. A well-built heat pump can hit a COP of 5.","headline":"PTC vs HEAT PUMP","subtext":"COP 1x  vs  COP 5x","accent":"00D2E6","query":"car engine technology heating"},
    {"id":4,"narration":"Here's the chart that explains everything. Horizontal axis: minutes since you started driving. Vertical axis: outside temperature. The percentages show heat pump efficiency relative to a PTC heater. Watch what happens as we drop the temperature scenario by scenario.","headline":"EFFICIENCY CHART","subtext":"DRIVE TIME x OUTSIDE TEMP","accent":"FFC800","query":"data visualization technology screen"},
    {"id":5,"narration":"At fifteen degrees, this isn't even a contest. The air outside is full of usable heat, the battery is sitting near its happy zone, and the heat pump pulls ahead within ten minutes. By the thirty-minute mark, it's running over three-hundred-fifty percent more efficient than a PTC heater.","headline":"+15 CELSIUS","subtext":"350%+ EFFICIENCY ADVANTAGE","accent":"00C878","query":"highway driving sunny warm weather"},
    {"id":6,"narration":"Now zero degrees — the line where everything gets interesting. For the first ten minutes, the PTC heater actually wins. Past that ten-minute mark, the heat pump takes over hard, climbing toward two-hundred percent efficiency. Cars without a heat pump never escape that one-to-one inefficient zone — for the entire drive.","headline":"0C CROSSOVER POINT","subtext":"HEAT PUMP WINS AFTER 10 MIN","accent":"FFC800","query":"winter driving road zero temperature"},
    {"id":7,"narration":"Drop to minus ten, and physics starts pushing back harder. The break-even point slides out to about fifteen minutes. But stick with a trip past fifteen minutes, and the heat pump can still deliver up to a ninety percent efficiency edge.","headline":"-10 CELSIUS","subtext":"90% ADVANTAGE AFTER 15 MIN","accent":"00D2E6","query":"cold winter snow driving road"},
    {"id":8,"narration":"At minus twenty-five, the heat pump hits a wall. Pulling heat from air that cold becomes brutally hard, and its COP collapses back toward 1. This is where manufacturers switch strategies entirely: PTC first, heat pump second, or routing current through the motors themselves to generate waste heat.","headline":"-25C PHYSICAL LIMIT","subtext":"COP COLLAPSES TO 1","accent":"DC1E1E","query":"extreme cold blizzard winter storm"},
    {"id":9,"narration":"Here's the core problem nobody puts on a spec sheet. Before a heat pump warms your cabin, it first has to warm itself — the coolant, the metal pipes, every heat exchanger in the loop. That thermal mass can carry roughly one hundred thousand joules per kelvin of pure inertia. This is exactly why a five-minute grocery run feels colder than a forty-minute highway drive — even in the same car.","headline":"100,000 J/K","subtext":"THERMAL MASS — THE REAL DRAIN","accent":"DC1E1E","query":"car engine metal parts closeup"},
    {"id":10,"narration":"After about fifteen minutes, something shifts. Motors and battery packs start throwing off real waste heat — and the system starts harvesting it. Combine that with a heat pump, and one kilowatt of electricity can put out up to four kilowatts of cabin heat. This is why EVs hold their range on longer winter drives.","headline":"1 kW IN  4 kW OUT","subtext":"WASTE HEAT RECOVERY","accent":"00C878","query":"electric motor technology energy"},
    {"id":11,"narration":"Three things you can actually use. One: precondition while you're still plugged in — let the grid pay for that startup energy, not your pack. Two: lean on seat and steering wheel heaters for short trips. Three: if you've got a garage, a gentle preheat there cuts the temperature gap the heat pump has to fight from the very first minute.","headline":"3 WINTER TIPS","subtext":"PRECONDITION - SEAT HEAT - GARAGE","accent":"FFC800","query":"ev charging station plug cable"},
    {"id":12,"narration":"Your winter range was never just about battery size. It's about the thermal inertia of everything wrapped around it. That's the data. No hype, just numbers. Subscribe to EVTRIX — there's a lot more thermal inertia left to unpack.","headline":"EVTRIX","subtext":"NO HYPE. JUST NUMBERS.","accent":"00D2E6","query":"electric car future technology"},
]

SHORT_SCENES = [
    {"id":1,"narration":"Your EV doesn't lose range because it's cold.","headline":"NOT THE COLD","subtext":"#Shorts  |  EVTRIX","accent":"FFFFFF","query":"electric car snow winter"},
    {"id":2,"narration":"It loses range because the heating system has to warm ITSELF up first — pipes, coolant, metal — before you feel a single degree.","headline":"WARMS ITSELF FIRST","subtext":"PIPES  COOLANT  METAL","accent":"00D2E6","query":"car heating pipes metal engine"},
    {"id":3,"narration":"At zero Celsius, your heat pump is actually WORSE than a basic heater for the first ten minutes.","headline":"WORSE FOR 10 MIN","subtext":"AT 0 CELSIUS","accent":"DC1E1E","query":"winter cold road driving snow"},
    {"id":4,"narration":"Push past that ten-minute mark, and it flips — climbing toward 200% efficiency.","headline":"200% EFFICIENCY","subtext":"AFTER THE CROSSOVER","accent":"00C878","query":"electric vehicle highway driving"},
    {"id":5,"narration":"The fix: precondition while you're still plugged in. Let the grid eat that startup cost, not your battery.","headline":"PRECONDITION","subtext":"WHILE PLUGGED IN","accent":"FFC800","query":"ev charging cable plug station"},
    {"id":6,"narration":"Full breakdown — link in bio. EVTRIX. No hype. Just numbers.","headline":"EVTRIX","subtext":"NO HYPE. JUST NUMBERS.","accent":"00D2E6","query":"electric car future city"},
]

# ── FOOTAGE DOWNLOAD ──────────────────────────────────────────────────
os.makedirs(FOOTAGE_DIR, exist_ok=True)

def pexels_download(query, orientation="landscape", out_prefix="winter"):
    """Download one clip from Pexels matching query. Returns path or None."""
    if not PEXELS_KEY:
        return None
    safe_q = query.replace(" ", "+")
    url = f"https://api.pexels.com/videos/search?query={safe_q}&per_page=5&orientation={orientation}&page={random.randint(1,3)}"
    try:
        r = requests.get(url, headers={"Authorization": PEXELS_KEY}, timeout=10)
        if r.status_code != 200:
            return None
        videos = r.json().get("videos", [])
        random.shuffle(videos)
        for v in videos:
            vid_id = v["id"]
            out = os.path.join(FOOTAGE_DIR, f"pexels_{vid_id}.mp4")
            if os.path.exists(out) and os.path.getsize(out) > 50000:
                return out
            files = sorted(
                [f for f in v.get("video_files", []) if f.get("width", 0) >= 720],
                key=lambda x: x.get("width", 0)
            )
            if not files:
                continue
            dl_url = files[0]["link"]
            try:
                dr = requests.get(dl_url, stream=True, timeout=(5, 30))
                if dr.status_code == 200:
                    with open(out, "wb") as f:
                        for chunk in dr.iter_content(65536):
                            f.write(chunk)
                    if os.path.getsize(out) > 50000:
                        log(f"   [Pexels] Downloaded: pexels_{vid_id}.mp4")
                        return out
                    os.remove(out)
            except Exception as e:
                log(f"   [Pexels] Download failed: {e}")
    except Exception as e:
        log(f"   [Pexels] API error: {e}")
    return None

def get_local_fallback():
    """Get random local clip."""
    clips = glob.glob(f"{FOOTAGE_DIR}/pexels_*.mp4") + glob.glob(f"{FOOTAGE_DIR}/pixabay_*.mp4")
    if not clips:
        log("[ERROR] No local footage clips found!")
        sys.exit(1)
    return random.choice(clips)

def get_clip_for_scene(query, orientation="landscape"):
    """Try Pexels first, fallback to local."""
    clip = pexels_download(query, orientation)
    if clip:
        return clip
    log(f"   [Fallback] Using local clip for: {query}")
    return get_local_fallback()

# ── TTS ───────────────────────────────────────────────────────────────
async def tts(text, out_path):
    import edge_tts
    comm = edge_tts.Communicate(text, "en-US-AndrewNeural")
    await asyncio.wait_for(comm.save(out_path), timeout=60)

def ffprobe_dur(path):
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try: return float(r.stdout.strip())
    except: return 0.0

# ── SCENE CLIP BUILDER ────────────────────────────────────────────────
def esc(text):
    return (text.replace("\\","\\\\").replace("'","\\'")
                .replace(":","\\:").replace("%","\\%"))

def build_clip(footage, audio, duration, headline, subtext, accent, w, h, out):
    font = f"fontfile='{FONT_PATH}':" if os.path.exists(FONT_PATH) else ""
    hs = 88 if w == 1920 else 80
    if len(headline) > 16: hs = 72 if w == 1920 else 66
    ss = 36 if w == 1920 else 34
    cy_h = int(h * 0.45)
    cy_s = cy_h + hs + 10

    vf = ",".join([
        f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
        f"drawbox=x=0:y=0:w={w}:h={h}:color=0x030814@0.58:t=fill",
        f"drawbox=x=0:y=0:w={w}:h=8:color=0x{accent}@1:t=fill",
        f"drawbox=x=0:y={h-8}:w={w}:h=8:color=0x{accent}@1:t=fill",
        f"drawbox=x=24:y=20:w=164:h=46:color=0x0A1428@0.9:t=fill",
        f"drawbox=x=24:y=20:w=164:h=46:color=0x{accent}@1:t=2",
        f"drawtext={font}fontsize=20:text='EVTRIX':x=106-text_w/2:y=43-text_h/2:fontcolor=0x{accent}",
        f"drawtext={font}fontsize={hs}:text='{esc(headline)}':x=(w-text_w)/2+3:y={cy_h}+3:fontcolor=0x{accent}@0.35",
        f"drawtext={font}fontsize={hs}:text='{esc(headline)}':x=(w-text_w)/2:y={cy_h}:fontcolor=0xFFFFFF",
        *([ f"drawtext={font}fontsize={ss}:text='{esc(subtext)}':x=(w-text_w)/2:y={cy_s}:fontcolor=0x{accent}" ] if subtext else []),
        f"drawtext={font}fontsize=24:text='NO HYPE. JUST NUMBERS.':x=(w-text_w)/2:y={h-46}:fontcolor=0x8AA0B8",
    ])

    cmd = ["ffmpeg","-y",
           "-stream_loop","-1","-i", os.path.abspath(footage),
           "-i", os.path.abspath(audio),
           "-vf", vf,
           "-af","aresample=48000,highpass=f=80,lowpass=f=16000",
           "-c:v","libx264","-preset","ultrafast","-crf","22",
           "-pix_fmt","yuv420p",
           "-c:a","aac","-b:a","320k","-ar","48000",
           "-t", f"{duration:.3f}", "-r","24", out]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log(f"   [ERROR] clip: {r.stderr[-300:]}")
        sys.exit(1)

def concat_clips(clip_paths, output_path):
    txt = output_path.replace(".mp4","_cat.txt")
    with open(txt,"w",encoding="utf-8") as f:
        for c in clip_paths:
            f.write(f"file '{os.path.abspath(c)}'\n")
    cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",txt,
           "-c:v","libx264","-preset","ultrafast","-crf","21",
           "-pix_fmt","yuv420p",
           "-c:a","aac","-b:a","320k","-ar","48000", output_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        log(f"   [ERROR] concat: {r.stderr[-300:]}")
        sys.exit(1)
    try: os.remove(txt)
    except: pass
    dur = ffprobe_dur(output_path)
    sz  = os.path.getsize(output_path)/1024/1024
    log(f"   [OK] {os.path.basename(output_path)} | {dur:.1f}s | {sz:.1f} MB")
    return dur

# ── BUILD ─────────────────────────────────────────────────────────────
async def build_video(scenes, w, h, orientation, label, out_base):
    log(f"\n{'='*55}")
    log(f"  {label}  ({w}x{h})")
    log(f"{'='*55}")
    audio_dir  = f"{out_base}/audio"
    clips_dir  = f"{out_base}/clips"
    output_dir = f"{out_base}/output"
    for d in [audio_dir, clips_dir, output_dir]:
        os.makedirs(d, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    scene_clips = []

    for scene in scenes:
        sid = scene["id"]
        log(f"\n  [Scene {sid}/{len(scenes)}] TTS: {scene['headline']}")
        ap = f"{audio_dir}/s{sid:02d}_{ts}.mp3"
        await tts(scene["narration"], ap)
        dur = ffprobe_dur(ap)
        log(f"    -> {dur:.1f}s audio")

        log(f"  [Scene {sid}] Footage: {scene['query']}")
        footage = get_clip_for_scene(scene["query"], orientation)
        log(f"    -> {os.path.basename(footage)}")

        cp = f"{clips_dir}/c{sid:02d}_{ts}.mp4"
        build_clip(footage, ap, dur+0.25,
                   scene["headline"], scene["subtext"], scene["accent"],
                   w, h, cp)
        scene_clips.append(cp)

    suffix = "long" if w==1920 else "short"
    out_mp4 = f"{output_dir}/evtrix_winter_range_{suffix}_{ts}.mp4"
    log(f"\n  [CONCAT] Merging {len(scene_clips)} clips...")
    total_dur = concat_clips(scene_clips, out_mp4)

    for c in scene_clips:
        try: os.remove(c)
        except: pass

    log(f"\n  [{label}] Done: {out_mp4} ({total_dur:.1f}s)")
    return out_mp4

# ── UPLOAD ────────────────────────────────────────────────────────────
def upload(path, title, desc, tags, playlist, topic):
    sys.path.insert(0, os.path.abspath("."))
    try:
        from src.uploader import YouTubeUploader
    except ImportError as e:
        log(f"[UPLOAD] Import error: {e}"); return None
    secret = os.getenv("YOUTUBE_CLIENT_SECRET_FILE","client_secret.json")
    if not os.path.exists(secret):
        log(f"[UPLOAD] {secret} not found"); return None
    log(f"[UPLOAD] Uploading: {os.path.basename(path)}")
    up = YouTubeUploader(secret)
    if not up.youtube:
        log("[UPLOAD] Auth failed"); return None
    vid_id = up.upload_video(file_path=path, title=title,
                             description=desc, tags=tags,
                             playlist_name=playlist, topic=topic)
    if vid_id:
        log(f"[UPLOAD] SUCCESS -> https://www.youtube.com/watch?v={vid_id}")
    return vid_id

# ── MAIN ─────────────────────────────────────────────────────────────
async def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--no-upload", action="store_true")
    p.add_argument("--short-only", action="store_true")
    p.add_argument("--long-only",  action="store_true")
    args = p.parse_args()

    t0 = datetime.datetime.now()
    log("[START] EVTRIX Winter Range v3 — Footage Edition")

    long_mp4 = short_mp4 = None

    if not args.short_only:
        long_mp4 = await build_video(
            LONG_SCENES, 1920, 1080, "landscape",
            "LONG VIDEO", "evtrix_winter_range/long"
        )

    if not args.long_only:
        short_mp4 = await build_video(
            SHORT_SCENES, 1080, 1920, "portrait",
            "SHORT VIDEO", "evtrix_winter_range/short"
        )

    elapsed = (datetime.datetime.now()-t0).total_seconds()
    log(f"\n[BUILD DONE] {elapsed:.0f}s")
    if long_mp4:  log(f"  Long  -> {long_mp4}")
    if short_mp4: log(f"  Short -> {short_mp4}")

    if args.no_upload:
        log("[SKIP] Upload skipped."); return

    LONG_DESC = (
        "Your winter EV range loss has almost nothing to do with battery size.\n"
        "The real culprit is thermal inertia — and once you understand it,\n"
        "a simple 15-minute rule can recover up to 30% of your lost range.\n\n"
        "Topics: PTC heater vs Heat Pump (COP 1x vs 5x), the 0C crossover,\n"
        "100,000 J/K thermal mass, waste heat recovery, 3 winter tips.\n\n"
        "#EVTRIX #ElectricVehicles #EVRange #WinterEV #HeatPump #EVData"
    )
    SHORT_DESC = (
        "It's NOT the cold. It's thermal inertia.\n"
        "At 0C your heat pump is WORSE for the first 10 minutes.\n"
        "Fix: precondition while plugged in.\n\n"
        "Full breakdown on our channel.\n\n"
        "#EVTRIX #EVRange #WinterEV #ElectricVehicles #EVTips #Shorts #EVShorts"
    )
    BASE_TAGS = ["ev","electric vehicle","ev range","winter ev","heat pump",
                 "evtrix","ev data","thermal inertia","ev winter tips"]

    if long_mp4:
        upload(long_mp4,
               "Why Your EV Loses 50% Range in Winter (It's Not the Cold)",
               LONG_DESC, BASE_TAGS + ["ev range loss","battery cold weather"],
               "EV Data Reports", "EV Winter Range")

    if short_mp4:
        upload(short_mp4,
               "Why Your EV Loses Range in Winter #Shorts",
               SHORT_DESC, BASE_TAGS + ["shorts","evshorts","precondition ev"],
               "Short Video", "EV Winter Range")

    total = (datetime.datetime.now()-t0).total_seconds()
    log(f"\n[COMPLETE] Total: {total:.0f}s")

if __name__ == "__main__":
    asyncio.run(main())
