#!/usr/bin/env python3
"""
Avatar Co-Host — Enhanced Voice Engine
Natural voice with SSML prosody + lip-sync avatar generation.
"""

import asyncio
import json
import os
import subprocess
import sys
import hashlib
import math
from pathlib import Path

try:
    import edge_tts
except ImportError:
    print("ERROR: edge-tts not installed")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════
VOICE_MODEL_DIR = Path(__file__).parent / "voice-model"
AUDIO_OUTPUT_DIR = Path(__file__).parent / "audio"
VIDEO_OUTPUT_DIR = Path(__file__).parent / "video"
AVATAR_IMAGE = Path(__file__).parent / "avatar" / "nova_avatar.png"

VOICE_MODEL_DIR.mkdir(exist_ok=True)
AUDIO_OUTPUT_DIR.mkdir(exist_ok=True)
VIDEO_OUTPUT_DIR.mkdir(exist_ok=True)
(Path(__file__).parent / "avatar").mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════
# NATURAL VOICE ENGINE
# ══════════════════════════════════════════════════════════════

# Voice profiles — optimized for natural sound
VOICES = {
    "nova_female_it": {
        "voice": "it-IT-ElsaNeural",
        "rate": "-8%",
        "pitch": "+3Hz",
        "style": "cheerful",
    },
    "nova_male_it": {
        "voice": "it-IT-DiegoNeural", 
        "rate": "-5%",
        "pitch": "-2Hz",
        "style": "professional",
    },
    "nova_female_en": {
        "voice": "en-US-JennyNeural",
        "rate": "-10%",
        "pitch": "+2Hz",
        "style": "friendly",
    },
}

# Default voice
DEFAULT_VOICE = "nova_female_it"


async def generate_natural_speech(
    text: str,
    output_path: str,
    voice_key: str = None,
    use_ssml: bool = True,
    use_cache: bool = True,
) -> str:
    """
    Generate natural-sounding speech with SSML prosody.
    SSML adds pauses, emphasis, and intonation for less robotic sound.
    """
    voice_key = voice_key or DEFAULT_VOICE
    voice_config = VOICES[voice_key]
    
    text_hash = hashlib.md5(f"{text}_{voice_key}_{use_ssml}".encode()).hexdigest()[:12]
    output_path = str(output_path)
    
    if use_cache:
        cache_key = f"{text_hash}"
        cached = AUDIO_OUTPUT_DIR / f"{cache_key}.mp3"
        if cached.exists():
            # Copy to output location
            import shutil
            shutil.copy(str(cached), output_path)
            return output_path
    
    if use_ssml:
        ssml = _build_ssml(text, voice_config)
        # edge_tts auto-detects SSML when text starts with <speak>
        communicate = edge_tts.Communicate(
            ssml,
            voice_config["voice"],
            rate=voice_config["rate"],
            pitch=voice_config["pitch"],
        )
    else:
        communicate = edge_tts.Communicate(
            text,
            voice_config["voice"],
            rate=voice_config["rate"],
            pitch=voice_config["pitch"],
        )
    
    await communicate.save(output_path)
    
    # Cache
    import shutil
    shutil.copy(output_path, str(AUDIO_OUTPUT_DIR / f"{text_hash}.mp3"))
    
    return output_path


def _build_ssml(text: str, voice_config: dict) -> str:
    """
    Build SSML with natural prosody:
    - Pauses after punctuation
    - Emphasis on key words
    - Breathing marks
    - Natural pitch variations
    """
    ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/speech10/synthesis"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xml:lang="it-IT">
    <prosody rate="{voice_config['rate'].replace('%', '')}%" pitch="{voice_config['pitch']}">
"""
    # Add breaks after punctuation for natural pacing
    import re
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for i, sentence in enumerate(sentences):
        if not sentence.strip():
            continue
        
        # Add emphasis on capitalized words (likely important)
        sentence = re.sub(
            r'\b([A-Z]{2,})\b',
            r'<emphasis level="moderate">\1</emphasis>',
            sentence
        )
        
        # Add micro-breaks between clauses
        sentence = sentence.replace(
            ', ',
            '<break time="150ms"/>, '
        )
        
        ssml += f"        {sentence}"
        
        # Add pause between sentences
        if i < len(sentences) - 1:
            ssml += '<break time="300ms"/>'
        
        ssml += "\n"
    
    ssml += """    </prosody>
</speak>"""
    
    return ssml


def text_to_speech_natural(
    text: str,
    output_path: str = None,
    voice_key: str = None,
) -> str:
    """Synchronous wrapper for natural speech generation."""
    if output_path is None:
        output_path = str(AUDIO_OUTPUT_DIR / "natural_output.mp3")
    return asyncio.get_event_loop().run_until_complete(
        generate_natural_speech(text, output_path, voice_key)
    )


# ══════════════════════════════════════════════════════════════
# LIP-SYNC AVATAR GENERATOR
# ══════════════════════════════════════════════════════════════

class LipSyncAvatar:
    """
    Generates a video of the avatar with lip-sync.
    Uses audio amplitude to drive mouth animation.
    """
    
    def __init__(self, avatar_image_path: str = None):
        self.avatar_path = avatar_image_path or str(AVATAR_IMAGE)
        self.fps = 25
        self.mouth_open_max = 15  # pixels
    
    def _get_audio_amplitudes(self, audio_path: str, num_frames: int) -> list:
        """Extract audio amplitudes for lip-sync timing."""
        # Use ffmpeg to get raw audio samples
        cmd = [
            "ffmpeg", "-i", audio_path,
            "-ac", "1", "-ar", "8000", "-f", "s16le",
            "-y", "/tmp/audio_raw.pcm"
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        
        # Read raw PCM and compute amplitudes per frame
        samples_per_frame = 8000 // self.fps  # 320 samples at 8kHz, 25fps
        
        with open("/tmp/audio_raw.pcm", "rb") as f:
            raw_data = f.read()
        
        import struct
        amplitudes = []
        for i in range(num_frames):
            start = i * samples_per_frame * 2  # 16-bit = 2 bytes
            end = start + samples_per_frame * 2
            if end > len(raw_data):
                amplitudes.append(0)
                continue
            
            chunk = raw_data[start:end]
            samples = struct.unpack(f"<{samples_per_frame}h", chunk[:samples_per_frame*2])
            # RMS amplitude
            rms = math.sqrt(sum(s*s for s in samples) / len(samples)) if samples else 0
            amplitudes.append(min(rms / 2048, 1.0))  # Normalize to 0-1
        
        return amplitudes
    
    def _generate_mouth_frame(self, base_image: Image.Image, mouth_open: float) -> Image.Image:
        """Generate a single frame with mouth open at given amplitude."""
        img = base_image.copy()
        draw = ImageDraw.Draw(img)
        
        # Avatar dimensions (assume 512x512)
        w, h = img.size
        
        # Mouth position (center-bottom area of face)
        mouth_cx = w // 2
        mouth_cy = int(h * 0.72)
        mouth_width = int(w * 0.18)
        mouth_height = int(mouth_open * self.mouth_open_max)
        
        # Draw mouth (dark ellipse)
        x1 = mouth_cx - mouth_width // 2
        y1 = mouth_cy - max(mouth_height // 2, 1)
        x2 = mouth_cx + mouth_width // 2
        y2 = mouth_cy + max(mouth_height // 2, 1)
        
        # Mouth interior (dark)
        if mouth_height > 2:
            draw.ellipse([x1, y1, x2, y2], fill="#2a1a1a")
            # Teeth hint (light line at top)
            if mouth_height > 5:
                draw.arc([x1+3, y1, x2-3, y1+4], 0, 180, fill="#ffffff", width=1)
        
        return img
    
    def generate_avatar_video(
        self,
        audio_path: str,
        output_video: str = None,
        avatar_image: str = None,
    ) -> str:
        """
        Generate lip-sync video from audio + avatar image.
        Returns path to generated video.
        """
        if not HAS_PILLOW:
            print("ERROR: Pillow not installed. Run: pip install Pillow")
            return None
        
        output_video = output_video or str(VIDEO_OUTPUT_DIR / "avatar_speaking.mp4")
        avatar_image = avatar_image or self.avatar_path
        
        # Get audio duration
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True
        )
        duration = float(probe.stdout.strip())
        num_frames = int(duration * self.fps)
        
        # Get audio amplitudes for lip-sync
        amplitudes = self._get_audio_amplitudes(audio_path, num_frames)
        
        # Load or create avatar image
        if os.path.exists(avatar_image):
            base_img = Image.open(avatar_image).convert("RGBA")
            # Resize to 512x512
            base_img = base_img.resize((512, 512), Image.LANCZOS)
        else:
            # Create placeholder avatar
            base_img = self._create_placeholder_avatar()
        
        # Generate frames
        frames_dir = Path("/tmp/avatar_frames")
        frames_dir.mkdir(exist_ok=True)
        
        print(f"Generating {num_frames} frames at {self.fps}fps ({duration:.1f}s)...")
        
        for i, amp in enumerate(amplitudes):
            frame = self._generate_mouth_frame(base_img, amp)
            frame.save(str(frames_dir / f"frame_{i:05d}.png"))
        
        # Compile video with ffmpeg
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(self.fps),
            "-i", str(frames_dir / "frame_%05d.png"),
            "-i", audio_path,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_video
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        # Cleanup frames
        import shutil
        shutil.rmtree(frames_dir, ignore_errors=True)
        
        print(f"Video generated: {output_video}")
        return output_video
    
    def _create_placeholder_avatar(self) -> Image.Image:
        """Create a simple placeholder avatar if no image provided."""
        img = Image.new("RGBA", (512, 512), "#2d2d44")
        draw = ImageDraw.Draw(img)
        
        # Face circle
        draw.ellipse([106, 80, 406, 420], fill="#f5d0a9")
        
        # Eyes
        draw.ellipse([170, 180, 220, 220], fill="#3d5a80")
        draw.ellipse([290, 180, 340, 220], fill="#3d5a80")
        draw.ellipse([185, 195, 205, 215], fill="white")
        draw.ellipse([305, 195, 325, 215], fill="white")
        
        # Smile
        draw.arc([180, 280, 330, 360], 0, 180, fill="#2a1a1a", width=3)
        
        # Hair
        draw.arc([106, 80, 406, 300], 180, 0, fill="#4a3728", width=40)
        
        return img


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Enhanced Voice Engine")
        print("Usage:")
        print("  python voice_engine_natural.py speak <text>   — Natural speech")
        print("  python voice_engine_natural.py voice <text>   — List voices")
        print("  python voice_engine_natural.py avatar <text>  — Generate lip-sync video")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "voices":
        print("Available voices:")
        for key, cfg in VOICES.items():
            print(f"  {key:25s} {cfg['voice']:25s} rate={cfg['rate']} pitch={cfg['pitch']}")
    
    elif cmd == "speak":
        text = " ".join(sys.argv[2:])
        path = text_to_speech_natural(text)
        print(f"Generated: {path}")
    
    elif cmd == "avatar":
        text = " ".join(sys.argv[2:])
        # First generate audio
        audio_path = text_to_speech_natural(text)
        # Then generate video
        avatar = LipSyncAvatar()
        video_path = avatar.generate_avatar_video(audio_path)
        print(f"Video: {video_path}")
    
    else:
        print(f"Unknown command: {cmd}")
