#!/usr/bin/env python
"""Kokoro TTS - small desktop UI (tkinter, no extra dependencies).

Launch with "Kokoro TTS.bat", the Desktop shortcut, or:  .venv\\Scripts\\pythonw gui.py
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent.parent

# pythonw.exe starts with sys.stdout/stderr set to None; loguru (used by Kokoro)
# raises "Cannot log to objects of type 'NoneType'" in that case.
if sys.stdout is None or sys.stderr is None:
    (ROOT / "output").mkdir(parents=True, exist_ok=True)
    _logfile = open(ROOT / "output" / "gui.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or _logfile
    sys.stderr = sys.stderr or _logfile

import tts

CONFIG_PATH = ROOT / "config.json"
SAMPLE = (
    "Hello! This is Kokoro, an eighty-two million parameter text to speech model "
    "running locally. Type anything here, pick a voice, and press Speak."
)


def load_prefs() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_prefs(data: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.engine: tts.KokoroEngine | None = None
        self.audio = None
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.cancel = threading.Event()
        self.prefs = load_prefs()

        self.voices = tts.list_voices()
        self.voice_items: list[tuple[str, str]] = []  # (display, name)

        self._build_ui()
        self._poll()
        threading.Thread(target=self._init_engine, args=(self.selected_voice(),), daemon=True).start()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI #
    def _build_ui(self) -> None:
        root = self.root
        root.title("Kokoro-82M TTS")
        root.geometry("760x580")
        root.minsize(600, 460)
        root.option_add("*Font", ("Segoe UI", 10))

        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        pad = {"padx": 12, "pady": 6}
        top = ttk.Frame(root)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Voice").pack(side="left")
        self.voice_var = tk.StringVar()
        self.voice_box = ttk.Combobox(top, textvariable=self.voice_var, state="readonly", width=46)
        self.voice_box.pack(side="left", padx=(8, 16), fill="x", expand=True)
        self._fill_voices()

        ttk.Label(top, text="Speed").pack(side="left")
        self.speed_var = tk.DoubleVar(value=float(self.prefs.get("speed", 1.0)))
        self.speed_scale = ttk.Scale(
            top, from_=0.5, to=2.0, variable=self.speed_var, orient="horizontal", length=130,
            command=lambda _v: self._update_speed_label(),
        )
        self.speed_scale.pack(side="left", padx=(8, 6))
        self.speed_label = ttk.Label(top, width=6)
        self.speed_label.pack(side="left")
        self._update_speed_label()

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True, **pad)
        self.text = tk.Text(body, wrap="word", undo=True, height=14, relief="solid", borderwidth=1,
                            padx=10, pady=10, font=("Segoe UI", 11))
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.text.insert("1.0", self.prefs.get("text") or SAMPLE)
        self.text.bind("<Control-Return>", lambda _e: (self.speak(), "break")[1])
        self.text.bind("<Control-s>", lambda _e: (self.save(), "break")[1])

        controls = ttk.Frame(root)
        controls.pack(fill="x", padx=12, pady=(0, 4))

        self.speak_btn = ttk.Button(controls, text="Speak  (Ctrl+Enter)", command=self.speak, state="disabled")
        self.speak_btn.pack(side="left")
        self.stop_btn = ttk.Button(controls, text="Stop  (Esc)", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        self.save_btn = ttk.Button(controls, text="Save audio...  (Ctrl+S)", command=self.save, state="disabled")
        self.save_btn.pack(side="left", padx=(0, 8))
        self.play_var = tk.BooleanVar(value=bool(self.prefs.get("autoplay", True)))
        ttk.Checkbutton(controls, text="Play after generating", variable=self.play_var).pack(side="left")

        right = ttk.Frame(controls)
        right.pack(side="right")
        ttk.Button(right, text="Voices...", command=self.show_voices).pack(side="right", padx=4)
        ttk.Button(right, text="Open output", command=self.open_output).pack(side="right", padx=4)

        self.status_var = tk.StringVar(value="Loading Kokoro...")
        status = ttk.Label(root, textvariable=self.status_var, anchor="w", padding=(12, 4))
        status.pack(fill="x", side="bottom")

        root.bind("<Escape>", lambda _e: self.stop())

    def _fill_voices(self) -> None:
        preferred = self.prefs.get("voice") or tts.DEFAULT_VOICE
        for lang in sorted(self.voices, key=lambda k: (k not in "ab", k)):
            for name in self.voices[lang]:
                self.voice_items.append((f"{name}  |  {tts.voice_label(name)}", name))
        self.voice_box["values"] = [d for d, _ in self.voice_items]
        match = next((d for d, n in self.voice_items if n == preferred), None)
        if match is None and self.voice_items:
            match = self.voice_items[0][0]
        if match:
            self.voice_var.set(match)

    def _update_speed_label(self) -> None:
        self.speed_label.configure(text=f"{self.speed_var.get():.2f}x")

    def selected_voice(self) -> str:
        current = self.voice_var.get()
        for display, name in self.voice_items:
            if display == current:
                return name
        return tts.DEFAULT_VOICE

    # ------------------------------------------------------------- actions #
    def _init_engine(self, warmup_voice: str) -> None:
        try:
            engine = tts.KokoroEngine(device=os.environ.get("KOKORO_DEVICE", "auto"))
            engine.warmup(warmup_voice)
            self.events.put(("ready", engine))
        except Exception as exc:
            self.events.put(("fatal", str(exc)))

    def speak(self) -> None:
        if self.engine is None or self.busy:
            return
        text = self.text.get("1.0", "end").strip()
        if not text:
            self.status_var.set("Type some text first.")
            return
        self.busy = True
        self.cancel.clear()
        self.speak_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_var.set("Generating...")
        voice, speed = self.selected_voice(), round(self.speed_var.get(), 2)
        autoplay = bool(self.play_var.get())
        threading.Thread(target=self._synth_worker, args=(text, voice, speed, autoplay), daemon=True).start()

    def _synth_worker(self, text: str, voice: str, speed: float, autoplay: bool) -> None:
        started = time.perf_counter()
        try:

            def progress(_index: int, seconds: float) -> None:
                self.events.put(("progress", seconds))

            audio = self.engine.synth(text, voice=voice, speed=speed, progress=progress, cancel=self.cancel)
            elapsed = time.perf_counter() - started
            if audio.size == 0:
                self.events.put(("done", None, elapsed, voice))
                return
            self.events.put(("done", audio, elapsed, voice))
            if autoplay and not self.cancel.is_set():
                self.events.put(("status", "Playing..."))
                tts.play_audio(audio)
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            self.events.put(("idle",))

    def stop(self) -> None:
        self.cancel.set()
        tts.stop_playback()
        self.status_var.set("Stopped.")

    def save(self) -> None:
        if self.audio is None:
            return
        path = filedialog.asksaveasfilename(
            title="Save audio",
            defaultextension=".wav",
            initialdir=str(tts.OUTPUT_DIR),
            filetypes=[("WAV audio", "*.wav"), ("MP3 audio", "*.mp3"), ("FLAC audio", "*.flac"), ("Ogg audio", "*.ogg")],
        )
        if not path:
            return
        try:
            out = tts.save_audio(self.audio, Path(path))
            self.status_var.set(f"Saved {out}")
        except Exception as exc:
            messagebox.showerror("Could not save", str(exc))

    def open_output(self) -> None:
        tts.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(tts.OUTPUT_DIR)  # type: ignore[attr-defined]

    def show_voices(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Available voices")
        win.geometry("460x520")
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        box = tk.Listbox(frame, font=("Consolas", 10))
        sb = ttk.Scrollbar(frame, orient="vertical", command=box.yview)
        box.configure(yscrollcommand=sb.set)
        box.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for lang in sorted(self.voices, key=lambda k: (k not in "ab", k)):
            box.insert("end", f"-- {tts.LANG_NAMES.get(lang, lang)} ({lang}) --")
            for name in self.voices[lang]:
                box.insert("end", f"  {name:<12} {tts.voice_label(name)}")
        ttk.Label(win, text="Tip: you can blend voices, e.g. af_heart,af_bella",
                  padding=10).pack(side="bottom", anchor="w")

    # --------------------------------------------------------------- queue #
    def _poll(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "ready":
                    self.engine = event[1]
                    self.speak_btn.configure(state="normal")
                    self.status_var.set(
                        f"Ready on {self.engine.device.upper()} - "
                        f"{sum(len(v) for v in self.voices.values())} voices - "
                        f"{Path(self.engine.weights_path).name}"
                    )
                elif kind == "fatal":
                    self.status_var.set("Kokoro could not start.")
                    try:
                        (ROOT / "output" / "gui_error.log").write_text(event[1] + "\n", encoding="utf-8")
                    except Exception:
                        pass
                    messagebox.showerror("Kokoro could not start", event[1])
                elif kind == "progress":
                    self.status_var.set(f"Generating... {event[1]:.1f}s of audio")
                elif kind == "done":
                    audio, elapsed, voice = event[1], event[2], event[3]
                    self.busy = False
                    if audio is None:
                        self.status_var.set("Nothing to speak.")
                        continue
                    self.audio = audio
                    self.save_btn.configure(state="normal")
                    duration = audio.size / tts.SAMPLE_RATE
                    rtf = duration / elapsed if elapsed else 0
                    self.status_var.set(
                        f"{len(audio)} samples / {duration:.2f}s audio in {elapsed:.2f}s "
                        f"({rtf:.0f}x realtime) - {voice}"
                    )
                elif kind == "status":
                    self.status_var.set(event[1])
                elif kind == "error":
                    self.status_var.set("Generation failed.")
                    messagebox.showerror("Generation failed", event[1])
                elif kind == "idle":
                    self.busy = False
                    self.speak_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _on_close(self) -> None:
        self.cancel.set()
        tts.stop_playback()
        save_prefs({
            "voice": self.selected_voice(),
            "speed": round(self.speed_var.get(), 2),
            "autoplay": bool(self.play_var.get()),
            "text": self.text.get("1.0", "end").strip()[:20000],
        })
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()