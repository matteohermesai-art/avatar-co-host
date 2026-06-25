# Avatar Co-Host — Setup Guide

## Overview

A local, privacy-respecting AI co-host system for internal innovation events.

**Key principles:**
- 🔒 **Fully local** — no cloud uploads, no data leaves the machine
- 👤 **Human-controlled** — the avatar never invents content
- 🎭 **Consistent voice** — same avatar voice throughout the event
- 🛡️ **Graceful fallback** — if anything fails, the main host takes over

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EVENT FLOW                                │
│                                                              │
│  [Script Template] → [Pre-generate Audio] → [OBS Scene]     │
│         ↓                                                    │
│  ┌──────────────────┐     ┌──────────────────────────┐      │
│  │  PRE-RECORDED     │     │  LIVE MODE                │      │
│  │  (90% of content) │     │  (unexpected questions)   │      │
│  │                   │     │                            │      │
│  │  Operator types   │     │  Operator speaks into      │      │
│  │  → Avatar speaks   │     │  mic → Avatar voice       │      │
│  └──────────────────┘     └──────────────────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────┐       │
│  │  FALLBACK CHAIN                                   │       │
│  │  1. Pre-generated audio → play section            │       │
│  │  2. Live synthesis → operator types text          │       │
│  │  3. Fallback audio → generic transitions          │       │
│  │  4. Main host speaks directly                     │       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install dependencies

```bash
pip install edge-tts
# Already available: ffmpeg, python3
```

### 2. Generate all pre-approved audio

```bash
cd ~/avatar-co-host
python3 script_runner.py generate
```

This reads `scripts/event_script.json` and generates all audio files in `audio/`.

### 3. Check status

```bash
python3 script_runner.py status
```

### 4. GUI (Interfaccia Grafica)

```bash
python3 gui_controller.py
```

Si apre una finestra con:
- **Pulsanti script** — clicca per riprodurre ogni sezione
- **Live mode** — digita testo e clicca "PARLA" per far parlare l'avatar
- **Fallback** — pulsanti rapido per situazioni impreviste
- **Stop** — interrompi la riproduzione

### 5. Set up OBS

```bash
python3 script_runner.py obs-setup
```

Then open OBS and import the generated profile and scene collection.

### 5. Test live mode

```bash
python3 live_mode.py interactive
```

Type text and the avatar speaks. Press Ctrl+C to exit.

### 6. Pre-generate fallbacks

```bash
python3 live_mode.py fallback-gen
```

### 7. Run a rehearsal

```bash
python3 live_mode.py rehearsal
```

## Customization

### Edit the event script

Edit `scripts/event_script.json` — replace bracketed placeholders:
- `[Team Name]` → actual team name
- `[Project Title]` → actual project title
- `[Presenter Name]` → actual presenter name
- `[one-line description]` → brief project description

### Change avatar voice

Edit `voice_engine.py`:
```python
AVATAR_VOICE = "en-US-JennyNeural"  # Change to any available voice
AVATAR_RATE = "-15%"  # Speed: -30% (slow) to +30% (fast)
AVATAR_PITCH = "+5Hz"  # Pitch: -10Hz to +10Hz
```

List available voices:
```bash
python3 voice_engine.py voices
```

### Add avatar image

Place your avatar image at `avatar/nova_avatar.png` (used in OBS scene).

## Fallback Plan

| Scenario | Action |
|----------|--------|
| TTS fails | Main host speaks directly |
| Audio file missing | Play fallback audio (generic transition) |
| OBS crashes | Switch to main host camera directly |
| Operator unavailable | Main host reads scripts manually |
| Network issue | Not applicable — fully local |

## Security

- ✅ No cloud API calls — all TTS runs locally via edge-tts
- ✅ No data leaves the machine
- ✅ No scripts stored in external services
- ✅ Audio files stored locally only
- ✅ Scripts are pre-approved before the event

## Directory Structure

```
avatar-co-host/
├── voice_engine.py        # TTS engine (voice generation)
├── script_runner.py       # Script generator + OBS controller
├── live_mode.py           # Live mode + fallback system
├── scripts/
│   └── event_script.json  # Approved scripts (edit this)
├── audio/
│   ├── *.mp3              # Generated audio files
│   ├── manifest.json      # Audio manifest
│   └── fallback/          # Fallback audio files
├── obs-configs/
│   ├── profiles/          # OBS profile
│   └── scenes/            # OBS scene collection
├── avatar/
│   └── nova_avatar.png    # Avatar image (add this)
├── output/                # Recorded output
└── docs/
    └── setup_guide.md     # This file
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `edge-tts` not found | `pip install edge-tts` |
| No audio output | Check `ffplay` is available: `which ffplay` |
| Audio too slow/fast | Adjust `AVATAR_RATE` in voice_engine.py |
| Voice sounds unnatural | Try different voice (see `voices` command) |
| OBS doesn't show avatar | Check image path in scene collection |
| Live mode lag | Shorter text = faster synthesis |

## Tips for a Smooth Event

1. **Generate audio the day before** — don't wait until the event
2. **Run a full rehearsal** at least once
3. **Have a backup laptop** ready with all files
4. **Test audio levels** in the venue beforehand
5. **Keep scripts short** — shorter = faster synthesis = less lag
6. **Prepare fallback phrases** for common situations
7. **Operator should practice** the live mode before the event
