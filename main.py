#!/usr/bin/env python3
"""
BestClick  –  Professional Auto Clicker
by @nummersechs  ·  bismillah ewa
"""

import customtkinter as ctk
import tkinter as tk
import threading
import time
import json
import os
import platform
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController, Listener as KeyboardListener

# ──────────────────────────────────────────────────────────────────────────────
# App constants
# ──────────────────────────────────────────────────────────────────────────────

APP_NAME = "BestClick"
SUBTITLE  = "by @nummersechs  ·  bismillah"
VERSION   = "1.0.0"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG: dict = {
    "start_key":  "f6",
    "stop_key":   "f7",
    "pause_key":  "f8",
    "click_key":  "k",
}

# ──────────────────────────────────────────────────────────────────────────────
# Config manager
# ──────────────────────────────────────────────────────────────────────────────

class Config:
    def __init__(self) -> None:
        self.data: dict = DEFAULT_CONFIG.copy()
        self._load()

    def _load(self) -> None:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    self.data.update(json.load(f))
            except Exception:
                pass

    def save(self) -> None:
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"[Config] save error: {e}")

    def get(self, k: str, default=None):
        return self.data.get(k, default)

    def set(self, k: str, v) -> None:
        self.data[k] = v


# ──────────────────────────────────────────────────────────────────────────────
# Auto-clicker engine  (runs in a daemon thread)
# ──────────────────────────────────────────────────────────────────────────────

class Engine:
    def __init__(self) -> None:
        self.mouse   = MouseController()
        self.kbd     = KeyboardController()
        self.running = False
        self.paused  = False
        self._thread = None
        self.clicks  = 0
        self.on_tick = None   # callback(count: int)
        self.on_done = None   # callback()

    # ── public ────────────────────────────────────────────────────────────────

    def start(self, click_type: str, interval_ms: int, repeat_count: int,
              click_key: str = "k") -> None:
        if self.running:
            return
        self.running = True
        self.paused  = False
        self.clicks  = 0
        self._thread = threading.Thread(
            target=self._loop,
            args=(click_type, max(1, interval_ms), repeat_count, click_key),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        self.paused  = False

    def toggle_pause(self) -> bool:
        if self.running:
            self.paused = not self.paused
        return self.paused

    # ── internal ──────────────────────────────────────────────────────────────

    def _loop(self, click_type: str, interval_ms: int, repeat_count: int,
              click_key: str) -> None:
        while self.running:
            if not self.paused:
                self._act(click_type, click_key)
                self.clicks += 1
                if self.on_tick:
                    self.on_tick(self.clicks)
                if repeat_count > 0 and self.clicks >= repeat_count:
                    self.running = False
                    if self.on_done:
                        self.on_done()
                    break
            time.sleep(interval_ms / 1000.0)

    def _act(self, click_type: str, click_key: str) -> None:
        try:
            if click_type == "left":
                self.mouse.click(Button.left)
            elif click_type == "right":
                self.mouse.click(Button.right)
            elif click_type == "middle":
                self.mouse.click(Button.middle)
            elif click_type == "double":
                self.mouse.click(Button.left, 2)
            elif click_type == "key" and click_key:
                if len(click_key) == 1:
                    self.kbd.tap(click_key)
                else:
                    # Named key like f1, enter, space …
                    try:
                        self.kbd.tap(getattr(Key, click_key))
                    except AttributeError:
                        self.kbd.tap(click_key)
        except Exception as e:
            print(f"[Engine] action error: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Main application window
# ──────────────────────────────────────────────────────────────────────────────

class BestClick(ctk.CTk):

    def __init__(self) -> None:
        super().__init__()

        self.cfg    = Config()
        self.engine = Engine()
        self.engine.on_tick = lambda c: self.after(0, lambda: self._count_var.set(str(c)))
        self.engine.on_done = lambda: self.after(0, self._on_engine_done)

        self._capture_mode: bool = False
        self._capture_cb         = None
        self._kb_listener        = None
        self._state: str         = "stopped"

        self._setup_window()
        self._build_ui()
        self._start_kb_listener()

    # ── window setup ──────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.title(APP_NAME)
        self.geometry("470x720")
        self.minsize(460, 580)
        self.configure(fg_color="#0d1117")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - 470) // 2
        y  = (sh - 720) // 2
        self.geometry(f"470x720+{x}+{y}")

    # ── UI skeleton ───────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_header()
        self._build_nav()

        # thin divider
        ctk.CTkFrame(self, fg_color="#21262d", height=1, corner_radius=0).pack(fill="x")

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=14, pady=10)

        self._frames: dict = {}
        for name, builder in [("main", self._build_main), ("keys", self._build_keys)]:
            f = ctk.CTkFrame(self._content, fg_color="transparent")
            builder(f)
            self._frames[name] = f

        self._switch_tab("main")

    # ── header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=76)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        inner = ctk.CTkFrame(hdr, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18)

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="y", expand=True, pady=12)

        ctk.CTkLabel(
            left,
            text="⚡  BestClick",
            font=ctk.CTkFont("Segoe UI", 22, "bold"),
            text_color="#58a6ff",
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            left,
            text=SUBTITLE,
            font=ctk.CTkFont("Segoe UI", 10),
            text_color="#484f58",
            anchor="w",
        ).pack(anchor="w")

        badge = ctk.CTkFrame(inner, fg_color="#21262d", corner_radius=6)
        badge.pack(side="right", pady=22)
        ctk.CTkLabel(
            badge,
            text=f"v{VERSION}",
            font=ctk.CTkFont(size=10),
            text_color="#484f58",
        ).pack(padx=8, pady=3)

    # ── navigation ────────────────────────────────────────────────────────────

    def _build_nav(self) -> None:
        nav = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=42)
        nav.pack(fill="x")
        nav.pack_propagate(False)

        self._nav_btns: dict = {}
        for tab_id, label in [("main", "⚡  Main"), ("keys", "🔑  Keybinds")]:
            btn = ctk.CTkButton(
                nav,
                text=label,
                width=120, height=30,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="transparent",
                hover_color="#21262d",
                text_color="#8b949e",
                border_width=0,
                corner_radius=6,
                command=lambda tid=tab_id: self._switch_tab(tid),
            )
            btn.pack(side="left", padx=(8, 2), pady=6)
            self._nav_btns[tab_id] = btn

    def _switch_tab(self, tab_id: str) -> None:
        for f in self._frames.values():
            f.pack_forget()
        self._frames[tab_id].pack(fill="both", expand=True)
        for tid, btn in self._nav_btns.items():
            if tid == tab_id:
                btn.configure(fg_color="#58a6ff", text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color="#8b949e")

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _section(self, parent, title: str) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(14, 5))
        ctk.CTkLabel(
            row,
            text=title.upper(),
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#58a6ff",
        ).pack(side="left")
        ctk.CTkFrame(row, fg_color="#21262d", height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=5
        )

    def _card(self, parent, **kw) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent,
            fg_color="#161b22",
            corner_radius=10,
            border_width=1,
            border_color="#21262d",
            **kw,
        )

    # ── MAIN TAB ──────────────────────────────────────────────────────────────

    def _build_main(self, parent: ctk.CTkFrame) -> None:
        sf = ctk.CTkScrollableFrame(
            parent, fg_color="transparent",
            scrollbar_button_color="#21262d",
            scrollbar_button_hover_color="#30363d",
        )
        sf.pack(fill="both", expand=True)

        # ── Click Type ────────────────────────────────────────────────────────
        self._section(sf, "Click Type")
        type_card = self._card(sf)
        type_card.pack(fill="x")

        self._click_type = tk.StringVar(value="left")
        opts = [
            ("🖱  Left Click",   "left"),
            ("🖱  Right Click",  "right"),
            ("🖱  Middle Click", "middle"),
            ("🖱  Double Click", "double"),
            ("⌨   Key Press",   "key"),
        ]
        grid = ctk.CTkFrame(type_card, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=12)
        for i, (lbl, val) in enumerate(opts):
            ctk.CTkRadioButton(
                grid,
                text=lbl,
                variable=self._click_type,
                value=val,
                font=ctk.CTkFont(size=12),
                text_color="#c9d1d9",
                fg_color="#58a6ff",
                hover_color="#79b8ff",
                command=self._on_type_change,
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=8, pady=4)

        self._key_hint = ctk.CTkLabel(
            type_card, text="",
            font=ctk.CTkFont(size=10), text_color="#58a6ff",
        )
        self._key_hint.pack(padx=14, pady=(0, 8))
        self._on_type_change()

        # ── Interval ──────────────────────────────────────────────────────────
        self._section(sf, "Click Interval")
        int_card = self._card(sf)
        int_card.pack(fill="x")

        int_row = ctk.CTkFrame(int_card, fg_color="transparent")
        int_row.pack(fill="x", padx=14, pady=14)

        self._tvar: dict = {}
        for label, key, default in [
            ("Hours", "h", 0), ("Min", "m", 0), ("Sec", "s", 0), ("ms", "ms", 100)
        ]:
            col = ctk.CTkFrame(int_row, fg_color="transparent")
            col.pack(side="left", expand=True)
            v = tk.StringVar(value=str(default))
            self._tvar[key] = v
            ctk.CTkLabel(
                col, text=label,
                font=ctk.CTkFont(size=9), text_color="#8b949e",
            ).pack()
            entry = ctk.CTkEntry(
                col, textvariable=v,
                width=70, height=44,
                font=ctk.CTkFont(size=17, weight="bold"),
                justify="center",
                fg_color="#0d1117",
                border_color="#30363d",
                text_color="#e6edf3",
            )
            entry.pack()

        # ── Repeat ────────────────────────────────────────────────────────────
        self._section(sf, "Repeat")
        rep_card = self._card(sf)
        rep_card.pack(fill="x")

        rep_row = ctk.CTkFrame(rep_card, fg_color="transparent")
        rep_row.pack(fill="x", padx=14, pady=14)

        self._infinite = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            rep_row,
            text="Infinite",
            variable=self._infinite,
            font=ctk.CTkFont(size=12),
            text_color="#c9d1d9",
            fg_color="#58a6ff",
            hover_color="#79b8ff",
            command=self._on_infinite,
        ).pack(side="left", padx=(0, 14))

        self._rep_count_var = tk.StringVar(value="10")
        self._rep_count_frame = ctk.CTkFrame(rep_row, fg_color="transparent")
        ctk.CTkLabel(
            self._rep_count_frame,
            text="Times:",
            font=ctk.CTkFont(size=11),
            text_color="#8b949e",
        ).pack(side="left", padx=(0, 6))
        ctk.CTkEntry(
            self._rep_count_frame,
            textvariable=self._rep_count_var,
            width=80, height=34,
            font=ctk.CTkFont(size=14, weight="bold"),
            justify="center",
            fg_color="#0d1117",
            border_color="#30363d",
            text_color="#e6edf3",
        ).pack(side="left")
        self._on_infinite()   # apply initial visibility

        # ── Status ────────────────────────────────────────────────────────────
        self._section(sf, "Status")
        stat_card = self._card(sf)
        stat_card.pack(fill="x")

        stat_row = ctk.CTkFrame(stat_card, fg_color="transparent")
        stat_row.pack(fill="x", padx=16, pady=14)

        ind = ctk.CTkFrame(stat_row, fg_color="transparent")
        ind.pack(side="left", fill="y")
        self._stat_dot = ctk.CTkLabel(
            ind, text="●",
            font=ctk.CTkFont(size=20), text_color="#f85149",
        )
        self._stat_dot.pack(side="left", padx=(0, 8))
        self._stat_text = ctk.CTkLabel(
            ind, text="STOPPED",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#f85149",
        )
        self._stat_text.pack(side="left")

        # click counter badge
        counter = ctk.CTkFrame(stat_row, fg_color="#0d1117", corner_radius=8)
        counter.pack(side="right")
        ctk.CTkLabel(
            counter, text="CLICKS",
            font=ctk.CTkFont(size=8), text_color="#484f58",
        ).pack(padx=14, pady=(6, 0))
        self._count_var = tk.StringVar(value="0")
        ctk.CTkLabel(
            counter,
            textvariable=self._count_var,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#58a6ff",
        ).pack(padx=14, pady=(0, 6))

        # ── Controls ──────────────────────────────────────────────────────────
        self._section(sf, "Controls")
        btn_row = ctk.CTkFrame(sf, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 4))

        self._btn_start = ctk.CTkButton(
            btn_row, text="▶  START",
            height=48,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#238636", hover_color="#2ea043",
            text_color="white", corner_radius=10,
            command=self._do_start,
        )
        self._btn_start.pack(side="left", expand=True, padx=(0, 4))

        self._btn_pause = ctk.CTkButton(
            btn_row, text="⏸  PAUSE",
            height=48,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#9e6a03", hover_color="#bb8009",
            text_color="white", corner_radius=10,
            state="disabled",
            command=self._do_pause,
        )
        self._btn_pause.pack(side="left", expand=True, padx=4)

        self._btn_stop = ctk.CTkButton(
            btn_row, text="■  STOP",
            height=48,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#b62324", hover_color="#da3633",
            text_color="white", corner_radius=10,
            state="disabled",
            command=self._do_stop,
        )
        self._btn_stop.pack(side="left", expand=True, padx=(4, 0))

        # hotkey hint
        self._hint_lbl = ctk.CTkLabel(
            sf,
            text=self._hint_text(),
            font=ctk.CTkFont(size=10),
            text_color="#484f58",
        )
        self._hint_lbl.pack(pady=8)

    # ── KEYBINDS TAB ──────────────────────────────────────────────────────────

    def _build_keys(self, parent: ctk.CTkFrame) -> None:
        sf = ctk.CTkScrollableFrame(
            parent, fg_color="transparent",
            scrollbar_button_color="#21262d",
            scrollbar_button_hover_color="#30363d",
        )
        sf.pack(fill="both", expand=True)

        # info banner
        info = self._card(sf)
        info.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            info,
            text="Click a key badge → press any key to bind it.  Esc = cancel.",
            font=ctk.CTkFont(size=11),
            text_color="#8b949e",
            justify="left",
        ).pack(padx=14, pady=10, anchor="w")

        # ── App hotkeys ───────────────────────────────────────────────────────
        self._section(sf, "App Hotkeys")
        hk_card = self._card(sf)
        hk_card.pack(fill="x")

        self._key_btns: dict = {}
        for kid, label, desc in [
            ("start_key",  "▶  Start",          "Starts the auto clicker"),
            ("stop_key",   "■  Stop",            "Stops the auto clicker"),
            ("pause_key",  "⏸  Pause / Resume",  "Pauses or resumes clicking"),
        ]:
            self._build_key_row(hk_card, kid, label, desc)

        # ── Key press target ──────────────────────────────────────────────────
        self._section(sf, "Key Press Target")
        kp_card = self._card(sf)
        kp_card.pack(fill="x")
        ctk.CTkLabel(
            kp_card,
            text='Key that gets pressed each tick when "Key Press" mode is active:',
            font=ctk.CTkFont(size=11),
            text_color="#8b949e",
            wraplength=380,
            justify="left",
        ).pack(padx=14, pady=(10, 4), anchor="w")
        self._build_key_row(kp_card, "click_key", "⌨  Key to Press", "Pressed every interval tick")

        # buttons
        ctk.CTkButton(
            sf,
            text="💾  Save Keybinds",
            height=46,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#58a6ff", hover_color="#79b8ff",
            text_color="white", corner_radius=10,
            command=self._save_keys,
        ).pack(fill="x", pady=(14, 4))

        ctk.CTkButton(
            sf,
            text="↺  Reset to Defaults",
            height=36,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color="#21262d",
            text_color="#8b949e",
            border_width=1, border_color="#30363d",
            corner_radius=10,
            command=self._reset_keys,
        ).pack(fill="x", pady=(0, 8))

    def _build_key_row(self, parent, key_id: str, label: str, desc: str) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=7)

        txt = ctk.CTkFrame(row, fg_color="transparent")
        txt.pack(side="left", fill="y", expand=True)
        ctk.CTkLabel(
            txt, text=label,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#c9d1d9", anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            txt, text=desc,
            font=ctk.CTkFont(size=10),
            text_color="#484f58", anchor="w",
        ).pack(anchor="w")

        current = self.cfg.get(key_id, "?")
        btn = ctk.CTkButton(
            row,
            text=current.upper(),
            width=76, height=34,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0d1117",
            hover_color="#21262d",
            text_color="#58a6ff",
            border_width=1, border_color="#30363d",
            corner_radius=8,
            command=lambda k=key_id: self._start_capture(k),
        )
        btn.pack(side="right")
        self._key_btns[key_id] = btn

    # ── Main tab logic ────────────────────────────────────────────────────────

    def _on_type_change(self) -> None:
        if self._click_type.get() == "key":
            k = self.cfg.get("click_key", "k")
            self._key_hint.configure(
                text=f'Will press  [{k.upper()}]  — configure in Keybinds tab'
            )
        else:
            self._key_hint.configure(text="")

    def _on_infinite(self) -> None:
        if self._infinite.get():
            self._rep_count_frame.pack_forget()
        else:
            self._rep_count_frame.pack(side="left")

    def _interval_ms(self) -> int:
        try:
            h  = int(self._tvar["h"].get()  or 0)
            m  = int(self._tvar["m"].get()  or 0)
            s  = int(self._tvar["s"].get()  or 0)
            ms = int(self._tvar["ms"].get() or 0)
            return max(1, (h * 3600 + m * 60 + s) * 1000 + ms)
        except ValueError:
            return 100

    def _repeat_count(self) -> int:
        if self._infinite.get():
            return 0
        try:
            return max(1, int(self._rep_count_var.get() or 1))
        except ValueError:
            return 1

    def _do_start(self) -> None:
        self.engine.start(
            click_type=self._click_type.get(),
            interval_ms=self._interval_ms(),
            repeat_count=self._repeat_count(),
            click_key=self.cfg.get("click_key", "k"),
        )
        self._set_state("running")

    def _do_pause(self) -> None:
        paused = self.engine.toggle_pause()
        self._set_state("paused" if paused else "running")

    def _do_stop(self) -> None:
        self.engine.stop()
        self._set_state("stopped")

    def _on_engine_done(self) -> None:
        self._set_state("stopped")

    def _set_state(self, state: str) -> None:
        self._state = state
        CFGS = {
            "stopped": dict(
                dot_c="#f85149", txt="STOPPED",  txt_c="#f85149",
                start="normal",   pause="disabled", stop="disabled",
                ptxt="⏸  PAUSE",
            ),
            "running": dict(
                dot_c="#3fb950", txt="RUNNING",  txt_c="#3fb950",
                start="disabled", pause="normal",   stop="normal",
                ptxt="⏸  PAUSE",
            ),
            "paused": dict(
                dot_c="#d29922", txt="PAUSED",   txt_c="#d29922",
                start="disabled", pause="normal",   stop="normal",
                ptxt="▶  RESUME",
            ),
        }
        c = CFGS[state]
        self._stat_dot.configure(text_color=c["dot_c"])
        self._stat_text.configure(text=c["txt"], text_color=c["txt_c"])
        self._btn_start.configure(state=c["start"])
        self._btn_pause.configure(state=c["pause"], text=c["ptxt"])
        self._btn_stop.configure(state=c["stop"])
        if state == "stopped":
            self._count_var.set("0")

    def _hint_text(self) -> str:
        s  = self.cfg.get("start_key",  "f6").upper()
        st = self.cfg.get("stop_key",   "f7").upper()
        p  = self.cfg.get("pause_key",  "f8").upper()
        return f"{s} = Start  ·  {st} = Stop  ·  {p} = Pause"

    # ── Keybinds tab logic ────────────────────────────────────────────────────

    def _start_capture(self, key_id: str) -> None:
        btn = self._key_btns[key_id]
        btn.configure(
            text="…",
            fg_color="#58a6ff", text_color="white", border_color="#58a6ff",
        )
        self._capture_mode = True
        self._capture_cb   = lambda key: self._finish_capture(key_id, key)

    def _finish_capture(self, key_id: str, key) -> None:
        try:
            if hasattr(key, "char") and key.char and key.char.isprintable():
                name = key.char.lower()
            elif hasattr(key, "name"):
                name = key.name.lower()
            else:
                name = None
        except Exception:
            name = None

        btn = self._key_btns[key_id]
        if name and name != "escape":
            self.cfg.set(key_id, name)
            self.after(0, lambda: btn.configure(
                text=name.upper(),
                fg_color="#0d1117", text_color="#58a6ff", border_color="#30363d",
            ))
            if key_id == "click_key":
                self.after(0, self._on_type_change)
        else:
            prev = self.cfg.get(key_id, "?")
            self.after(0, lambda: btn.configure(
                text=prev.upper(),
                fg_color="#0d1117", text_color="#58a6ff", border_color="#30363d",
            ))

    def _save_keys(self) -> None:
        self.cfg.save()
        if hasattr(self, "_hint_lbl"):
            self._hint_lbl.configure(text=self._hint_text())
        self._on_type_change()
        self._toast("✓  Keybinds saved!")

    def _reset_keys(self) -> None:
        for k, v in DEFAULT_CONFIG.items():
            self.cfg.set(k, v)
            if k in self._key_btns:
                self._key_btns[k].configure(text=v.upper())
        self._save_keys()

    def _toast(self, msg: str) -> None:
        t = ctk.CTkToplevel(self)
        t.wm_overrideredirect(True)
        t.configure(fg_color="#238636")
        ctk.CTkLabel(
            t, text=msg,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white",
        ).pack(padx=16, pady=9)
        self.update_idletasks()
        cx = self.winfo_x() + (self.winfo_width() - 230) // 2
        cy = self.winfo_y() + self.winfo_height() - 60
        t.geometry(f"230x34+{cx}+{cy}")
        self.after(2000, t.destroy)

    # ── Global keyboard listener ──────────────────────────────────────────────

    def _start_kb_listener(self) -> None:
        threading.Thread(target=self._kb_thread, daemon=True).start()

    def _kb_thread(self) -> None:
        def on_press(key):
            # key-capture mode takes priority
            if self._capture_mode and self._capture_cb:
                cb = self._capture_cb
                self._capture_mode = False
                self._capture_cb   = None
                cb(key)
                return

            # global hotkeys
            try:
                if hasattr(key, "char") and key.char:
                    name = key.char.lower()
                elif hasattr(key, "name"):
                    name = key.name.lower()
                else:
                    return

                sk = self.cfg.get("start_key",  "f6")
                ek = self.cfg.get("stop_key",   "f7")
                pk = self.cfg.get("pause_key",  "f8")

                if name == sk and not self.engine.running:
                    self.after(0, self._do_start)
                    self.after(20, self._bring_front)
                elif name == ek and self.engine.running:
                    self.after(0, self._do_stop)
                    self.after(20, self._bring_front)
                elif name == pk and self.engine.running:
                    self.after(0, self._do_pause)
                    self.after(20, self._bring_front)
            except Exception:
                pass

        while True:
            try:
                with KeyboardListener(on_press=on_press) as lst:
                    self._kb_listener = lst
                    lst.join()
            except Exception:
                time.sleep(0.5)

    def _bring_front(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            if platform.system() == "Windows":
                import ctypes as ct
                hwnd = ct.windll.user32.FindWindowW(None, APP_NAME)
                if hwnd:
                    ct.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _on_close(self) -> None:
        self.engine.stop()
        if self._kb_listener:
            try:
                self._kb_listener.stop()
            except Exception:
                pass
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    BestClick().mainloop()
