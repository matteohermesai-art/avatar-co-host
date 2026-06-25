#!/usr/bin/env python3
"""
Avatar Co-Host — Script Generator & OBS Controller
Generates pre-approved audio files and controls OBS for live event playback.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import asyncio
    import edge_tts
except ImportError:
    print("ERROR: edge-tts not installed. Run: pip install edge-tts")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).parent  # avatar-co-host/
SCRIPTS_DIR = BASE_DIR / "scripts"
AUDIO_DIR = BASE_DIR / "audio"
OBS_CONFIGS = BASE_DIR / "obs-configs"

AUDIO_DIR.mkdir(exist_ok=True)
OBS_CONFIGS.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════
# AVATAR VOICE SETTINGS
# ══════════════════════════════════════════════════════════════
AVATAR_VOICE = "en-US-JennyNeural"
AVATAR_RATE = "-15%"
AVATAR_PITCH = "+5Hz"


async def generate_speech(text: str, output_path: str, voice: str = AVATAR_VOICE) -> str:
    """Generate avatar speech and save to file."""
    communicate = edge_tts.Communicate(text, voice, rate=AVATAR_RATE, pitch=AVATAR_PITCH)
    await communicate.save(output_path)
    return output_path


def generate_all_scripts(script_json: str = None):
    """
    Pre-generate all approved audio files from the event script.
    Run this BEFORE the event to have everything ready.
    """
    script_json = script_json or str(SCRIPTS_DIR / "event_script.json")
    
    with open(script_json) as f:
        event = json.load(f)
    
    print(f"Generating audio for: {event['event']}")
    print(f"Voice: {AVATAR_VOICE}")
    print(f"Sections: {len(event['sections'])}")
    print("=" * 60)
    
    generated = []
    
    for section in event["sections"]:
        section_id = section["id"]
        text = section.get("avatar_script", "")
        
        if not text:
            print(f"  SKIP {section_id}: No avatar script")
            continue
        
        output_path = str(AUDIO_DIR / f"{section_id}.mp3")
        
        print(f"  Generating: {section_id}...")
        print(f"    Text: {text[:80]}...")
        
        asyncio.get_event_loop().run_until_complete(
            generate_speech(text, output_path)
        )
        
        generated.append({
            "id": section_id,
            "file": output_path,
            "timing": section.get("timing", ""),
            "speaker": section.get("speaker", "avatar"),
            "notes": section.get("notes", "")
        })
        
        print(f"    OK: {output_path}")
    
    # Also generate live mode prompts
    print("\n  Generating live mode prompts...")
    for prompt_id, prompt_text in event.get("live_mode_prompts", {}).items():
        output_path = str(AUDIO_DIR / f"live_{prompt_id}.mp3")
        asyncio.get_event_loop().run_until_complete(
            generate_speech(prompt_text, output_path)
        )
        generated.append({
            "id": f"live_{prompt_id}",
            "file": output_path,
            "notes": "Live mode prompt"
        })
        print(f"    OK: live_{prompt_id}.mp3")
    
    # Save manifest
    manifest_path = AUDIO_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({
            "event": event["event"],
            "voice": AVATAR_VOICE,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "files": generated
        }, f, indent=2)
    
    print("=" * 60)
    print(f"Generated {len(generated)} audio files")
    print(f"Manifest: {manifest_path}")
    return generated


def play_section(section_id: str):
    """Play a pre-generated section audio file."""
    audio_path = AUDIO_DIR / f"{section_id}.mp3"
    if not audio_path.exists():
        print(f"ERROR: {audio_path} not found. Run 'generate' first.")
        return False
    
    # Play via ffplay (OBS will capture this)
    subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-volume", "100", str(audio_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(f"Playing: {section_id}")
    return True


def live_speak(text: str, output_name: str = "live_output.mp3"):
    """
    Live mode: operator types/pastes text, avatar speaks it.
    This is the controlled live interaction — human decides what to say,
    avatar provides the voice.
    """
    output_path = str(AUDIO_DIR / output_name)
    asyncio.get_event_loop().run_until_complete(
        generate_speech(text, output_path)
    )
    play_path = output_path
    
    # Play it
    subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-volume", "100", play_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(f"Live: '{text[:60]}...'")
    return play_path


# ══════════════════════════════════════════════════════════════
# OBS INTEGRATION
# ══════════════════════════════════════════════════════════════
def generate_obs_profile():
    """Generate OBS profile for the avatar co-host setup."""
    profile_dir = OBS_CONFIGS / "profiles" / "AvatarCoHost"
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    # OBS Profile config (obs-studio config format)
    profile_config = {
        "General": {
            "Name": "AvatarCoHost"
        },
        "Video": {
            "BaseCX": 1920,
            "BaseCY": 1080,
            "OutputCX": 1920,
            "OutputCY": 1080,
            "FPSType": 0,
            "FPSCommon": "30"
        },
        "Output": {
            "Mode": "Simple",
            "Streaming": {
                "Encoder": "x264",
                "Bitrate": 2500
            },
            "Recording": {
                "FilePath": str(BASE_DIR / "output"),
                "Format": "mp4",
                "Encoder": "ffmpeg",
                "MuxerCustom": ""
            }
        },
        "Audio": {
            "SampleRate": 44100,
            "ChannelSetup": "Stereo"
        }
    }
    
    with open(profile_dir / "basic.ini", "w") as f:
        for section, values in profile_config.items():
            f.write(f"[{section}]\n")
            for key, value in values.items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        f.write(f"{subkey}={subvalue}\n")
                else:
                    f.write(f"{key}={value}\n")
            f.write("\n")
    
    print(f"OBS Profile generated: {profile_dir}")
    return profile_dir


def generate_obs_scene_collection():
    """Generate OBS scene collection for the event."""
    scenes_dir = OBS_CONFIGS / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    
    scene_collection = {
        "name": "AvatarCoHost",
        "scenes": [
            {
                "name": "Avatar Speaking",
                "sources": [
                    {
                        "name": "Avatar Video",
                        "type": "image_source",
                        "settings": {
                            "file": str(BASE_DIR / "avatar" / "nova_avatar.png")
                        }
                    },
                    {
                        "name": "Avatar Audio",
                        "type": "wasapi_output_capture",
                        "settings": {
                            "device_id": "default"
                        }
                    },
                    {
                        "name": "Lower Third",
                        "type": "text_gdiplus",
                        "settings": {
                            "text": "Nova — AI Co-Host",
                            "font": {"face": "Arial", "size": 24, "bold": True},
                            "color": "#FFFFFF"
                        },
                        "pos": {"x": 100, "y": 900},
                        "size": {"cx": 400, "cy": 50}
                    }
                ]
            },
            {
                "name": "Main Host",
                "sources": [
                    {
                        "name": "Host Camera",
                        "type": "dshow_input_capture",
                        "settings": {
                            "video_device_id": "Default Camera"
                        }
                    }
                ]
            },
            {
                "name": "Project Presentation",
                "sources": [
                    {
                        "name": "Screen Capture",
                        "type": "monitor_capture",
                        "settings": {
                            "monitor": 0
                        }
                    },
                    {
                        "name": "Avatar Overlay",
                        "type": "image_source",
                        "settings": {
                            "file": str(BASE_DIR / "avatar" / "nova_small.png")
                        },
                        "pos": {"x": 1600, "y": 800},
                        "size": {"cx": 300, "cy": 200}
                    }
                ]
            },
            {
                "name": "Break Screen",
                "sources": [
                    {
                        "name": "Break Image",
                        "type": "image_source",
                        "settings": {
                            "file": str(BASE_DIR / "output" / "break_slide.png")
                        }
                    },
                    {
                        "name": "Timer",
                        "type": "text_gdiplus",
                        "settings": {
                            "text": "Back in 15:00",
                            "font": {"face": "Arial", "size": 48, "bold": True},
                            "color": "#FFFFFF"
                        },
                        "pos": {"x": 760, "y": 440}
                    }
                ]
            }
        ]
    }
    
    with open(scenes_dir / "AvatarCoHost.json", "w") as f:
        json.dump(scene_collection, f, indent=2)
    
    print(f"OBS Scene Collection: {scenes_dir / 'AvatarCoHost.json'}")
    return scenes_dir


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Avatar Co-Host — Script Generator & Controller")
        print()
        print("Usage:")
        print("  python script_runner.py generate          Generate all audio files")
        print("  python script_runner.py play <section_id>  Play a section")
        print("  python script_runner.py live <text>       Live: speak text as avatar")
        print("  python script_runner.py obs-setup         Generate OBS config")
        print("  python script_runner.py status            Check audio files status")
        print()
        print("Examples:")
        print("  python script_runner.py generate")
        print("  python script_runner.py play opening")
        print('  python script_runner.py live "Hello everyone!"')
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "generate":
        generate_all_scripts()
    
    elif cmd == "play":
        if len(sys.argv) < 3:
            print("ERROR: section_id required")
            sys.exit(1)
        play_section(sys.argv[2])
    
    elif cmd == "live":
        if len(sys.argv) < 3:
            print("ERROR: text required")
            sys.exit(1)
        live_speak(" ".join(sys.argv[2:]))
    
    elif cmd == "obs-setup":
        generate_obs_profile()
        generate_obs_scene_collection()
        print("\nOBS setup complete!")
        print("1. Open OBS")
        print("2. Import profile from obs-configs/profiles/AvatarCoHost/")
        print("3. Import scene collection from obs-configs/scenes/AvatarCoHost.json")
        print("4. Set avatar image in 'Avatar Speaking' scene")
    
    elif cmd == "status":
        manifest_path = AUDIO_DIR / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
            print(f"Event: {manifest['event']}")
            print(f"Voice: {manifest['voice']}")
            print(f"Generated: {manifest['generated_at']}")
            print(f"Files: {len(manifest['files'])}")
            for entry in manifest["files"]:
                exists = "OK" if os.path.exists(entry["file"]) else "MISSING"
                print(f"  [{exists}] {entry['id']:30s} {entry['timing']:10s}")
        else:
            print("No manifest found. Run 'generate' first.")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
