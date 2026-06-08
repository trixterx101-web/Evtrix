"""
src/utils/thumbnail_burn.py
============================
Thumbnail görselini videonun ilk karesine gömer.
YouTube doğrulanmamış kanallarda custom thumbnail API'si çalışmaz.
Bu yöntemle YouTube'un otomatik kare seçicisi thumbnail'imizi seçer.

Düzeltmeler:
- 9:16 aspect ratio desteği (Shorts uyumlu)
- Sessiz ses track'ı eklenir (ses kaybını önler)
"""

import os
import subprocess
import shutil


def burn_thumbnail_into_video(video_path: str, thumbnail_path: str, duration: float = 0.5) -> str:
    """
    Thumbnail görselini videonun başına freeze-frame olarak ekler.
    
    - Video boyutuna (9:16 veya 16:9) otomatik uyum sağlar
    - Freeze-frame'e sessiz ses track'ı ekler (concat ses kaybını önler)
    
    Args:
        video_path: Orijinal video dosyası
        thumbnail_path: Thumbnail görseli (JPG/PNG)
        duration: Freeze frame süresi (saniye)
    
    Returns:
        Yeni video dosyasının yolu (başarısızlıkta orijinal video döner)
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
        # Frame rate: "30/1" formatında gelebilir
        fps_raw = parts[2] if len(parts) > 2 else "30"
        try:
            if "/" in fps_raw:
                num, den = fps_raw.split("/")
                fps = round(int(num) / int(den))
            else:
                fps = int(float(fps_raw))
        except:
            fps = 30

        # Ses stream var mı kontrol et
        audio_probe = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate",
            "-of", "csv=p=0",
            video_path
        ]
        audio_result = subprocess.run(audio_probe, capture_output=True, text=True, timeout=10)
        has_audio = bool(audio_result.stdout.strip())
        
        # Ses parametreleri
        audio_parts = audio_result.stdout.strip().split(",") if has_audio else []
        sample_rate = audio_parts[1] if len(audio_parts) > 1 else "44100"

        print(f"[ThumbnailBurn] Video: {width}x{height}, {fps}fps, ses={'var' if has_audio else 'yok'}")

        base_dir = os.path.dirname(video_path) or "."
        thumb_video = os.path.join(base_dir, "_thumb_intro.mp4")
        output_path = os.path.join(base_dir, "_with_thumb_" + os.path.basename(video_path))
        concat_file = os.path.join(base_dir, "_concat_list.txt")

        # ── 2. Thumbnail'den freeze-frame video oluştur ──────────
        # Thumbnail'i videonun GERÇEK boyutuna (ör. 1080x1920 Shorts) resize + crop
        # center crop ile aspect ratio'yu koruyarak sığdır
        vf_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"setsar=1"
        )

        if has_audio:
            # Sessiz ses track'ı ekle (orijinal videonun ses parametrelerine uyumlu)
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
            # Ses yok, sadece video
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

        r1 = subprocess.run(thumb_cmd, capture_output=True, timeout=30)
        if r1.returncode != 0:
            print(f"[ThumbnailBurn] Freeze-frame oluşturulamadı: {r1.stderr[-200:]}")
            return video_path

        # ── 3. Re-encode ile birleştir (codec uyumsuzluğunu önler) ──
        # concat demuxer yerine filter_complex ile güvenli birleştirme
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

        r2 = subprocess.run(merge_cmd, capture_output=True, timeout=120)

        # Geçici dosyaları temizle
        for tmp in [thumb_video, concat_file]:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except:
                pass

        if r2.returncode != 0:
            print(f"[ThumbnailBurn] Birleştirme hatası: {r2.stderr[-300:]}")
            return video_path

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            # Orijinalin yerine koy
            shutil.move(output_path, video_path)
            print(f"[ThumbnailBurn] ✅ Thumbnail gömüldü ({width}x{height}, {duration}s, ses={'korundu' if has_audio else 'yok'})")
            return video_path
        else:
            print(f"[ThumbnailBurn] Çıktı dosyası geçersiz, orijinal video kullanılacak")
            return video_path

    except Exception as e:
        print(f"[ThumbnailBurn] Hata (orijinal video kullanılacak): {e}")
        # Temizlik
        for tmp in [thumb_video, output_path, concat_file]:
            try:
                if 'tmp' in dir() and os.path.exists(tmp):
                    os.remove(tmp)
            except:
                pass
        return video_path
