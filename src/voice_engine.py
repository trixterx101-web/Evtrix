import os
import asyncio
import logging
import re
import json
import random
from pathlib import Path
from typing import Optional

print("=== NEW VOICE ENGINE LOADED ===", flush=True)
logger = logging.getLogger("VoiceEngine")

class VoiceEngine:
    def __init__(self):
        self.use_kokoro = False # Set to true if model is cached

    async def generate_voice(self, text: str, output_path: str, voice_type: str = "female"):
        """v10.0: High-Quality Free TTS (Edge/Kokoro)"""
        if self.use_kokoro:
            return await self._generate_kokoro(text, output_path, voice_type)
        return await self._generate_edge(text, output_path, voice_type)

    async def _generate_edge(self, text: str, output_path: str, voice_type: str = "female"):
        import edge_tts
        
        voice = "en-US-BrianNeural" if voice_type == "male" else "en-US-JennyNeural"
        communicate = edge_tts.Communicate(text, voice)
        
        word_timings = []
        try:
            # Ses dosyasını kaydet ve word boundaries topla
            with open(output_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] in ["WordBoundary", "word", "boundary"]:
                        word_timings.append({
                            "text": chunk["text"],
                            "start": chunk["offset"] / 10**7,
                            "duration": chunk["duration"] / 10**7
                        })
        except Exception as e:
            logger.error(f"TTS Error: {e}")

        # Süreyi hesapla
        duration = await self._get_duration(output_path)
        
        # GUARANTEED FALLBACK
        if not word_timings or len(word_timings) == 0:
            logger.warning("[VoiceEngine] FORCE fallback timing.")
            word_timings = self._generate_fallback_timings(text, duration)

        logger.info(f"[VoiceEngine] FINAL TIMINGS = {len(word_timings)}")
        
        return {
            "audio_path": output_path,
            "word_timings": word_timings,
            "duration": duration
        }

    async def _get_duration(self, path):
        try:
            import subprocess
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
            res = subprocess.run(cmd, capture_output=True, text=True)
            return float(res.stdout.strip())
        except: return 0.0

    async def _generate_kokoro(self, text, output_path, voice_type):
        # Skeleton for Kokoro-TTS (Local high-quality)
        # Needs kokoro-onnx and model files
        logger.info("[VoiceEngine] Attempting Kokoro-TTS...")
        # Fallback to edge for now if model missing
        return await self._generate_edge(text, output_path, voice_type)

    def _generate_fallback_timings(self, text, duration):
        words = text.split()
        if not words: return []
        per_word = duration / len(words)
        timings = []
        for i, w in enumerate(words):
            timings.append({
                "text": w,
                "start": i * per_word,
                "duration": per_word
            })
        return timings
