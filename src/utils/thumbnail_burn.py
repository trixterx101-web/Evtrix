"""
src/utils/thumbnail_burn.py
============================
Thumbnail görselini videonun ilk karesine gömer (Shorts uyumlu).

16:9 thumbnail'i 9:16 Shorts formatına dönüştürür:
- Thumbnail'i canvas ortasına yerleştirir
- Üstüne/altına marka gradient ekler
- Sessiz ses track'ı ile concat yapar (ses kaybını önler)
"""

import os
import subprocess
import shutil


def burn_thumbnail_into_video(video_path: str, thumbnail_path: str, duration: float = 0.5) -> str:
    """
    Thumbnail'i videonun başına freeze-frame olarak ekler.
    16:9 thumbnail → 9:16 Shorts uyumlu dönüşüm.
    """
    if not video_path or not os.path.exists(video_path):
        print(f"[ThumbnailBurn] Video bulunamadı: {video_path}")
        return video_path
    
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        print(f"[ThumbnailBurn] Thumbnail bulunamadı: {thumbnail_path}")
        return video_path

    try:
        # ── 1. Videonun boyut + ses bilgisini al ─────────────────
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "csv=p=0",
            video_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"[ThumbnailBurn] ffprobe hatası, orijinal video kullanılacak")
            return video_path
        
        parts = result.stdout.strip().split(",")
        width, height = int(parts[0]), int(parts[1])
        fps_raw = parts[2] if len(parts) > 2 else "30"
        try:
            if "/" in fps_raw:
                num, den = fps_raw.split("/")
                fps = round(int(num) / int(den))
            else:
                fps = int(float(fps_raw))
        except:
            fps = 30

        # Ses stream var mı
        audio_probe = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate",
            "-of", "csv=p=0",
            video_path
        ]
        audio_result = subprocess.run(audio_probe, capture_output=True, text=True, timeout=10)
        has_audio = bool(audio_result.stdout.strip())
        audio_parts = audio_result.stdout.strip().split(",") if has_audio else []
        sample_rate = audio_parts[1] if len(audio_parts) > 1 else "44100"

        is_portrait = height > width  # Shorts = 9:16 portrait

        print(f"[ThumbnailBurn] Video: {width}x{height}, {fps}fps, portrait={is_portrait}, ses={'var' if has_audio else 'yok'}")

        base_dir = os.path.dirname(video_path) or "."
        thumb_video = os.path.join(base_dir, "_thumb_intro.mp4")
        output_path = os.path.join(base_dir, "_with_thumb_" + os.path.basename(video_path))

        # ── 2. Video filtresi oluştur ────────────────────────────
        if is_portrait:
            # 16:9 thumbnail → 9:16 canvas:
            # Thumbnail'i genişliğe sığdır, ortala, üst/alt gradient
            # pad ile siyah/koyu arka plan, overlay ile thumbnail ortada
            vf_filter = (
                f"scale={width}:-2,"                                    # Genişliğe sığdır
                f"pad={width}:{height}:0:(oh-ih)/2:color=0x0A0A14,"   # Dikey ortala, koyu arka plan
                f"drawbox=x=0:y=0:w={width}:h=(ih-{width}*9/16)/2:color=0x0A0A14@1:t=fill,"  # Üst padding
                f"setsar=1"
            )
        else:
            # 16:9 video — thumbnail zaten uyumlu
            vf_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x0A0A14,"
                f"setsar=1"
            )

        # ── 3. Freeze-frame video oluştur ────────────────────────
        if has_audio:
            thumb_cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", thumbnail_path,
                "-f", "lavfi",
                "-i", f"anullsrc=r={sample_rate}:cl=stereo",
                "-t", str(duration),
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-r", str(fps),
                "-shortest",
                thumb_video
            ]
        else:
            thumb_cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", thumbnail_path,
                "-t", str(duration),
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                thumb_video
            ]

        r1 = subprocess.run(thumb_cmd, capture_output=True, text=True, timeout=30)
        if r1.returncode != 0:
            print(f"[ThumbnailBurn] Freeze-frame hatası: {r1.stderr[-300:]}")
            return video_path

        # ── 4. filter_complex concat ile birleştir ───────────────
        if has_audio:
            merge_cmd = [
                "ffmpeg", "-y",
                "-i", thumb_video,
                "-i", video_path,
                "-filter_complex",
                "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]",
                "-map", "[outv]",
                "-map", "[outa]",
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-r", str(fps),
                "-movflags", "+faststart",
                output_path
            ]
        else:
            merge_cmd = [
                "ffmpeg", "-y",
                "-i", thumb_video,
                "-i", video_path,
                "-filter_complex",
                "[0:v][1:v]concat=n=2:v=1:a=0[outv]",
                "-map", "[outv]",
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                "-movflags", "+faststart",
                output_path
            ]

        r2 = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=120)

        # Geçici dosyaları temizle
        try:
            if os.path.exists(thumb_video):
                os.remove(thumb_video)
        except:
            pass

        if r2.returncode != 0:
            print(f"[ThumbnailBurn] Birleştirme hatası: {r2.stderr[-300:]}")
            return video_path

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            shutil.move(output_path, video_path)
            print(f"[ThumbnailBurn] ✅ Thumbnail gömüldü ({width}x{height}, {duration}s, ses={'korundu' if has_audio else 'yok'})")
            return video_path
        else:
            print(f"[ThumbnailBurn] Çıktı geçersiz, orijinal video kullanılacak")
            return video_path

    except Exception as e:
        print(f"[ThumbnailBurn] Hata (orijinal video kullanılacak): {e}")
        return video_path
