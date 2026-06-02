import os
import json
import time
import random
import hashlib
import requests
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger("AIVideoGenerator")
OUTPUT_DIR = "assets/ai_clips"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Görsel Temalar ───────────────────────────────────────────
THEMES = {
    "electric": {"bg": "#001833", "acc": "#00D4FF"},
    "green":    {"bg": "#001A00", "acc": "#00FF88"},
    "purple":   {"bg": "#0D001A", "acc": "#CC44FF"},
    "orange":   {"bg": "#1A0800", "acc": "#FF6B00"},
    "gold":     {"bg": "#1A1400", "acc": "#FFD700"},
    "red":      {"bg": "#1A0000", "acc": "#FF3300"},
}

KEYWORD_MAP = {
    "electric": ["blue","electric","battery","energy","charge","ev","volt","lfp","lithium"],
    "green":    ["green","robot","factory","eco","sustainable","plant","clean"],
    "purple":   ["purple","ai","neural","data","tech","future","digital","analysis"],
    "orange":   ["orange","mining","desert","solar","warm","heat"],
    "gold":     ["gold","luxury","premium","speed","performance","race","fast"],
    "red":      ["red","power","engine","fire","fast","turbo","sport","danger"],
}

TITLE_MAP = {
    "speed":    ("SPEED VS",   "RANGE"),
    "range":    ("RANGE",      "ANALYSIS"),
    "battery":  ("BATTERY",    "CAPACITY"),
    "charge":   ("TURBO",      "CHARGE"),
    "electric": ("ELECTRIC",   "VEHICLE"),
    "lithium":  ("LITHIUM",    "ENERGY"),
    "default":  ("AI VIDEO",   "CONTENT"),
}

def _pick_theme(prompt: str) -> dict:
    pl = prompt.lower()
    for name, kws in KEYWORD_MAP.items():
        if any(k in pl for k in kws): return THEMES[name]
    return THEMES["electric"]

def _pick_titles(prompt: str) -> tuple[str, str]:
    pl = prompt.lower()
    for key, pair in TITLE_MAP.items():
        if key in pl: return pair
    words = [w.upper() for w in prompt.split()[:4]]
    t1 = " ".join(words[:2]) if len(words) >= 2 else (words[0] if words else "EVCARIX")
    t2 = " ".join(words[2:]) if len(words) > 2 else "AUTO-STUDIO"
    return t1, t2

def _build_vf(title1: str, title2: str, sub: str, bg: str, acc: str) -> str:
    """Garantili ve estetik FFmpeg video filtresi."""
    line_ys  = [280, 580, 880, 1180, 1480, 1760]
    line_ops = [0.25, 0.12, 0.20, 0.12, 0.20, 0.12]
    parts = [f"drawbox=x=0:y=0:w=iw:h=ih:color={bg}@1.0:t=fill"]
    for y, op in zip(line_ys, line_ops):
        parts.append(f"drawbox=x=0:y={y}:w=iw:h=3:color={acc}@{op:.2f}:t=fill")
    parts += [
        f"drawtext=text='{title1}':fontsize=120:fontcolor={acc}:x=(w-tw)/2:y=(h-th)/2-160:shadowcolor=black@0.9:shadowx=5:shadowy=5",
        f"drawtext=text='{title2}':fontsize=120:fontcolor={acc}:x=(w-tw)/2:y=(h-th)/2:shadowcolor=black@0.9:shadowx=5:shadowy=5",
        f"drawtext=text='{sub}':fontsize=48:fontcolor=white@0.75:x=(w-tw)/2:y=(h-th)/2+160",
        f"drawtext=text='EVCARIX':fontsize=36:fontcolor={acc}@0.50:x=(w-tw)/2:y=(h-th)/2+250"
    ]
    return ",".join(parts)

class AIVideoGenerator:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.muapi_key  = os.getenv("MUAPI_KEY")
        self.kling_key  = os.getenv("KLING_API_KEY")
        self.luma_key   = os.getenv("LUMA_API_KEY")
        self.hf_token   = os.getenv("HF_TOKEN")

    def generate_clips(self, prompts: list[str]) -> list[str]:
        clips = []
        for i, prompt in enumerate(prompts):
            path = None
            logger.info(f"[AIVideo] Sahne {i+1} üretiliyor...")
            
            # 1. AI Kaynakları (Sırayla)
            methods = [
                ("Veo", self._google_veo),
                ("Muapi", self._muapi),
                ("Kling", self._kling),
                ("Luma", self._luma),
                ("HF", self._huggingface)
            ]
            
            for name, method in methods:
                try:
                    path = method(prompt, i)
                    if path and self._validate(path):
                        logger.info(f"[AIVideo] ✅ {name} Başarılı!")
                        break
                except: pass
            
            # 2. AI Başarısız bildirimi (Artık fallback burada üretilmiyor, Pexels'e şans veriliyor)
            if not path:
                logger.warning(f"[AIVideo] ⚠️ Sahne {i+1} için AI başarısız, Pexels/Pixabay devreye girecek.")
            
            if path: clips.append(path)
        return clips

    def _google_veo(self, prompt, idx):
        if not self.gemini_key: return None
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=self.gemini_key)
            logger.info(f"[GoogleVeo] Veo 2.0 ile video üretimi başlatılıyor (Sahne {idx+1})")
            
            operation = client.models.generate_videos(
                model="veo-2.0-generate-001",
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio="9:16",
                    duration_seconds=5,
                    number_of_videos=1,
                )
            )

            # Üretim tamamlanana kadar bekle (max 3 dakika)
            for _ in range(36):
                if operation.done:
                    break
                time.sleep(5)
                operation = client.operations.get(operation)

            if operation.done and operation.response.generated_videos:
                video = operation.response.generated_videos[0]
                p = os.path.join(OUTPUT_DIR, f"veo_{idx}.mp4")
                # Videoyu indir
                client.files.download(file=video.video, download_path=p)
                return p if os.path.exists(p) else None

        except Exception as e:
            logger.debug(f"[GoogleVeo] Hata: {e}")
        return None

    def _muapi(self, prompt, idx):
        if not self.muapi_key: return None
        r = requests.post("https://api.muapi.ai/v1/video/generate", headers={"Authorization": f"Bearer {self.muapi_key}"}, 
                          json={"model": "kling-v1.6", "prompt": prompt, "aspect_ratio": "9:16"}, timeout=10)
        if r.status_code == 200:
            tid = r.json().get("task_id")
            for _ in range(20):
                tr = requests.get(f"https://api.muapi.ai/v1/video/status/{tid}", headers={"Authorization": f"Bearer {self.muapi_key}"})
                d = tr.json()
                if d.get("status") == "succeeded": return self._download(d["video_url"], f"mu_{idx}.mp4")
                time.sleep(10)
        return None


    def _ffmpeg_animated(self, prompt: str, idx: int) -> str | None:
        """
        Generate unique 3D cinematic animation using FFmpeg lavfi.
        Every call produces visually different output.
        Zero external dependencies. Unlimited and free.
        """
        out = os.path.join(OUTPUT_DIR, f"anim_{idx}_{random.randint(1000,9999)}.mp4")
        theme = _pick_theme(prompt)
        p = self._get_random_params()
        base_filter = self._pick_effect(prompt, p)
        color_filter = self._apply_theme_color(base_filter, theme)
        text_filter = self._add_text_overlay(color_filter, prompt, theme, p)
        cmd = self._build_ffmpeg_cmd(text_filter, out, duration=5)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 5000:
                logger.info(f"[FFmpeg3D] ✅ Clip {idx}: {out}")
                return out
            logger.error(f"[FFmpeg3D] Failed: {result.stderr[-300:]}")
        except Exception as e:
            logger.error(f"[FFmpeg3D] Error: {e}")
        return None

    def _get_random_params(self) -> dict:
        return {
            "freq1": round(random.uniform(20, 60), 1),
            "freq2": round(random.uniform(30, 80), 1),
            "freq3": round(random.uniform(15, 45), 1),
            "speed1": round(random.uniform(1.5, 5.0), 2),
            "speed2": round(random.uniform(2.0, 6.0), 2),
            "r_amp": random.randint(80, 127),
            "g_amp": random.randint(60, 127),
            "b_amp": random.randint(100, 127),
            "grid": random.choice([40, 60, 80, 100, 120]),
            "cx_offset": random.randint(-100, 100),
            "cy_offset": random.randint(-200, 200),
            "seed": random.randint(1, 9999),
            "variant": random.randint(0, 3)
        }

    def _pick_effect(self, prompt: str, p: dict) -> str:
        pl = prompt.lower()
        effects = {
            "plasma": f"geq=r='{p['r_amp']}+100*sin(2*PI*(X/W+T/{p['speed1']}))':g='{p['g_amp']}+80*cos(2*PI*(Y/H+T/{p['speed2']}))':b='{p['b_amp']}+55*sin(2*PI*(X/W+Y/H+T/2))'",
            "tunnel": f"geq=r='{p['r_amp']}+127*sin(hypot(X-W/2-{p['cx_offset']},Y-H/2-{p['cy_offset']})/{p['freq1']}-T*{p['speed1']})':g='{p['g_amp']}+127*sin(hypot(X-W/2,Y-H/2)/{p['freq2']}-T*{p['speed2']})':b='{p['b_amp']}'",
            "particles": f"geq=r='255*gt(sin(X/{p['grid']/10}+T*{p['speed1']}),0.95)':g='255*gt(sin(Y/8+T*{p['speed2']}),0.95)':b='{p['b_amp']}'",
            "matrix": f"geq=lum='255*gt(random(floor(X/{p['grid']/2})*floor(T*{p['speed1']})),0.97)':cb=128:cr=100",
            "wormhole": f"geq=r='128+127*sin(10*atan2(Y-H/2,X-W/2)+hypot(X-W/2,Y-H/2)/{p['freq1']}-T*{p['speed1']})':g='128+127*cos(8*atan2(Y-H/2,X-W/2)-T*{p['speed2']})':b='{p['b_amp']}+55*sin(T*2)'",
            "grid": f"geq=r='255*lt(mod(X,{p['grid']}),2)':g='200*lt(mod(Y,{p['grid']}),2)':b='255*lt(mod(X,{p['grid']}),2)+255*lt(mod(Y,{p['grid']}),2)'",
            "lava": f"geq=r='200+55*sin(X/{p['freq1']}+T*{p['speed1']})':g='80+40*cos(Y/{p['freq2']}+T*{p['speed2']})':b='30'",
            "stars": f"geq=lum='255*gt(random(floor(X/3)+floor(Y/3)*{p['seed']}),0.995)':cb=128:cr=128",
            "scan": f"geq=r='255*gt(sin(Y/5+T*{p['speed1']*2}),0.98)+100*sin(X/100+T)':g='200*gt(sin(Y/5+T*{p['speed1']*2}),0.98)':b='255*sin(X/50+T*2)'",
            "quantum": f"geq=r='128+127*sin(X/{p['freq1']})*cos(T*{p['speed1']})':g='128+127*cos(Y/{p['freq2']})*sin(T*{p['speed2']})':b='200+55*sin((X+Y)/{p['freq3']}+T)'"
        }
        
        if any(k in pl for k in ["electric", "battery", "charge", "energy"]):
            return random.choice([effects["tunnel"], effects["grid"]])
        if any(k in pl for k in ["ai", "neural", "data", "tech"]):
            return random.choice([effects["matrix"], effects["scan"]])
        if any(k in pl for k in ["robot", "factory", "mechanical"]):
            return random.choice([effects["grid"], effects["particles"]])
        if any(k in pl for k in ["mining", "lithium", "chemical"]):
            return random.choice([effects["plasma"], effects["lava"]])
        if any(k in pl for k in ["future", "space", "quantum"]):
            return random.choice([effects["wormhole"], effects["stars"]])
        if any(k in pl for k in ["speed", "fast", "performance"]):
            return random.choice([effects["quantum"], effects["tunnel"]])
            
        return random.choice(list(effects.values()))

    def _apply_theme_color(self, base_filter: str, theme: dict) -> str:
        acc = theme["acc"].lower()
        r, g, b = 1.0, 1.0, 1.0
        if "00d4ff" in acc or "blue" in acc: r, g, b = 0.5, 1.0, 1.5
        elif "00ff88" in acc or "green" in acc: r, g, b = 0.5, 1.5, 0.5
        elif "cc44ff" in acc or "purple" in acc: r, g, b = 1.2, 0.5, 1.5
        elif "ff6b00" in acc or "orange" in acc: r, g, b = 1.5, 0.8, 0.2
        elif "ffd700" in acc or "gold" in acc: r, g, b = 1.5, 1.2, 0.2
        elif "ff3300" in acc or "red" in acc: r, g, b = 1.5, 0.2, 0.2
        
        return f"{base_filter},colorchannelmixer=rr={r}:gg={g}:bb={b}"

    def _add_text_overlay(self, video_filter: str, prompt: str, theme: dict, params: dict) -> str:
        t1, t2 = _pick_titles(prompt)
        acc = theme["acc"]
        
        t1 = "".join(c for c in t1 if c.isalnum() or c in " -").strip()[:20]
        t2 = "".join(c for c in t2 if c.isalnum() or c in " -").strip()[:20]
        
        TEXT_STYLES = [
            f"drawtext=text='{t1}':fontsize=110:fontcolor=white:x=(w-tw)/2:y=800:shadowcolor={acc}@0.8:shadowx=6:shadowy=6:borderw=3:bordercolor={acc}",
            f"drawbox=x=0:y=780:w=25:h=220:color={acc}:t=fill,drawtext=text='{t1}':fontsize=100:fontcolor=white:x=80:y=820:shadowcolor=black@0.5:shadowx=3:shadowy=3",
            f"drawbox=x=0:y=1400:w=iw:h=300:color=black@0.7:t=fill,drawtext=text='{t1}':fontsize=90:fontcolor={acc}:x=(w-tw)/2:y=1450",
            f"drawtext=text='{t1}':fontsize=90:fontcolor={acc}:x=(w-tw)/2:y=720,drawtext=text='{t2}':fontsize=90:fontcolor=white:x=(w-tw)/2:y=850"
        ]
        
        style = random.choice(TEXT_STYLES)
        return f"{video_filter},{style}"

    def _build_ffmpeg_cmd(self, filter_chain: str, output: str, duration: int = 5) -> list:
        return [
            "ffmpeg", "-y", "-t", str(duration),
            "-f", "lavfi", "-i", f"nullsrc=s=1080x1920:r=30",
            "-filter_complex", f"[0:v]{filter_chain}[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-crf", "18", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-an", output
        ]

    def _validate(self, path: str) -> bool:
        if not path or not os.path.exists(path): return False
        if os.path.getsize(path) < 5000: return False
        return True

    def _download(self, url, name):
        p = os.path.join(OUTPUT_DIR, name)
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                with open(p, "wb") as f: f.write(r.content)
                return p
        except: pass
        return None

    def _kling(self, p, i): return None
    def _luma(self, p, i): return None
    def _huggingface(self, p, i): return None
