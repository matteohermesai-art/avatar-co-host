#!/usr/bin/env python3
"""
Avatar Co-Host — Live Mode Controller
Handles real-time voice conversion: operator speaks → avatar voice output.
Also manages fallback procedures for the event.
"""

import json
import os
import subprocess
import sys
import time
import threading
from pathlib import Path

try:
    import asyncio
    import edge_tts
except ImportError:
    print("ERROR: edge-tts not installed")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).parent  # avatar-co-host/
AUDIO_DIR = BASE_DIR / "audio"
SCRIPTS_DIR = BASE_DIR / "scripts"

AVATAR_VOICE = "it-IT-ElsaNeural"
AVATAR_RATE = "-10%"
AVATAR_PITCH = "+5Hz"

# Audio routing
AUDIO_OUTPUT = str(AUDIO_DIR / "live_output.mp3")
FADE_IN_DURATION = 0.3  # seconds
FADE_OUT_DURATION = 0.5  # seconds


async def synthesize_live(text: str, output_path: str) -> str:
    """Quick synthesis for live mode — optimized for speed."""
    communicate = edge_tts.Communicate(
        text, AVATAR_VOICE,
        rate=AVATAR_RATE,
        pitch=AVATAR_PITCH
    )
    await communicate.save(output_path)
    return output_path


def play_live_audio(audio_path: str, fade_in: bool = True, fade_out: bool = True):
    """Play audio with optional fade in/out for smooth transitions."""
    cmd = ["ffplay", "-nodisp", "-autoexit"]
    
    if fade_in:
        cmd += ["-af", "afade=t=in:st=0:d=0.3"]
    if fade_out:
        cmd += ["-af", "afade=t=out:st=0:d=0.5"]
    
    cmd += ["-volume", "100", audio_path]
    
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def live_operator_mode():
    """
    Interactive live mode: operator types text, avatar speaks.
    This is the primary live interaction method — human controls content.
    """
    print("=" * 60)
    print("  AVATAR CO-HOST — LIVE MODE")
    print("  Type text and press Enter to have the avatar speak.")
    print("  Commands: /play <section>, /status, /quit")
    print("=" * 60)
    
    while True:
        try:
            user_input = input("\n🎤 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting live mode.")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() == "/quit":
            print("Exiting live mode.")
            break
        
        elif user_input.lower() == "/status":
            # Check which audio files exist
            manifest_path = AUDIO_DIR / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest = json.load(f)
                ready = sum(1 for e in manifest["files"] if os.path.exists(e["file"]))
                total = len(manifest["files"])
                print(f"  Audio ready: {ready}/{total}")
            else:
                print("  No audio generated yet. Run 'python script_runner.py generate'")
            continue
        
        elif user_input.lower().startswith("/play "):
            section_id = user_input[6:].strip()
            audio_path = AUDIO_DIR / f"{section_id}.mp3"
            if audio_path.exists():
                print(f"  Playing: {section_id}")
                play_live_audio(str(audio_path))
            else:
                print(f"  Not found: {section_id}")
            continue
        
        # Live speak — operator types, avatar speaks
        print(f"  🎙️ Avatar says: {user_input[:60]}...")
        try:
            asyncio.get_event_loop().run_until_complete(
                synthesize_live(user_input, AUDIO_OUTPUT)
            )
            play_live_audio(AUDIO_OUTPUT)
            print("  ✓ Done")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            print("  FALLBACK: Main host should speak directly.")


# ══════════════════════════════════════════════════════════════
# FALLBACK SYSTEM
# ══════════════════════════════════════════════════════════════
class FallbackManager:
    """
    Manages fallback procedures during the event.
    If something fails, the system degrades gracefully.
    """
    
    FALLBACK_AUDIO = {
        "greeting": "Hello everyone, I'm Nova. Let's get started!",
        "technical_issue": "We're experiencing a small technical issue. Please bear with us for a moment.",
        "transition": "Thank you for that presentation! Let's move on to our next project.",
        "time_check": "Just a quick reminder — we're running on schedule.",
        "closing": "Thank you all for being here today. What a wonderful showcase!",
    }
    
    def __init__(self):
        self.fallback_dir = AUDIO_DIR / "fallback"
        self.fallback_dir.mkdir(exist_ok=True)
        self._pre_generated = {}
    
    def pre_generate_fallbacks(self):
        """Pre-generate all fallback audio files."""
        print("Generating fallback audio files...")
        for key, text in self.FALLBACK_AUDIO.items():
            output_path = str(self.fallback_dir / f"{key}.mp3")
            try:
                asyncio.get_event_loop().run_until_complete(
                    synthesize_live(text, output_path)
                )
                self._pre_generated[key] = output_path
                print(f"  ✓ {key}")
            except Exception as e:
                print(f"  ✗ {key}: {e}")
        
        print(f"Fallback ready: {len(self._pre_generated)}/{len(self.FALLBACK_AUDIO)}")
    
    def trigger_fallback(self, key: str):
        """Play a fallback audio file."""
        if key in self._pre_generated:
            play_live_audio(self._pre_generated[key])
            print(f"Fallback triggered: {key}")
        else:
            print(f"Fallback not available: {key}")
    
    def live_fallback(self, text: str):
        """
        Ultimate fallback: if pre-generated files fail,
        generate audio on the fly.
        """
        output_path = str(self.fallback_dir / "on_the_fly.mp3")
        try:
            asyncio.get_event_loop().run_until_complete(
                synthesize_live(text, output_path)
            )
            play_live_audio(output_path)
            print(f"Live fallback: {text[:50]}...")
        except Exception as e:
            print(f"FALLBACK FAILED: {e}")
            print(">>> MAIN HOST SHOULD SPEAK DIRECTLY <<<")


# ══════════════════════════════════════════════════════════════
# EVENT CONTROLLER (for rehearsals and testing)
# ══════════════════════════════════════════════════════════════
def run_rehearsal():
    """
    Run a full rehearsal of the event.
    Plays all sections in sequence with timings.
    """
    manifest_path = AUDIO_DIR / "manifest.json"
    if not manifest_path.exists():
        print("ERROR: No audio generated. Run 'generate' first.")
        return
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    print("=" * 60)
    print("  EVENT REHEARSAL")
    print(f"  Event: {manifest['event']}")
    print(f"  Sections: {len(manifest['files'])}")
    print("=" * 60)
    
    fallback = FallbackManager()
    
    for i, entry in enumerate(manifest["files"]):
        section_id = entry["id"]
        audio_path = entry["file"]
        timing = entry.get("timing", "")
        notes = entry.get("notes", "")
        
        if not os.path.exists(audio_path):
            print(f"\n[{i+1}/{len(manifest['files'])}] SKIP {section_id} (file missing)")
            continue
        
        print(f"\n[{i+1}/{len(manifest['files'])}] {section_id}")
        print(f"  Timing: {timing}")
        print(f"  Notes: {notes}")
        print(f"  Playing in 3 seconds...")
        time.sleep(3)
        
        play_live_audio(audio_path)
        
        # Wait for audio to finish (rough estimate)
        try:
            duration = float(subprocess.check_output(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
            ).decode().strip())
            time.sleep(duration + 1)
        except:
            time.sleep(5)
    
    print("\n" + "=" * 60)
    print("  REHEARSAL COMPLETE")
    print("=" * 60)


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Avatar Co-Host — Live Mode & Fallback Controller")
        print()
        print("Usage:")
        print("  python live_mode.py interactive     Live operator mode")
        print("  python live_mode.py fallback-gen     Pre-generate fallback audio")
        print("  python live_mode.py fallback <key>   Trigger fallback")
        print("  python live_mode.py rehearsal        Full event rehearsal")
        print()
        print("Fallback keys: greeting, technical_issue, transition, time_check, closing")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "interactive":
        live_operator_mode()
    
    elif cmd == "fallback-gen":
        fb = FallbackManager()
        fb.pre_generate_fallbacks()
    
    elif cmd == "fallback":
        if len(sys.argv) < 3:
            print("ERROR: fallback key required")
            sys.exit(1)
        fb = FallbackManager()
        fb.trigger_fallback(sys.argv[2])
    
    elif cmd == "rehearsal":
        run_rehearsal()
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
