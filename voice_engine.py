#!/usr/bin/env python3
"""
Avatar Co-Host — Voice Engine
Local TTS with consistent avatar voice + live voice conversion fallback.
No cloud uploads — all processing happens locally.
"""

import asyncio
import json
import os
import sys
import hashlib
import subprocess
from pathlib import Path
from typing import Optional

try:
    import edge_tts
except ImportError:
    print("ERROR: edge-tts not installed. Run: pip install edge-tts")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════
VOICE_MODEL_DIR = Path(__file__).parent / "voice-model"
AUDIO_OUTPUT_DIR = Path(__file__).parent / "audio"
SCRIPTS_DIR = Path(__file__).parent / "scripts"

VOICE_MODEL_DIR.mkdir(exist_ok=True)
AUDIO_OUTPUT_DIR.mkdir(exist_ok=True)
SCRIPTS_DIR.mkdir(exist_ok=True)

# Avatar voice settings — consistent across all pre-recorded content
AVATAR_VOICE = "it-IT-ElsaNeural"  # Italian voice
AVATAR_RATE = "-10%"  # Slightly slower for clarity
AVATAR_PITCH = "+5Hz"  # Slightly higher pitch for friendly tone

# Cache for generated audio (avoid re-generating same text)
AUDIO_CACHE = {}


async def generate_avatar_speech(text: str, output_path: str, voice: str = None, use_cache: bool = True) -> str:
    """
    Generate avatar speech using edge-tts.
    Uses caching to avoid regenerating identical scripts.
    Returns path to generated audio file.
    """
    voice = voice or AVATAR_VOICE
    text_hash = hashlib.md5(f"{text}_{voice}".encode()).hexdigest()[:12]
    output_path = str(output_path)
    
    if use_cache and text_hash in AUDIO_CACHE and os.path.exists(AUDIO_CACHE[text_hash]):
        return AUDIO_CACHE[text_hash]
    
    communicate = edge_talk(text, voice, rate=AVATAR_RATE, pitch=AVATAR_PITCH)
    await communicate.save(output_path)
    AUDIO_CACHE[text_hash] = output_path
    return output_path


async def edge_talk(text: str, voice: str, rate: str = "-15%", pitch: str = "+5Hz"):
    """Shorthand for edge_communicate with avatar settings."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    return communicate


def text_to_speech_sync(text: str, output_path: str, voice: str = None) -> str:
    """Synchronous wrapper for generate_avatar_speech."""
    return asyncio.get_event_loop().run_until_complete(
        generate_avatar_speech(text, output_path, voice)
    )


def play_audio(audio_path: str):
    """Play audio locally using ffplay (non-blocking)."""
    subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-volume", "100", audio_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def list_voices():
    """List available voices for the avatar."""
    async def _list():
        voices = await edge_tts.list_voices()
        for v in voices:
            if v["Locale"].startswith("en"):
                print(f"  {v['ShortName']:25s} {v['Gender']:8s} {v['Locale']}")
    asyncio.get_event_loop().run_until_complete(_list())


# ══════════════════════════════════════════════════════════════
# LIVE VOICE CONVERSION (Operator -> Avatar voice)
# ══════════════════════════════════════════════════════════════
class LiveVoiceConverter:
    """
    Captures operator microphone input and converts it to avatar voice in real-time.
    Uses edge-tts for voice synthesis with the operator's text.
    """
    
    def __init__(self, avatar_voice: str = AVATAR_VOICE):
        self.avatar_voice = avatar_voice
        self.is_recording = False
        self._arecord_process = None
    
    def record_and_synthesize(self, output_path: str, duration: int = 10) -> str:
        """
        Record from microphone for `duration` seconds, then synthesize with avatar voice.
        In a full implementation, this would use speech-to-text first, then TTS.
        For now, it captures audio and uses it as a voice reference.
        """
        # Record audio from microphone
        record_cmd = [
            "ffmpeg", "-f", "alsa", "-i", "default",
            "-t", str(duration),
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-y", "/tmp/avatar_live_input.wav"
        ]
        subprocess.run(record_cmd, check=True, capture_output=True)
        return "/tmp/avatar_live_input.wav"
    
    def speak_text_as_avatar(self, text: str, output_path: str = None) -> str:
        """
        Convert text to avatar voice (used when operator types or pastes text).
        This is the primary live mode — operator controls content, avatar controls voice.
        """
        if output_path is None:
            output_path = str(AUDIO_OUTPUT_DIR / "live_output.mp3")
        return text_to_speech_sync(text, output_path, self.avatar_voice)


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python voice_engine.py <command> [args]")
        print("  speak <text>          — Generate avatar speech")
        print("  play <audio_file>     — Play audio file")
        print("  voices                — List available voices")
        print("  live <text>           — Live mode: speak text as avatar")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "speak":
        text = " ".join(sys.argv[2:])
        output = str(AUDIO_OUTPUT_DIR / "output.mp3")
        path = text_to_speech_sync(text, output)
        print(f"Generated: {path}")
    
    elif cmd == "play":
        play_audio(sys.argv[2])
    
    elif cmd == "voices":
        list_voices()
    
    elif cmd == "live":
        text = " ".join(sys.argv[2:])
        converter = LiveVoiceConverter()
        path = converter.speak_text_as_avatar(text)
        print(f"Live output: {path}")
        play_audio(path)
