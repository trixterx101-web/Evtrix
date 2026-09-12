import os
import asyncio
from src.media_engine import MediaEngine
from src.footage_library import FootageLibrary
from src.editor import AutoEditor
from src.uploader import YouTubeUploader

async def run_lfp_video():
    print("🚀 Starting LFP Video Production Pipeline...")
    
    # Init components
    media_engine = MediaEngine()
    footage_library = FootageLibrary()
    editor = AutoEditor()
    
    secret_path = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
    uploader = YouTubeUploader(secret_path) if os.path.exists(secret_path) else None

    # LFP Script
    script = """They told you LFP batteries would survive a million miles. Then a driver posts a screenshot: full charge last night, ten percent gone by morning. No crash. No fault code. Just... gone. So which one is lying — the lab chart, or the dashboard? Today we pull the real data and find out. Start with the chart every manufacturer loves to show. Two curves. LFP barely bends — over four thousand charge cycles before it drops to eighty percent health. Translate that to driving, and you're looking at well over a million miles. NMC taps out twice as fast, around two thousand cycles. On paper, LFP looks unbreakable. But that chart was drawn in a lab — fixed temperature, perfect charging behavior, zero real-world chaos. The moment you leave the lab, the story gets complicated. Scroll through enough EV forums and a pattern shows up fast. "Lost ten percent overnight." "Range tanked the second it got cold." "BMS says fifty percent — feels like thirty." These aren't isolated complaints. They're a signal that something doesn't match the marketing slide. And the surprise is this: the battery usually isn't broken. The math reading it is. Here's the part almost nobody explains. Every battery management system estimates charge by reading voltage. In NMC cells, voltage falls in a smooth, predictable slope. LFP doesn't cooperate. Between roughly eighty and thirty percent state of charge, the voltage curve goes almost flat — stuck in a narrow band for most of the usable range. We call this the blind zone. The BMS can't tell seventy percent from forty percent just by reading volts, so it switches to counting energy in and out instead — a method that drifts further from reality with every cycle. That drift, not chemical decay, is the real source of most "sudden" range loss. Here's how a phantom drop actually happens, step by step. One: because of the blind zone, the BMS underestimates capacity — your screen might show ninety percent when the cells are essentially full. Two: you charge to one hundred and let the car sit. The cells balance, and the system finally sees the true voltage peak. Three: the BMS recalculates — and the "lost" range reappears, all at once, like nothing ever happened. Because nothing did. The capacity was never gone. The number was just wrong. There's a second reason LFP looks like it ages faster: buffers. To protect more fragile chemistries, manufacturers quietly reserve extra capacity at the top and bottom — capacity you never see. As an NMC pack ages, it eats into that hidden reserve first, so the dashboard barely moves. LFP cells are tougher, so the buffer is much thinner. Every percent of real wear shows up almost immediately. It's not that LFP degrades faster. It's that LFP doesn't lie to you about it. Look at the first six to twelve months of any LFP pack, and you'll usually see an early dip — two to three percent. This is the SEI layer: a thin film that forms as the chemistry settles in. It's unavoidable, it happens once, and then it stops. The problem is psychological — owners see that early drop, panic, and assume the line keeps falling. It doesn't. After settling, the curve flattens for years. To be fair, LFP isn't perfect. Drop the temperature toward freezing, and usable range can fall by as much as forty percent — noticeably worse than NMC's roughly twenty-five. Ion movement slows hard in the cold, and without preheating, charge acceptance can nearly flatline. But here's the distinction that matters: that's a performance loss, not a health loss. Warm the pack back up, and the range comes right back. The battery isn't dying in winter. It's just cold. One more myth to clear up: degradation isn't only about driving. Roughly sixty percent of total wear happens just from time passing. Only forty percent comes from actual charge cycles. Leave any LFP pack sitting at a high charge in a hot garage, and it can lose one to two percent a year doing nothing at all. So what does this look like in the real world? High-mileage rideshare and fleet vehicles — the cars that get fast-charged constantly and never babied — are consistently showing single-digit percentage loss well past one hundred thousand miles, with degradation curves that flatten hard after the first twenty to thirty thousand. At that rate, hitting the four-thousand-cycle "limit" isn't a question of chemistry — it's a question of decades most private drivers will never log. So — immortal, or marketing? Neither. LFP is honest, stable, and built for high mileage and long calendar life. NMC still wins in extreme cold and raw energy density. There's no perfect battery — only the right battery for how you actually drive. That's the data. No hype, just numbers. If you want the next breakdown before everyone else, subscribe to EVTRIX."""
    
    title = "LFP Batteries: Built to Last or Built to Confuse?"
    description = "A deep dive into the real data behind LFP battery degradation, voltage curves, and cold weather performance. No hype. Just numbers.\n\n#EVTRIX #ElectricVehicles #LFP #BatteryTech #EVData #Shorts #EVShorts"
    tags = ["ev", "electric vehicle", "lfp battery", "nmc vs lfp", "battery degradation", "ev range", "evtrix", "shorts", "evshorts"]
    
    # 1. Generate Audio
    print("🎙️ Generating audio narration...")
    os.makedirs("assets/audio", exist_ok=True)
    audio_output = "assets/audio/lfp_narration.mp3"
    voice_data = await media_engine.voice_engine.generate_voice(
        text=script,
        output_path=audio_output,
        voice_type="male"
    )
    audio_path = voice_data["audio_path"]
    
    from moviepy.editor import AudioFileClip
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    audio_clip.close()
    
    clip_count = max(6, int(duration / 5))
    
    # 2. Get Footage
    print(f"🎬 Fetching footage (need {clip_count} clips)...")
    clips = footage_library.get_fresh_clips(topic="battery_tech", count=clip_count, format="long")
    
    # 3. Assemble Video
    print("🎞️ Assembling video...")
    os.makedirs("output", exist_ok=True)
    final_video_path = "output/evtrix_lfp_final.mp4"
    
    editor.assemble(
        clips_paths=clips,
        audio_path=audio_path,
        output_path=final_video_path,
        is_short=False,  # Generating a long form format
        title=script
    )
    
    print(f"✅ Video created at: {final_video_path}")
    
    # 4. Upload
    if uploader and uploader.youtube:
        print("⬆️ Uploading to YouTube...")
        video_id = uploader.upload_video(
            file_path=final_video_path,
            title=title,
            description=description,
            tags=tags,
            playlist_name="EV Data Reports",
            thumbnail_path=None,
            topic="LFP Batteries"
        )
        print(f"✅ Uploaded successfully! Video ID: {video_id}")
        print(f"🔗 URL: https://www.youtube.com/watch?v={video_id}")
    else:
        print("⚠️ YouTube uploader not configured. Skipping upload.")

if __name__ == "__main__":
    asyncio.run(run_lfp_video())
