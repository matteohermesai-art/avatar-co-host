#!/usr/bin/env python3
"""
Avatar Co-Host — Main Entry Point
Orchestrates all subsystems for the event.
"""

import argparse
import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))


def main():
    parser = argparse.ArgumentParser(
        description="Avatar Co-Host — AI Co-Host System for Internal Events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all pre-approved audio files
  python avatar_co_host.py generate

  # Check audio status
  python avatar_co_host.py status

  # Live operator mode (interactive)
  python avatar_co_host.py live

  # Generate OBS configuration
  python avatar_co_host.py obs-setup

  # Pre-generate fallback audio
  python avatar_co_host.py fallback

  # Run rehearsal
  python avatar_co_host.py rehearsal

Quick workflow:
  1. python avatar_co_host.py generate       (prepare audio)
  2. python avatar_co_host.py obs-setup       (configure OBS)
  3. python avatar_co_host.py fallback        (prepare fallbacks)
  4. python avatar_co_host.py rehearsal       (test everything)
  5. python avatar_co_host.py live            (start event)
"""
    )
    
    parser.add_argument(
        "command",
        choices=["generate", "status", "live", "obs-setup", "fallback", "rehearsal", "voices"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "args",
        nargs="*",
        help="Additional arguments for the command"
    )
    
    args = parser.parse_args()
    
    if args.command == "generate":
        from script_runner import generate_all_scripts
        generate_all_scripts()
    
    elif args.command == "status":
        from script_runner import AUDIO_DIR
        manifest_path = AUDIO_DIR / "manifest.json"
        if manifest_path.exists():
            import json
            with open(manifest_path) as f:
                manifest = json.load(f)
            print(f"Event: {manifest['event']}")
            print(f"Voice: {manifest['voice']}")
            print(f"Generated: {manifest['generated_at']}")
            ready = sum(1 for e in manifest["files"] if os.path.exists(e["file"]))
            total = len(manifest["files"])
            print(f"Audio ready: {ready}/{total}")
            for entry in manifest["files"]:
                s = "OK" if os.path.exists(entry["file"]) else "MISSING"
                print(f"  [{s}] {entry['id']:30s} {entry.get('timing', '')}")
        else:
            print("No audio generated. Run: python avatar_co_host.py generate")
    
    elif args.command == "live":
        from live_mode import live_operator_mode
        live_operator_mode()
    
    elif args.command == "obs-setup":
        from script_runner import generate_obs_profile, generate_obs_scene_collection
        generate_obs_profile()
        generate_obs_scene_collection()
        print("\nOBS Setup complete!")
        print("\nNext steps:")
        print("  1. Open OBS Studio")
        print("  2. Profile → Import → obs-configs/profiles/AvatarCoHost/")
        print("  3. Scene Collection → Import → obs-configs/scenes/AvatarCoHost.json")
        print("  4. Add your avatar image to the 'Avatar Speaking' scene")
        print("  5. Configure audio input for live mode")
    
    elif args.command == "fallback":
        from live_mode import FallbackManager
        fb = FallbackManager()
        fb.pre_generate_fallbacks()
    
    elif args.command == "rehearsal":
        from live_mode import run_rehearsal
        run_rehearsal()
    
    elif args.command == "voices":
        from voice_engine import list_voices
        print("Available English voices:")
        list_voices()


if __name__ == "__main__":
    main()
