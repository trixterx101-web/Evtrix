"""
run_episode.py — Evtrix Injected Episode Runner
================================================
Bypasses Brain / auto-topic selection.
Takes a fully pre-written script + metadata and runs it through:
  1. TTS (Edge-TTS, voice=male)
  2. B-roll footage (FootageLibrary, topic=robotics, 16:9 long)
  3. Video assembly + subtitles (AutoEditor)
  4. Thumbnail generation (ThumbnailGenerator, custom text)
  5. Thumbnail burn into first frame
  6. YouTube upload (public, playlist="Humanoid Rise")
  7. First engagement comment

Usage:
    python run_episode.py
    python run_episode.py --dry-run   (skips upload, saves video locally)
"""

import os
import sys
import asyncio
import datetime
import argparse
import textwrap

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def log(msg): print(msg, flush=True)

# ─────────────────────────────────────────────────────────────
#  EPISODE METADATA  (edit this block for each new episode)
# ─────────────────────────────────────────────────────────────

EPISODE = {
    "series":       "humanoid_rise",
    "episode":      2,
    "topic_key":    "manufacturing robots",          # FootageLibrary category (updated to get different footage)
    "voice_type":   "male",              # edge-tts male voice

    "title": (
        "Tesla's 10,000-Unit Factory: The $145K Robot Assembly Line"
    ),

    "description": textwrap.dedent("""\
        Tesla flipped the switch. 10,000 Optimus robots. 2026.
        But Goldman Sachs says each one costs $145,000 to build. Here's why that number changes everything.

        Three years ago, a humanoid cost $250,000. Today, Goldman Sachs confirms a 42% drop to $145,000.
        But at $145K build cost, Tesla needs to sell Optimus for $200K+ to make margin.
        
        Goldman breaks down the three parts that crashed in price:
        1: Actuators (down 47%)
        2: Battery (down 27%)
        3: Vision system (down 50%)

        Below the $145K "economic activation threshold", 34% of light manufacturing unlocks.
        Can it hit $50,000 by 2027? Goldman runs the model.

        CHAPTERS
        0:00 Tesla's 10,000-Unit Factory
        0:15 The Margin Problem
        1:00 Three Components That Crashed
        2:30 The $145K Economic Threshold
        4:00 2027 Projection: Sub-$50K?
        5:00 Data Analytics Friday

        SOURCE: Goldman Sachs 2026 Humanoid Robot Report, page 47; Morgan Stanley Note; Tesla Q2 2026 Shareholder Deck.

        New data every Friday 15:00 TR. Subscribe to Evtrix.

        ---
        Stock footage courtesy of Pexels, Pixabay (CC0).
        No affiliation with any manufacturer shown.
    """),

    "tags": [
        "Tesla", "Optimus", "HumanoidRobots", "GoldmanSachs",
        "RobotCost", "Evtrix", "Robotics", "Manufacturing",
        "GigaTexas", "TeslaFactory", "MorganStanley", "DataJournalism",
        "AI", "Automation", "FutureTech"
    ],

    "category_id":    "28",           # Science & Technology
    "playlist_name":  "Humanoid Rise",

    "thumbnail_text": "TESLA'S $145K ROBOT\n10,000 UNITS\n",

    # ── Full 5.5-minute voiceover script ─────────────────────
    "script": textwrap.dedent("""\
        Tesla flipped the switch. 10,000 Optimus robots. 2026. But Goldman says each one costs 145,000 dollars to build. Here's why that number changes everything.

        Three years ago, a humanoid cost 250,000 dollars. Too expensive for any factory. Today, Goldman Sachs confirms: 145,000 dollars. A 42 percent drop. But here's the trap: At 145,000 dollars build cost, Tesla needs to sell Optimus for 200,000 dollars plus to make margin. Who buys a 200,000 dollar robot? Not factories. Not yet.

        Goldman breaks it down. Three parts drove the collapse:
        One: Actuators. The robot's joints. 2022: 90,000 dollars. 2026: 48,000 dollars. Down 47 percent. Why? Chinese suppliers in Zhejiang hit scale. Harmonic drives went from hand-built to mass production.
        Two: Battery. 2022: 85,000 dollars. 2026: 62,000 dollars. Down 27 percent. CATL's new LFP cells. Energy density up, cost down.
        Three: Vision system. Cameras, lidar, compute. 2022: 50,000 dollars. 2026: 25,000 dollars. Down 50 percent. Nvidia chips crashed 30 percent after AI demand cooled.
        Total: 145,000 dollars. Goldman page 47. But Tesla's target is 25,000 dollars. We're 5.8 times away.

        So why does 145,000 dollars matter? Goldman calls it the economic activation threshold. Above 150,000 dollars, robots only work in auto plants. BMW. Mercedes. High-margin assembly. Below 145,000 dollars? 34 percent of light manufacturing unlocks. Electronics assembly. Warehouse picking. Hospital logistics. Tesla's 10,000 units aren't for sale. They're for Tesla. Giga Texas. Giga Berlin. Optimus building Model Y. If each robot replaces one 60,000 dollar worker and runs 20 hours a day, payback is 1.2 years. At 145,000 dollars cost. The math finally works.

        Can it hit 50,000 dollars by 2027? Goldman runs the model. Best case: actuators drop to 15,000 dollars, battery to 20,000 dollars, vision to 10,000 dollars. Total 45,000 dollars. But that requires Chinese supply chain to 10X volume. 88 percent probability it fails. Most likely 2027 cost: 95,000 dollars. Still too high for mass market. Tesla needs 100,000 units, not 10,000, to hit 25,000 dollars. That factory doesn't exist yet.

        Goldman gave us the data. Tesla gave us the factory. Episode 03: Figure's BMW deployment. How 1,000 robots work next to humans. New data analysis every Friday 15:00 TR. Subscribe. Link to Goldman report in description. See you next week.
    """),
}

# ─────────────────────────────────────────────────────────────
#  THUMBNAIL GENERATOR (custom text override)
# ─────────────────────────────────────────────────────────────

def generate_episode_thumbnail(title: str, custom_text: str, ts: str) -> str | None:
    """
    Calls ThumbnailGenerator with a Goldman/navy/data palette,
    then overlays the custom thumbnail text lines.
    Falls back to standard generator on any error.
    """
    try:
        from PIL import Image, ImageDraw
        from src.thumbnail_generator import _fnt, _auto_font, _text_h, _block_top, _hex

        W, H = 1280, 720
        # Navy palette matching Goldman terminal style
        NAVY      = (11, 31, 58)    # #0B1F3A
        GREY      = (90, 104, 114)  # #5A6872
        ACCENT    = (0, 115, 230)   # #0073E6
        WHITE     = (255, 255, 255)
        YELLOW    = (255, 200, 0)

        img  = Image.new("RGB", (W, H), NAVY)
        draw = ImageDraw.Draw(img)

        # ── Subtle gradient overlay ───────────────────────────────
        for y in range(H):
            t = y / H
            r = int(NAVY[0] * (1 - t * 0.4))
            g = int(NAVY[1] * (1 - t * 0.4))
            b = int(NAVY[2] * (1 - t * 0.3))
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # ── Left accent bar ───────────────────────────────────────
        draw.rectangle([0, 0, 10, H], fill=ACCENT)

        # ── Top source badge ─────────────────────────────────────
        badge = "GOLDMAN SACHS 2026 · EQUITY RESEARCH"
        bf    = _fnt(22, bold=False)
        bw    = int(draw.textlength(badge, font=bf))
        draw.rectangle([18, 18, bw + 54, 52], fill=ACCENT)
        draw.text((26, 22), badge, font=bf, fill=WHITE)

        # ── Right badge: series ───────────────────────────────────
        series_txt = "HUMANOID RISE  EP.01"
        sf  = _fnt(20, bold=False)
        sw  = int(draw.textlength(series_txt, font=sf))
        draw.rectangle([W - sw - 36, 18, W - 14, 52], fill=GREY)
        draw.text((W - sw - 22, 22), series_txt, font=sf, fill=WHITE)

        # ── Main thumbnail text (3 lines from custom_text) ───────
        raw_lines = [l.strip() for l in custom_text.strip().split("\n") if l.strip()]
        # Ensure exactly 3 lines
        while len(raw_lines) < 3:
            raw_lines.append("")
        raw_lines = raw_lines[:3]

        # Line 1 — large, yellow accent
        max_w = W - 40
        f1 = _auto_font(draw, raw_lines[0], max_w, 110)
        f2 = _auto_font(draw, raw_lines[1], max_w, 88)
        f3 = _auto_font(draw, raw_lines[2], max_w, 60, bold=False) if raw_lines[2] else None
        GAP = 16
        h1 = _text_h(draw, raw_lines[0], f1)
        h2 = _text_h(draw, raw_lines[1], f2)
        h3 = _text_h(draw, raw_lines[2], f3) if f3 else 0
        total_h = h1 + GAP + h2 + (GAP + h3 if f3 else 0)
        y1 = _block_top(total_h, 68, H - 90)

        # Line 1 outline + fill
        for ox, oy in [(-2,0),(2,0),(0,-2),(0,2)]:
            draw.text((20+ox, y1+oy), raw_lines[0], font=f1, fill=(0,60,120))
        draw.text((20, y1), raw_lines[0], font=f1, fill=YELLOW)

        y2 = y1 + h1 + GAP
        draw.text((20, y2), raw_lines[1], font=f2, fill=WHITE)

        if f3 and raw_lines[2]:
            y3 = y2 + h2 + GAP
            draw.rectangle([20, y3 - 4, 28, y3 + h3 + 4], fill=ACCENT)
            draw.text((36, y3), raw_lines[2], font=f3, fill=(180, 200, 220))

        # ── Bottom brand bar ─────────────────────────────────────
        by = H - 72
        draw.rectangle([0, by, W, H], fill=(0, 0, 0))
        draw.rectangle([0, by, W, by + 3], fill=ACCENT)
        draw.text((50, by + 18), "* EVTRIX", font=_fnt(34), fill=WHITE)
        tag = "DATA JOURNALISM"
        tw  = int(draw.textlength(tag, font=_fnt(20, bold=False)))
        draw.text((W - tw - 40, by + 24), tag, font=_fnt(20, bold=False), fill=GREY)

        # ── Corner marks ─────────────────────────────────────────
        s, t, m = 50, 5, 15
        for (x1, y_1, x2, y_2) in [
            (m, m, m+s, m+t), (m, m, m+t, m+s),
            (W-m-s, m, W-m, m+t), (W-m-t, m, W-m, m+s)
        ]:
            draw.rectangle([x1, y_1, x2, y_2], fill=ACCENT)

        os.makedirs("output/thumbnails", exist_ok=True)
        out_path = f"output/thumbnails/ep{EPISODE['episode']:02d}_{ts}.png"
        img.save(out_path, "PNG")
        log(f"      [OK] Episode thumbnail: {out_path}")
        return out_path

    except Exception as e:
        log(f"      ⚠️ Custom thumbnail failed ({e}), using standard generator...")
        try:
            from src.thumbnail_generator import ThumbnailGenerator
            tg = ThumbnailGenerator()
            return tg.create(title=title, topic="robotics")
        except Exception as e2:
            log(f"      ❌ Standard thumbnail also failed: {e2}")
            return None


# ─────────────────────────────────────────────────────────────
#  MAIN PIPELINE
# ─────────────────────────────────────────────────────────────

async def run(dry_run: bool = False):
    import math

    now = datetime.datetime.now()
    ts  = now.strftime("%Y%m%d_%H%M%S")
    ep  = EPISODE

    print(f"\n{'='*64}", flush=True)
    print(f"  Evtrix Episode Runner", flush=True)
    print(f"  Series : {ep['series'].upper()}", flush=True)
    print(f"  Episode: {ep['episode']:02d}", flush=True)
    print(f"  Title  : {ep['title'][:60]}...", flush=True)
    print(f"  Mode   : {'DRY RUN (no upload)' if dry_run else 'PRODUCTION — PUBLIC PUBLISH'}", flush=True)
    print(f"{'='*64}\n", flush=True)

    # ── Load components ───────────────────────────────────────
    log("[0/7] Loading pipeline components...")
    from src.media_engine import MediaEngine
    from src.footage_library import FootageLibrary
    from src.editor import AutoEditor
    from src.compositor import VideoCompositor
    import config

    media_engine    = MediaEngine()
    footage_library = FootageLibrary()
    editor          = AutoEditor()
    compositor      = VideoCompositor()

    uploader = None
    if not dry_run:
        secret_path = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
        if os.path.exists(secret_path):
            try:
                from src.uploader import YouTubeUploader
                uploader = YouTubeUploader(secret_path)
                log("      ✅ YouTube uploader ready.")
            except Exception as e:
                log(f"      ⚠️ Uploader failed: {e}. Video will be saved locally.")

    script     = ep["script"].strip()
    topic_key  = ep["topic_key"]
    voice_type = ep["voice_type"]

    # 12 clips is enough — AutoEditor loops/stretches them to fill the audio.
    # Fetching 60 clips would mean ~60 API calls + downloads = 5-10 min wait.
    target_duration_s = 480
    clip_count = 12

    # ── 1. Footage ────────────────────────────────────────────
    log(f"\n[1/7] Fetching B-roll footage (topic={topic_key}, count={clip_count}, fast-mode)...")

    # Fast-only: only Pexels + Pixabay (respond in <5s each).
    # NASA / Archive.org / Wikimedia are too slow for on-demand runs.
    from src.footage_library import FootageLibrary as FL
    _fl = FL()
    clip_list = []
    for _src in [_fl._fetch_pexels, _fl._fetch_pixabay]:
        if len(clip_list) >= clip_count:
            break
        try:
            got = _src(topic_key, clip_count - len(clip_list), "long")
            clip_list.extend([c for c in got if c and os.path.exists(c)])
        except Exception as _e:
            log(f"      [!] Source {_src.__name__} failed: {_e}")

    if not clip_list:
        log("      [!] No footage found — generating fallback video...")
        from src.utils.fallback import generate_fallback_video
        os.makedirs("assets/footage", exist_ok=True)
        fallback_path = f"assets/footage/fallback_ep{ep['episode']}_{ts}.mp4"
        generate_fallback_video(target_duration_s, "humanoid robots", fallback_path)
        clip_list = [fallback_path]
    log(f"      [OK] {len(clip_list)} clips collected.")

    # ── 2. TTS ────────────────────────────────────────────────
    log(f"\n[2/7] Generating TTS audio (voice={voice_type})...")
    os.makedirs("assets/audio", exist_ok=True)
    audio_output = f"assets/audio/ep{ep['episode']:02d}_{ts}.mp3"
    voice_data = await media_engine.voice_engine.generate_voice(
        text=script,
        output_path=audio_output,
        voice_type=voice_type,
    )
    if not voice_data or not voice_data.get("audio_path"):
        raise RuntimeError("[Episode Runner] TTS generation failed.")
    audio_path = voice_data["audio_path"]
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"[Episode Runner] Audio not found: {audio_path}")

    from moviepy.editor import AudioFileClip
    clip_obj = AudioFileClip(audio_path)
    duration = clip_obj.duration
    clip_obj.close()
    log(f"      [OK] Audio ready: {audio_path} ({duration:.1f}s)")

    # ── 3. Video assembly ─────────────────────────────────────
    log(f"\n[3/7] Assembling 16:9 video ({duration:.0f}s multi-clip + subtitles)...")
    import gc
    gc.collect()
    os.makedirs("output", exist_ok=True)
    output_filename  = f"evtrix_humanoid_ep{ep['episode']:02d}_{ts}.mp4"
    final_video_path = os.path.join("output", output_filename)

    assembled = editor.assemble(
        clips_paths=clip_list,
        audio_path=audio_path,
        output_path=final_video_path,
        is_short=False,
        title=f"Humanoid Rise Ep{ep['episode']:02d}",  # short slug — avoids WinError 206
    )
    if not assembled or not os.path.exists(final_video_path):
        raise RuntimeError("[Episode Runner] Video assembly failed.")
    log(f"      [OK] Video assembled: {final_video_path}")
    gc.collect()

    # ── 4. Thumbnail ──────────────────────────────────────────
    log(f"\n[4/7] Generating Goldman-style thumbnail...")
    thumbnail_path = generate_episode_thumbnail(
        title=ep["title"],
        custom_text=ep["thumbnail_text"],
        ts=ts,
    )

    # ── 5. Burn thumbnail into first frame ────────────────────
    if thumbnail_path and os.path.exists(thumbnail_path):
        log(f"\n[5/7] Burning thumbnail into first frame...")
        try:
            from src.utils.thumbnail_burn import burn_thumbnail_into_video
            final_video_path = burn_thumbnail_into_video(
                final_video_path, thumbnail_path, duration=0.5
            )
            log(f"      [OK] Thumbnail burned: {final_video_path}")
        except Exception as be:
            log(f"      [!] Thumbnail burn skipped: {be}")
    else:
        log("\n[5/7] No thumbnail — skipping burn step.")

    # ── 6. SEO package ────────────────────────────────────────
    log(f"\n[6/7] SEO package confirmed.")
    log(f"      Title : {ep['title'][:70]}")
    log(f"      Tags  : {len(ep['tags'])} tags")
    log(f"      Desc  : {len(ep['description'])} chars")

    # ── 7. Upload ─────────────────────────────────────────────
    if dry_run:
        log(f"\n[7/7] DRY RUN — skipping YouTube upload.")
        log(f"      Video saved to: {final_video_path}")
        if thumbnail_path:
            log(f"      Thumbnail at  : {thumbnail_path}")
    elif uploader and uploader.youtube and os.path.exists(final_video_path):
        log(f"\n[7/7] Uploading to YouTube (PUBLIC)...")
        try:
            video_id = uploader.upload_video(
                file_path=final_video_path,
                title=ep["title"],
                description=ep["description"],
                tags=ep["tags"],
                category_id=ep["category_id"],
                playlist_name=ep["playlist_name"],
                thumbnail_path=thumbnail_path,
                topic="humanoid robots",
            )
            log(f"      [OK] Uploaded! Video ID : {video_id}")
            log(f"      --> https://www.youtube.com/watch?v={video_id}")
        except Exception as e:
            log(f"      ❌ Upload error: {e}")
            log(f"      Video saved locally: {final_video_path}")
    else:
        log(f"\n[7/7] Uploader not available. Video saved locally: {final_video_path}")

    print(f"\n{'='*64}", flush=True)
    print(f"  [DONE] EPISODE {ep['episode']:02d} PIPELINE COMPLETE", flush=True)
    print(f"  Video : {final_video_path}", flush=True)
    if thumbnail_path:
        print(f"  Thumb : {thumbnail_path}", flush=True)
    print(f"{'='*64}\n", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evtrix Episode Runner")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate video + thumbnail without uploading to YouTube"
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(dry_run=args.dry_run))
    except KeyboardInterrupt:
        log("\n[Episode Runner] Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        import traceback
        log(f"\n[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        import glob
        cleaned = 0
        for f in glob.glob("*TEMP_MPY_wvf_snd.mp4") + glob.glob("*TEMP_MPY_wvf_snd.wav"):
            try:
                os.remove(f)
                cleaned += 1
            except Exception:
                pass
        if cleaned:
            log(f"[Cleanup] {cleaned} temp MoviePy files removed.")
