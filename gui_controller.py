#!/usr/bin/env python3
"""
Avatar Co-Host — GUI Controller
Simple graphical interface to control the avatar during events.
Shows on screen when avatar is speaking.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import os
import json
import threading
from pathlib import Path

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
SCRIPTS_DIR = BASE_DIR / "scripts"


class AvatarGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Avatar Co-Host — Control")
        self.root.geometry("800x600")
        self.root.configure(bg="#1a1a2e")
        
        # Load event script
        self.script = self._load_script()
        self.is_playing = False
        
        self._build_ui()
    
    def _load_script(self):
        script_path = SCRIPTS_DIR / "event_script.json"
        if script_path.exists():
            with open(script_path) as f:
                return json.load(f)
        return {"sections": [], "live_mode_prompts": {}}
    
    def _build_ui(self):
        # Style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Arial", 18, "bold"), foreground="#e94560", background="#1a1a2e")
        style.configure("Section.TLabel", font=("Arial", 11), foreground="#eaeaea", background="#16213e")
        style.configure("Play.TButton", font=("Arial", 10, "bold"), padding=5)
        style.configure("Status.TLabel", font=("Arial", 10), foreground="#0f3460", background="#eaeaea")
        
        # Header
        header = tk.Frame(self.root, bg="#1a1a2e", pady=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="🎙️ AVATAR CO-HOST", style="Title.TLabel").pack()
        ttk.Label(header, text=self.script.get("event", "Event"), font=("Arial", 12), foreground="#eaeaea", background="#1a1a2e").pack()
        
        # Main content
        main = tk.Frame(self.root, bg="#16213e")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left: Script sections
        left = tk.Frame(main, bg="#16213e")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(left, text="📜 Script Sections", style="Section.TLabel").pack(anchor=tk.W, pady=(0, 5))
        
        # Scrollable list of sections
        canvas = tk.Canvas(left, bg="#16213e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(left, orient=tk.VERTICAL, command=canvas.yview)
        self.sections_frame = tk.Frame(canvas, bg="#16213e")
        
        self.sections_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.sections_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate sections
        for section in self.script.get("sections", []):
            self._add_section_button(section)
        
        # Right: Controls
        right = tk.Frame(main, bg="#16213e", width=250)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right.pack_propagate(False)
        
        ttk.Label(right, text="🎮 Controls", style="Section.TLabel").pack(anchor=tk.W, pady=(0, 10))
        
        # Live mode input
        ttk.Label(right, text="Live Mode:", font=("Arial", 10, "bold"), foreground="#eaeaea", background="#16213e").pack(anchor=tk.W)
        
        self.live_text = scrolledtext.ScrolledText(right, height=4, width=28, font=("Arial", 10))
        self.live_text.pack(pady=(0, 5))
        
        live_btn = tk.Button(right, text="🎙️ PARLA (Live)", font=("Arial", 10, "bold"),
                            bg="#e94560", fg="white", command=self._live_speak)
        live_btn.pack(fill=tk.X, pady=(0, 15))
        
        # Fallback buttons
        ttk.Label(right, text="🛡️ Fallback:", font=("Arial", 10, "bold"), foreground="#eaeaea", background="#16213e").pack(anchor=tk.W)
        
        fallbacks = [
            ("Problema Tecnico", "technical_issue"),
            ("Transizione", "transition"),
            ("Pausa Pranzo", "lunch_back"),
            ("Chiusura", "closing"),
        ]
        for label, key in fallbacks:
            btn = tk.Button(right, text=f"⏵ {label}", font=("Arial", 9),
                           bg="#0f3460", fg="white", command=lambda k=key: self._play_fallback(k))
            btn.pack(fill=tk.X, pady=2)
        
        # Currently playing
        ttk.Label(right, text="📢 In riproduzione:", font=("Arial", 9), foreground="#eaeaea", background="#16213e").pack(anchor=tk.W, pady=(15, 0))
        self.current_label = ttk.Label(right, text="(nessuno)", font=("Arial", 9, "italic"), foreground="#a0a0a0", background="#16213e")
        self.current_label.pack(anchor=tk.W)
        
        # Stop button
        stop_btn = tk.Button(right, text="⏹ STOP", font=("Arial", 10, "bold"),
                            bg="#333333", fg="white", command=self._stop_playback)
        stop_btn.pack(fill=tk.X, side=tk.BOTTOM, pady=(15, 0))
        
        # Status bar
        status = tk.Frame(self.root, bg="#0f3460", pady=5)
        status.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(status, text="Pronto — Audio generati: 29", style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT, padx=10)
    
    def _add_section_button(self, section):
        section_id = section["id"]
        title = section.get("title", section_id)
        timing = section.get("timing", "")
        
        btn = tk.Button(self.sections_frame, text=f"⏵ {title} ({timing})",
                       font=("Arial", 9), bg="#0f3460", fg="white", anchor=tk.W,
                       command=lambda sid=section_id: self._play_section(sid))
        btn.pack(fill=tk.X, pady=1)
    
    def _play_section(self, section_id):
        """Play a pre-generated section audio file."""
        audio_path = AUDIO_DIR / f"{section_id}.mp3"
        if not audio_path.exists():
            messagebox.showerror("Errore", f"Audio non trovato: {section_id}\nEsegui prima: python avatar_co_host.py generate")
            return
        
        self._play_audio(str(audio_path), section_id)
    
    def _play_fallback(self, key):
        """Play a fallback audio file."""
        audio_path = AUDIO_DIR / "fallback" / f"{key}.mp3"
        if not audio_path.exists():
            messagebox.showerror("Errore", f"Fallback non trovato: {key}")
            return
        self._play_audio(str(audio_path), f"Fallback: {key}")
    
    def _live_speak(self):
        """Live mode: operator types text, avatar speaks."""
        text = self.live_text.get("1.0", tk.END).strip()
        if not text:
            return
        
        self.current_label.config(text=f"Live: {text[:40]}...")
        self.status_label.config(text="Generazione in corso...")
        
        def generate():
            import asyncio
            import edge_tts
            
            async def do_it():
                out = str(AUDIO_DIR / "live_output.mp3")
                await edge_tts.Communicate(text, "it-IT-ElsaNeural", rate="-10%", pitch="+5Hz").save(out)
                return out
            
            loop = asyncio.new_event_loop()
            output_path = loop.run_until_complete(do_it())
            loop.close()
            
            self.root.after(0, lambda: self._play_audio(output_path, "Live"))
        
        threading.Thread(target=generate, daemon=True).start()
    
    def _play_audio(self, audio_path: str, title: str):
        self.current_label.config(text=f"🔊 {title}")
        self.status_label.config(text=f"In riproduzione: {title}")
        self.is_playing = True
        
        # Play via ffplay
        subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-volume", "100", audio_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    
    def _stop_playback(self):
        os.system("pkill -f ffplay")
        self.current_label.config(text="(fermato)")
        self.is_playing = False
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = AvatarGUI()
    app.run()
