"""Upload the latest winter-range SHORT video to YouTube."""
import os, sys, glob
sys.path.insert(0, os.path.abspath("."))

def log(msg):
    try: print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)

short_files = sorted(glob.glob("evtrix_winter_range/short/output/*.mp4"))
if not short_files:
    log("[ERROR] No short video found in evtrix_winter_range/short/output/")
    sys.exit(1)

short_mp4 = short_files[-1]
log(f"[UPLOAD] Short video: {short_mp4}")

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

from src.uploader import YouTubeUploader

secret = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
uploader = YouTubeUploader(secret)
if not uploader.youtube:
    log("[ERROR] YouTube auth failed.")
    sys.exit(1)

video_id = uploader.upload_video(
    file_path=short_mp4,
    title=short_title,
    description=short_desc,
    tags=short_tags,
    playlist_name="Short Video",
    topic="EV Winter Range",
)
if video_id:
    log(f"[SUCCESS] https://www.youtube.com/watch?v={video_id}")
else:
    log("[ERROR] Upload failed.")
