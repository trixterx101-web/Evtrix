"""
src/utils/thumbnail_burn.py
============================
Thumbnail görselini videonun ilk karesine gömer.
YouTube doğrulanmamış kanallarda custom thumbnail API'si çalışmaz.
Bu yöntemle YouTube'un otomatik kare seçicisi thumbnail'imizi seçer.
"""

import os
import subprocess
import shutil


def burn_thumbnail_into_video(video_path: str, thumbnail_path: str, duration: float = 0.5) -> str:
    """
    Thumbnail görselini videonun başına freeze-frame olarak ekler.
    
    Args:
        video_path: Orijinal video dosyası
        thumbnail_path: Thumbnail görseli (JPG/PNG)
        duration: Freeze frame süresi (saniye) — 0.5s yeterli
    
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
        # Videonun boyut bilgisini al
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            video_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"[ThumbnailBurn] ffprobe hatası, orijinal video kullanılacak")
            return video_path
        
        dims = result.stdout.strip().split(",")
        width, height = int(dims[0]), int(dims[1])

        # 1. Thumbnail'den freeze-frame video oluştur
        base_dir = os.path.dirname(video_path)
        thumb_video = os.path.join(base_dir, "_thumb_intro.mp4")
        output_path = os.path.join(base_dir, "_with_thumb_" + os.path.basename(video_path))
        
        # Thumbnail'i video boyutuna resize et + freeze frame yap
        thumb_cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", thumbnail_path,
            "-t", str(duration),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            thumb_video
        ]
        r1 = subprocess.run(thumb_cmd, capture_output=True, timeout=30)
        if r1.returncode != 0:
            print(f"[ThumbnailBurn] Freeze-frame oluşturulamadı")
            return video_path

        # 2. Concat file oluştur
        concat_file = os.path.join(base_dir, "_concat_list.txt")
        with open(concat_file, "w") as f:
            f.write(f"file '{os.path.abspath(thumb_video)}'\n")
            f.write(f"file '{os.path.abspath(video_path)}'\n")

        # 3. Birleştir
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path
        ]
        r2 = subprocess.run(concat_cmd, capture_output=True, timeout=60)
        
        # Geçici dosyaları temizle
        for tmp in [thumb_video, concat_file]:
            try:
                os.remove(tmp)
            except:
                pass

        if r2.returncode != 0:
            # concat copy başarısız olursa re-encode dene
            concat_cmd_re = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file if os.path.exists(concat_file) else "",
                "-c:v", "libx264",
                "-c:a", "aac",
                output_path
            ]
            # Concat file'ı tekrar oluştur
            with open(concat_file, "w") as f:
                f.write(f"file '{os.path.abspath(thumb_video)}'\n")
                f.write(f"file '{os.path.abspath(video_path)}'\n")
            
            # Thumb video'yu tekrar oluştur
            subprocess.run(thumb_cmd, capture_output=True, timeout=30)
            r3 = subprocess.run(concat_cmd_re, capture_output=True, timeout=120)
            
            # Temizle
            for tmp in [thumb_video, concat_file]:
                try:
                    os.remove(tmp)
                except:
                    pass
            
            if r3.returncode != 0:
                print(f"[ThumbnailBurn] Re-encode de başarısız, orijinal video kullanılacak")
                return video_path

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            # Orijinali yedekle, yeni dosyayı yerine koy
            shutil.move(output_path, video_path)
            print(f"[ThumbnailBurn] ✅ Thumbnail videonun ilk karesine gömüldü ({duration}s)")
            return video_path
        else:
            print(f"[ThumbnailBurn] Çıktı dosyası geçersiz, orijinal video kullanılacak")
            return video_path

    except Exception as e:
        print(f"[ThumbnailBurn] Hata (orijinal video kullanılacak): {e}")
        return video_path
