import os
import math
import asyncio
import logging
import subprocess
from typing import Optional

print("=== NEW VOICE ENGINE LOADED (v11.0 - Real Timings) ===", flush=True)
logger = logging.getLogger("VoiceEngine")


def _sentence_to_chunks(sentence_text: str, start_t: float, end_t: float, target_words: int = 5) -> list:
    """
    Split a single sentence into sub-chunks while preserving real timing proportionally.
    Each chunk's start/end is derived from word-count fraction within the sentence.
    """
    words = sentence_text.strip().split()
    if not words:
        return []

    total_words = len(words)
    total_dur   = end_t - start_t

    # If sentence is short enough, keep as one chunk
    if total_words <= target_words + 1:
        return [{
            "text":     sentence_text.strip(),
            "start":    round(start_t, 3),
            "end":      round(end_t,   3),
            "duration": round(total_dur, 3),
        }]

    # Split into balanced sub-chunks
    num_chunks = math.ceil(total_words / target_words)
    chunk_size  = math.ceil(total_words / num_chunks)
    raw_chunks  = [words[i: i + chunk_size] for i in range(0, total_words, chunk_size)]

    result    = []
    cur_start = start_t
    for ch in raw_chunks:
        ch_text = " ".join(ch)
        frac    = len(ch) / total_words
        ch_dur  = total_dur * frac
        ch_end  = cur_start + ch_dur
        result.append({
            "text":     ch_text,
            "start":    round(cur_start, 3),
            "end":      round(ch_end,   3),
            "duration": round(ch_dur,   3),
        })
        cur_start = ch_end
    return result


class VoiceEngine:
    def __init__(self):
        self.use_kokoro = False  # Set to True if Kokoro model is cached

    # ── Public API ────────────────────────────────────────────────────────────

    async def generate_voice(self, text: str, output_path: str, voice_type: str = "female"):
        """v11.0 — Uses stream() to capture real SentenceBoundary timings."""
        if self.use_kokoro:
            return await self._generate_kokoro(text, output_path, voice_type)
        return await self._generate_edge(text, output_path, voice_type)

    # ── Private: Edge TTS ──────────────────────────────────────────────────────

    async def _generate_edge(self, text: str, output_path: str, voice_type: str = "female"):
        import edge_tts

        text = (text or "").strip()
        if not text:
            logger.error("[VoiceEngine] TTS text is empty — cannot generate audio")
            return None

        voice = "en-US-BrianNeural" if voice_type == "male" else "en-US-JennyNeural"

        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True,
        )

        communicate      = edge_tts.Communicate(text, voice)
        sentence_timings = []   # raw SentenceBoundary events
        audio_bytes      = bytearray()

        stream_success = False
        # Calculate dynamic timeout: min 120s, up to 300s for long texts
        stream_timeout = max(120, min(300, len(text) // 10))

        try:
            async def _stream_with_timeout():
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes.extend(chunk["data"])
                    elif chunk["type"] == "SentenceBoundary":
                        sentence_timings.append({
                            "text":  chunk["text"],
                            "start": chunk["offset"]   / 10_000_000,
                            "end":   (chunk["offset"] + chunk["duration"]) / 10_000_000,
                        })

            await asyncio.wait_for(_stream_with_timeout(), timeout=stream_timeout)
            if len(audio_bytes) >= 512:
                stream_success = True
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)

        except asyncio.TimeoutError:
            logger.warning(f"[VoiceEngine] TTS stream timed out after {stream_timeout}s — attempting fallback save()")
        except Exception as e:
            logger.warning(f"[VoiceEngine] TTS stream error: {e} — attempting fallback save()")

        # Fallback 1: communicate.save() if stream failed or timed out
        if not stream_success:
            try:
                logger.info("[VoiceEngine] Running fallback communicate.save()...")
                await communicate.save(output_path)
                if os.path.exists(output_path) and os.path.getsize(output_path) >= 1024:
                    logger.info("[VoiceEngine] ✅ Fallback communicate.save() succeeded!")
                    stream_success = True
            except Exception as e:
                logger.error(f"[VoiceEngine] Fallback communicate.save() failed: {e}")

        # Fallback 2: Paragraph chunking if direct save failed
        if not stream_success:
            try:
                logger.info("[VoiceEngine] Running paragraph-chunked TTS generation...")
                stream_success = await self._generate_edge_chunked(text, voice, output_path)
            except Exception as e:
                logger.error(f"[VoiceEngine] Paragraph-chunked TTS failed: {e}")

        if not stream_success or not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            logger.error(f"[VoiceEngine] Output file invalid or TTS completely failed: {output_path}")
            return None

        # Get exact duration via ffprobe
        duration = await self._get_duration(output_path)
        if duration <= 0:
            file_size = os.path.getsize(output_path)
            duration = file_size / (16_000 * 2)   # rough fallback

        # ── Build precise subtitle chunks from SentenceBoundary events ──────
        if sentence_timings:
            logger.info(f"[VoiceEngine] ✅ Got {len(sentence_timings)} real sentence boundaries")
            subtitle_chunks = []
            for s in sentence_timings:
                subtitle_chunks.extend(
                    _sentence_to_chunks(s["text"], s["start"], s["end"], target_words=5)
                )
        else:
            # Fallback: if no boundaries received (network glitch, fallback save used, etc.)
            logger.warning("[VoiceEngine] No SentenceBoundary events — using fallback timings")
            subtitle_chunks = self._generate_fallback_chunks(text, duration)

        logger.info(f"[VoiceEngine] Total subtitle chunks: {len(subtitle_chunks)}")

        return {
            "audio_path":      output_path,
            "word_timings":    subtitle_chunks,   # kept for back-compat
            "subtitle_chunks": subtitle_chunks,   # explicit key for bottom_panel / editor
            "duration":        duration,
        }

    async def _generate_edge_chunked(self, text: str, voice: str, output_path: str) -> bool:
        """Splits long text into paragraph chunks and concatenates audio via ffmpeg."""
        import tempfile
        import shutil
        import edge_tts

        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text]

        temp_files = []
        try:
            for idx, p in enumerate(paragraphs):
                tmp_p = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{idx}.mp3")
                tmp_p.close()
                c = edge_tts.Communicate(p, voice)
                await c.save(tmp_p.name)
                if os.path.exists(tmp_p.name) and os.path.getsize(tmp_p.name) > 256:
                    temp_files.append(tmp_p.name)

            if not temp_files:
                return False

            if len(temp_files) == 1:
                shutil.move(temp_files[0], output_path)
                return True

            concat_list = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt")
            for tf in temp_files:
                tf_path = tf.replace('\\', '/')
                concat_list.write(f"file '{tf_path}'\n")
            concat_list.close()

            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list.name, "-c", "copy", output_path
            ]
            res = subprocess.run(cmd, capture_output=True)
            if os.path.exists(concat_list.name):
                os.unlink(concat_list.name)
            return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024
        finally:
            for tf in temp_files:
                if os.path.exists(tf):
                    try:
                        os.unlink(tf)
                    except Exception:
                        pass

    # ── Private: Kokoro (skeleton) ─────────────────────────────────────────────

    async def _generate_kokoro(self, text: str, output_path: str, voice_type: str):
        logger.info("[VoiceEngine] Attempting Kokoro-TTS...")
        return await self._generate_edge(text, output_path, voice_type)

    # ── Private: Helpers ───────────────────────────────────────────────────────

    async def _get_duration(self, path: str) -> float:
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            return float(res.stdout.strip())
        except Exception:
            return 0.0

    def _generate_fallback_chunks(self, text: str, duration: float, words_per_chunk: int = 5) -> list:
        """Equal-time fallback when real boundaries are unavailable."""
        import re
        clean  = re.sub(r"[^a-zA-Z0-9 .,!?%\\-]", " ", text).strip()
        words  = clean.upper().split()
        if not words:
            return []

        chunks = []
        for i in range(0, len(words), words_per_chunk):
            chunks.append(" ".join(words[i: i + words_per_chunk]))

        chunk_dur = duration / len(chunks)
        result    = []
        for idx, chunk_text in enumerate(chunks):
            start = idx * chunk_dur
            result.append({
                "text":     chunk_text,
                "start":    round(start, 3),
                "end":      round(start + chunk_dur, 3),
                "duration": round(chunk_dur, 3),
            })
        return result
