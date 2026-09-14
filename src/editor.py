import os
import re
import subprocess
import logging
import tempfile

logger = logging.getLogger("Editor")

class AutoEditor:
    """
    Assembles multiple clips.
    Short (9:16): Full 1080x1920 phone screen — karaoke-style subtitles burned-in.
    Long (16:9):  1920x1080 full-screen video with subtitle burn-in at bottom.
    """

    def assemble(self, clips_paths, audio_path, output_path,
                 is_short=True, title=None, topic=None, words_with_times=None,
                 subtitle_chunks=None):   # <- Real timing chunks from VoiceEngine
        temp_filter_file = None
        temp_video = None
        try:
            # Filter non-existent clip files
            clips_paths = [c for c in clips_paths if c and os.path.exists(c)]
            if not clips_paths:
                logger.error("[Editor] No valid clip files provided for assembly.")
                return False

            logger.info(f"[Editor] Assembling {len(clips_paths)} clips, short={is_short}")

            duration = self._get_audio_duration(audio_path)
            logger.info(f"[Editor] Audio duration: {duration:.1f}s")

            import random

            clip_dur = 6.0
            # Adjust clip duration so that the whole pool fits evenly without repetition if possible
            if len(clips_paths) > 0 and (duration / clip_dur) > len(clips_paths):
                # Try to extend each clip's duration so we need fewer repeats
                ideal_dur = duration / len(clips_paths)
                # Cap at 20s per clip for variety, floor at 5s
                clip_dur = max(5.0, min(20.0, ideal_dur))

            needed = max(1, int(duration / clip_dur) + 1)
            if len(clips_paths) < needed:
                # Smart cycling: shuffle copies so the same clip never appears back-to-back
                pool = list(clips_paths)
                random.shuffle(pool)
                extended = []
                prev = None
                pool_copy = list(pool)
                while len(extended) < needed:
                    random.shuffle(pool_copy)
                    for c in pool_copy:
                        if len(extended) >= needed:
                            break
                        if c != prev:
                            extended.append(c)
                            prev = c
                        else:
                            # Try to insert a different clip
                            for alt in pool_copy:
                                if alt != prev and len(extended) < needed:
                                    extended.append(alt)
                                    prev = alt
                                    break
                            else:
                                # No alternative, accept the duplicate
                                extended.append(c)
                                prev = c
                clips_paths = extended[:needed]
            else:
                random.shuffle(clips_paths)

            W, H = (1080, 1920) if is_short else (1920, 1080)

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

            # Both short and long: burn subtitles on video.
            # Short: karaoke-style large text in lower third.
            # Long:  standard subtitle text near bottom.
            if title:
                subtitle_filters = self._build_subtitles(
                    title, duration, W, H,
                    subtitle_chunks=subtitle_chunks,
                    is_short=is_short
                )
                subtitle_chain = ",".join(subtitle_filters) if subtitle_filters else ""
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

            # Write filter complex script to file to avoid Windows command-line character limits
            temp_filter_file = os.path.join(tempfile.gettempdir(), f"filter_complex_{os.getpid()}.txt")
            with open(temp_filter_file, "w", encoding="utf-8") as ff:
                ff.write(fg)

            temp_video = os.path.join(tempfile.gettempdir(), f"temp_merged_{os.getpid()}.mp4")

            cmd_v = ["ffmpeg", "-y"] + inputs + [
                "-filter_complex_script", temp_filter_file,
                "-map", "[vout]",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-threads", "2", "-an",
                temp_video
            ]
            r = subprocess.run(cmd_v, capture_output=True, text=True, timeout=1200)
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
            r2 = subprocess.run(cmd_a, capture_output=True, text=True, timeout=900)
            if r2.returncode != 0:
                logger.error(f"[Editor] Pass 2 failed: {r2.stderr[-400:]}")
                return False

            logger.info(f"[Editor] Done: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"[Editor] Error: {e}")
            return False
        finally:
            if temp_filter_file and os.path.exists(temp_filter_file):
                try: os.remove(temp_filter_file)
                except: pass
            if temp_video and os.path.exists(temp_video):
                try: os.remove(temp_video)
                except: pass

    # ------------------------------------------------------------------
    # Subtitle helpers
    # ------------------------------------------------------------------

    def _wrap_words(self, txt: str, max_chars: int) -> list:
        """Word-wrap txt into lines of at most max_chars characters (max 2 rows)."""
        words  = txt.split()
        rows   = []
        row    = []
        length = 0
        for w in words:
            need = (1 if row else 0) + len(w)
            if length + need > max_chars and row:
                rows.append(" ".join(row))
                row    = [w]
                length = len(w)
            else:
                row.append(w)
                length += need
        if row:
            rows.append(" ".join(row))
        return rows[:2]   # cap at 2 rows

    def _safe_text(self, s: str) -> str:
        """Strip chars that break FFmpeg drawtext argument parsing."""
        return s.replace("'", "").replace(":", " ").replace("\\", "")

    def _drawtext_filters(self, rows: list, t0: float, t1: float,
                          font_size: int, y_base: int, line_height: int,
                          box_flag: str) -> list:
        """Produce one drawtext filter per row, stacked vertically."""
        result = []
        for ri, row_text in enumerate(rows):
            st = self._safe_text(row_text)
            if not st:
                continue
            y = y_base + ri * line_height
            result.append(
                f"drawtext=text='{st}'"
                f":fontsize={font_size}:fontcolor=white"
                f":x=(w-tw)/2:y={y}"
                f":shadowcolor=black@0.95:shadowx=3:shadowy=3"
                f"{box_flag}"
                f":enable='between(t\\,{t0}\\,{t1})'"
            )
        return result

    def _build_subtitles(self, text: str, duration: float, W: int, H: int,
                         subtitle_chunks: list = None,
                         is_short: bool = False) -> list:
        """
        Build FFmpeg drawtext subtitle filters with automatic word-wrap.
        Long lines are split into at most 2 rows so text never overflows the screen.
        """
        if is_short:
            # Karaoke style: 64px font, ~18 chars/row safe on 1080px wide screen
            font_size   = 64
            max_chars   = 18
            line_height = 78
            y_base      = int(H * 0.78)
            box_flag    = ":box=1:boxcolor=black@0.60:boxborderw=16"
        else:
            font_size   = 52
            max_chars   = 28
            line_height = 62
            y_base      = H - 140
            box_flag    = ":box=1:boxcolor=black@0.40:boxborderw=10"

        # ── Real timing path ─────────────────────────────────────────────────
        if subtitle_chunks:
            filters = []
            for ch in subtitle_chunks:
                raw   = ch.get("text", "")
                clean = re.sub(r"[^A-Z0-9 ]", " ", raw.upper()).strip()
                clean = re.sub(r" +", " ", clean)
                if not clean:
                    continue
                t0 = round(ch.get("start", 0), 3)
                t1 = round(ch.get("end",   0) - 0.04, 3)
                if t1 <= t0:
                    t1 = round(t0 + 0.1, 3)
                rows = self._wrap_words(clean, max_chars)
                filters.extend(
                    self._drawtext_filters(rows, t0, t1,
                                           font_size, y_base, line_height, box_flag)
                )
            logger.info(f"[Editor] Built {len(filters)} subtitle drawtext filters (short={is_short})")
            return filters

        # ── Fallback: equal-duration split (4 words per chunk) ───────────────
        clean  = re.sub(r"[^A-Z0-9 ]", " ", text.upper()).strip()
        clean  = re.sub(r" +", " ", clean)
        words  = clean.split()

        raw_chunks = []
        chunk = []
        for w in words:
            chunk.append(w)
            if len(chunk) >= 4:
                raw_chunks.append(" ".join(chunk))
                chunk = []
        if chunk:
            raw_chunks.append(" ".join(chunk))

        if not raw_chunks:
            return []

        chunk_dur = duration / len(raw_chunks)
        filters   = []
        for i, chunk_text in enumerate(raw_chunks):
            t0   = round(i * chunk_dur, 3)
            t1   = round((i + 1) * chunk_dur - 0.08, 3)
            rows = self._wrap_words(chunk_text, max_chars)
            filters.extend(
                self._drawtext_filters(rows, t0, t1,
                                       font_size, y_base, line_height, box_flag)
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
