import os
import re
import subprocess
import logging

logger = logging.getLogger("Editor")

class AutoEditor:
    """
    Assembles multiple clips.
    Short (9:16): NO subtitle burn-in on video — subtitles shown in bottom panel.
    Long (16:9):  subtitle burn-in at bottom of full-screen video.
    """

    def assemble(self, clips_paths, audio_path, output_path,
                 is_short=True, title=None, topic=None, words_with_times=None):
        try:
            logger.info(f"[Editor] Assembling {len(clips_paths)} clips, short={is_short}")

            duration = self._get_audio_duration(audio_path)
            logger.info(f"[Editor] Audio duration: {duration:.1f}s")

            clip_dur = 6.0
            # Prevent clip duplication by dynamically extending clip_dur if we don't have enough clips
            if len(clips_paths) > 0 and (duration / clip_dur) > len(clips_paths):
                clip_dur = (duration / len(clips_paths)) + 0.1
                
            needed = max(1, int(duration / clip_dur) + 1)
            if len(clips_paths) < needed:
                clips_paths = (clips_paths * (needed // len(clips_paths) + 1))[:needed]

            W, H = (1080, 1440) if is_short else (1920, 1080)

            inputs      = []
            scale_parts = []
            for i, clip in enumerate(clips_paths):
                # Loop input infinitely so it can cover the dynamic clip_dur safely
                inputs += ["-stream_loop", "-1", "-i", os.path.abspath(clip)]
                scale_parts.append(
                    f"[{i}:v]trim=duration={clip_dur},setpts=PTS-STARTPTS,"
                    f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                    f"crop={W}:{H},setsar=1,fps=24[v{i}]"
                )

            concat_inputs = "".join(f"[v{i}]" for i in range(len(clips_paths)))

            # Long video: burn subtitles on video. Short: no subtitles (panel handles it)
            if not is_short and title:
                subtitle_filters = self._build_subtitles(title, duration, W, H)
                subtitle_chain   = ",".join(subtitle_filters) if subtitle_filters else ""
            else:
                subtitle_chain = ""

            if subtitle_chain:
                fg = (
                    ";".join(scale_parts) + ";" +
                    concat_inputs + f"concat=n={len(clips_paths)}:v=1:a=0[concat];" +
                    f"[concat]{subtitle_chain}[vout]"
                )
            else:
                fg = (
                    ";".join(scale_parts) + ";" +
                    concat_inputs + f"concat=n={len(clips_paths)}:v=1:a=0[vout]"
                )

            temp_video = f"/tmp/temp_merged_{os.getpid()}.mp4"

            cmd_v = ["ffmpeg", "-y"] + inputs + [
                "-filter_complex", fg,
                "-map", "[vout]",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-threads", "2", "-an",
                temp_video
            ]
            r = subprocess.run(cmd_v, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                logger.error(f"[Editor] Pass 1 failed: {r.stderr[-400:]}")
                return False

            cmd_a = [
                "ffmpeg", "-y",
                "-i", temp_video,
                "-i", os.path.abspath(audio_path),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(round(duration, 3)),
                "-shortest", output_path
            ]
            r2 = subprocess.run(cmd_a, capture_output=True, text=True, timeout=120)
            if r2.returncode != 0:
                logger.error(f"[Editor] Pass 2 failed: {r2.stderr[-400:]}")
                return False

            if os.path.exists(temp_video):
                os.remove(temp_video)

            logger.info(f"[Editor] ✅ Done: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"[Editor] Error: {e}")
            return False

    def _build_subtitles(self, text: str, duration: float, W: int, H: int) -> list:
        """Sentence-level subtitle burn-in for long video only."""
        # Strip ALL special chars that break FFmpeg drawtext
        clean = re.sub(r"[^A-Z0-9 ]", " ", text.upper()).strip()
        clean = re.sub(r" +", " ", clean)

        words  = clean.split()
        chunks = []
        chunk  = []
        for w in words:
            chunk.append(w)
            if len(chunk) >= 6:
                chunks.append(" ".join(chunk))
                chunk = []
        if chunk:
            chunks.append(" ".join(chunk))

        if not chunks:
            return []

        font_size = 52
        y_pos     = H - 110
        chunk_dur = duration / len(chunks)

        filters = []
        for i, chunk_text in enumerate(chunks):
            t0   = round(i * chunk_dur, 3)
            t1   = round((i + 1) * chunk_dur - 0.08, 3)
            # Only alphanumeric + space — fully safe for FFmpeg
            safe = chunk_text[:40]  # max length guard
            filters.append(
                f"drawtext=text='{safe}'"
                f":fontsize={font_size}:fontcolor=white"
                f":x=(w-tw)/2:y={y_pos}"
                f":shadowcolor=black@0.95:shadowx=3:shadowy=3"
                f":enable='between(t\\,{t0}\\,{t1})'"
            )
        return filters

    def _get_audio_duration(self, path: str) -> float:
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", path]
            r = subprocess.run(cmd, capture_output=True, text=True)
            return float(r.stdout.strip())
        except:
            return 45.0
