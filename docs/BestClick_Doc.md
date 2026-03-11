# BestClick — Project Documentation

> **Version:** 1.1.0
> **Author:** @nummersechs
> **Language:** Python 3
> **Platform:** Windows (primary), macOS / Linux (partial support)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Features](#2-features)
3. [Architecture](#3-architecture)
4. [Class Reference](#4-class-reference)
   - 4.1 [Config](#41-config)
   - 4.2 [Engine](#42-engine)
   - 4.3 [BestClick (GUI)](#43-bestclick-gui)
5. [UI Layout](#5-ui-layout)
6. [Configuration System](#6-configuration-system)
7. [Theming System](#7-theming-system)
8. [Hotkey System](#8-hotkey-system)
9. [Dependencies](#9-dependencies)
10. [Build & Distribution](#10-build--distribution)
11. [File Structure](#11-file-structure)
12. [Known Limitations](#12-known-limitations)

---

## 1. Project Overview

**BestClick** is a desktop auto-clicker application with a modern, polished GUI. It allows users to automate repetitive mouse clicks or keyboard key presses at configurable intervals. The application supports global hotkeys, multiple click types, repeat limits, live status feedback, and persistent configuration — all packaged into a standalone Windows `.exe` via PyInstaller.

The entire application lives in a single Python file (`main.py`) for simplicity and ease of distribution. It is intentionally kept dependency-light: only two third-party packages are required (`customtkinter`, `pynput`).

---

## 2. Features

| Feature | Details |
|---|---|
| **Click Types** | Left click, Right click, Middle click, Double click, Key press |
| **Interval Control** | Hours / Minutes / Seconds / Milliseconds — all fields combinable |
| **Repeat Mode** | Infinite loop **or** fixed click count |
| **Global Hotkeys** | Start / Stop / Pause work even when the app window is in the background |
| **Live Status** | Color-coded status indicator (STOPPED / RUNNING / PAUSED) with click counter |
| **Settings Tab** | Rebind all hotkeys by pressing any key; configure key-press target key |
| **Theme** | Dark mode (green accents) and Light mode (blue accents) — persisted to disk |
| **Toast Notifications** | Transient on-screen confirmations when settings are saved |
| **Portable Config** | Settings saved as `config.json` next to the executable |
| **Standalone Exe** | Bundled via PyInstaller into a single `.exe` — no Python installation needed |

---

## 3. Architecture

```
┌───────────────────────────────────────────┐
│                BestClick (CTk)            │  ← Main window / GUI layer
│  ┌─────────────┐   ┌────────────────────┐ │
│  │  Main Tab   │   │   Settings Tab     │ │
│  │  (controls) │   │ (keys + theme)     │ │
│  └─────────────┘   └────────────────────┘ │
│                                           │
│  ┌──────────────────────────────────────┐ │
│  │  Engine (daemon thread)              │ │  ← Click loop, isolated from UI
│  │  on_tick(count) → after(0, …)       │ │
│  │  on_done()      → after(0, …)       │ │
│  └──────────────────────────────────────┘ │
│                                           │
│  ┌──────────────────────────────────────┐ │
│  │  Config                              │ │  ← JSON read/write, defaults
│  └──────────────────────────────────────┘ │
│                                           │
│  ┌──────────────────────────────────────┐ │
│  │  KB Listener (daemon thread)         │ │  ← pynput global hotkey capture
│  └──────────────────────────────────────┘ │
└───────────────────────────────────────────┘
```

### Threading Model

| Thread | Role |
|---|---|
| **Main thread** | Tkinter event loop — all UI updates must happen here |
| **Engine thread** | Daemon thread; performs click/key actions in a tight loop |
| **KB Listener thread** | Daemon thread; listens for global hotkeys via `pynput` |

Cross-thread UI calls are always routed through `self.after(0, callback)` to keep Tkinter thread-safe. Both background threads are marked `daemon=True` so they are automatically killed when the main process exits.

---

## 4. Class Reference

### 4.1 `Config`

**File:** `main.py:95`

Handles loading and saving user settings to `config.json`.

```
Config
├── __init__()          — loads from disk, falls back to DEFAULT_CONFIG
├── _load()             — reads config.json if it exists
├── save()              — writes current data to config.json (pretty-printed)
├── get(key, default)   — retrieves a config value
└── set(key, value)     — updates a config value in memory
```

**Default values:**

| Key | Default | Description |
|---|---|---|
| `start_key` | `f6` | Global hotkey to start clicking |
| `stop_key` | `f7` | Global hotkey to stop clicking |
| `pause_key` | `f8` | Global hotkey to pause/resume |
| `click_key` | `k` | Key pressed in "Key Press" mode |
| `theme` | `dark` | UI color theme (`dark` or `light`) |

**Config file location:** same directory as `main.py` / the `.exe` — `config.json`.

---

### 4.2 `Engine`

**File:** `main.py:126`

The click automation core. Runs entirely in a separate daemon thread.

```
Engine
├── start(click_type, interval_ms, repeat_count, click_key)
│       — spawns daemon thread, begins click loop
├── stop()              — signals loop to exit
├── toggle_pause()      — flips paused flag, returns new state
├── _loop(...)          — main loop: waits, acts, counts, checks limits
└── _act(click_type, click_key)
        — dispatches the actual mouse/keyboard action via pynput
```

**Supported `click_type` values:**

| Value | Action |
|---|---|
| `left` | Single left mouse button click |
| `right` | Single right mouse button click |
| `middle` | Single middle mouse button click |
| `double` | Double left mouse button click |
| `key` | Tap the configured `click_key` on the keyboard |

**Callbacks (set by GUI):**

| Attribute | Signature | When called |
|---|---|---|
| `on_tick` | `(count: int) → None` | After every successful action |
| `on_done` | `() → None` | When repeat limit is reached |

The GUI wires these callbacks to `self.after(0, ...)` calls to safely update the Tkinter UI from the engine thread.

---

### 4.3 `BestClick` (GUI)

**File:** `main.py:201`

Inherits from `customtkinter.CTk`. Manages the entire UI lifecycle.

#### Key Methods

| Method | Purpose |
|---|---|
| `_setup_window()` | Sets title, size, centers on screen, applies icon |
| `_build_ui()` | Top-level UI builder — header, nav bar, content frames |
| `_build_header()` | Renders app name, subtitle, version badge |
| `_build_nav()` | Renders tab navigation buttons (Main / Settings) |
| `_build_main(parent)` | Builds the Main tab: click type, interval, repeat, status, controls |
| `_build_keys(parent)` | Builds the Settings tab: keybindings, theme picker, save/reset |
| `_switch_tab(tab_id)` | Shows/hides content frames, updates nav button styles |
| `_switch_theme(name)` | Destroys and rebuilds all widgets with new color palette |
| `_set_state(state)` | Updates all UI elements for `stopped` / `running` / `paused` state |
| `_do_start()` | Reads UI values and calls `engine.start()` |
| `_do_pause()` | Calls `engine.toggle_pause()`, updates state |
| `_do_stop()` | Calls `engine.stop()`, resets state |
| `_start_capture(key_id)` | Enters key-capture mode for a specific binding |
| `_finish_capture(key_id, key)` | Processes captured key, updates config and button label |
| `_save_keys()` | Persists current config to disk, shows toast |
| `_reset_keys()` | Restores DEFAULT_CONFIG values for all hotkeys |
| `_toast(msg)` | Shows a temporary borderless popup at the bottom of the window |
| `_start_kb_listener()` | Launches the keyboard listener daemon thread |
| `_kb_thread()` | Listens for keypresses globally, routes to start/stop/pause or capture |
| `_bring_front()` | Brings window to foreground after a hotkey press (Windows only) |
| `_on_close()` | Graceful shutdown: stops engine, stops listener, destroys window |

#### Theme Rebuild Strategy

When the user switches themes, `_switch_theme()` calls `child.destroy()` on every widget and then calls `_build_ui()` fresh with the new color palette. The engine instance and its click counter survive this rebuild because they live on `self`, not inside any widget tree.

---

## 5. UI Layout

```
┌─────────────────────────────────────────────┐
│  ⚡ BestClick          [by @nummersechs]  v1.1.0 │  ← Header (74px)
├────────────────────────────────────────────┤
│  [⚡ Main]  [🔑 Settings]                  │  ← Nav bar (40px)
├────────────────────────────────────────────┤
│                                            │
│  CLICK TYPE                                │
│  ┌──────────────────────────────────────┐  │
│  │ ○ Left   ○ Right  ○ Middle          │  │
│  │ ○ Double ○ Key Press                │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  CLICK INTERVAL                            │
│  ┌──────────────────────────────────────┐  │
│  │  [Hours]  [Min]  [Sec]  [ms]        │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  REPEAT              STATUS               │
│  ┌───────────┐   ┌──────────────────────┐  │
│  │ ☑ Infinite│   │ ● STOPPED            │  │
│  │           │   │ CLICKS: 0            │  │
│  └───────────┘   └──────────────────────┘  │
│                                            │
│  CONTROLS                                  │
│  [▶ START]  [⏸ PAUSE]  [■ STOP]           │
│                                            │
│  F6 = Start  ·  F7 = Stop  ·  F8 = Pause  │
└────────────────────────────────────────────┘
```

Window dimensions: **470 × 720 px** (non-resizable).

---

## 6. Configuration System

Settings are stored in plain JSON at `config.json` in the application directory.

**Example `config.json`:**
```json
{
  "start_key": "f6",
  "stop_key": "f7",
  "pause_key": "f8",
  "click_key": "k",
  "theme": "dark"
}
```

- The file is created/updated on "Save Keybinds" or theme change.
- On first run, if the file does not exist, defaults are used in memory (file is not written until the user saves).
- Parse errors in `config.json` are silently ignored and defaults are applied.

**PyInstaller path resolution** — `_resource(name)` resolves file paths relative to `sys._MEIPASS` (the temp extraction directory of the bundled exe) so bundled assets (like `icon.ico`) are always found regardless of working directory.

---

## 7. Theming System

Two built-in themes are defined in the `THEMES` dict. Each theme maps semantic names to concrete color values.

| Token | Dark | Light | Usage |
|---|---|---|---|
| `app_bg` | `#0d1117` | `#ffffff` | Window background |
| `header_bg` | `#161b22` | `#f6f8fa` | Header / nav bar |
| `card_bg` | `#161b22` | `#f6f8fa` | Section card fill |
| `card_border` | `#21262d` | `#d0d7de` | Card border |
| `accent` | `#4ade80` | `#1f6feb` | Primary accent (green / blue) |
| `accent_hov` | `#86efac` | `#388bfd` | Accent hover state |
| `text` | `#c9d1d9` | `#1f2328` | Primary text |
| `text_dim` | `#8b949e` | `#656d76` | Secondary / label text |
| `text_faint` | `#484f58` | `#8c959f` | Hint / footer text |
| `entry_bg` | `#0d1117` | `#ffffff` | Input field background |
| `entry_border` | `#30363d` | `#d0d7de` | Input field border |

The selected theme is stored in `config.json` under the key `theme` and restored on next launch.

---

## 8. Hotkey System

Global hotkeys are captured by a `pynput.keyboard.Listener` running in a background daemon thread.

### Hotkey Flow

```
Key pressed (anywhere on system)
        │
        ▼
KB Listener thread (pynput)
        │
        ├─ Capture mode active?
        │       └─ YES → call _finish_capture(), exit capture mode
        │
        └─ NO → compare key name against start_key / stop_key / pause_key
                      │
                      ├─ match start_key  + engine not running → self.after(0, _do_start)
                      ├─ match stop_key   + engine running     → self.after(0, _do_stop)
                      └─ match pause_key  + engine running     → self.after(0, _do_pause)
```

- All hotkey triggers call `_bring_front()` after a 20 ms delay to raise the app window.
- The listener restarts automatically if it crashes (infinite loop with `time.sleep(0.5)` on exception).
- Capture mode (`_capture_mode = True`) temporarily hijacks the next keypress for key rebinding. `Esc` cancels capture without changing the binding.

---

## 9. Dependencies

| Package | Version | Purpose |
|---|---|---|
| `customtkinter` | ≥ 5.2.2 | Modern-looking Tkinter wrapper (rounded widgets, themes) |
| `pynput` | ≥ 1.7.7 | Global keyboard/mouse listener and mouse controller |

Standard library modules used: `threading`, `time`, `json`, `os`, `sys`, `platform`, `tkinter`, `ctypes`.

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## 10. Build & Distribution

The app is packaged into a single standalone `.exe` using **PyInstaller**.

### Build Command

```bash
pyinstaller BestClick.spec
```

The output is located at `dist/BestClick.exe`.

### `BestClick.spec` Highlights

| Setting | Value | Notes |
|---|---|---|
| Entry point | `main.py` | Single-file application |
| `datas` | `icon.ico`, `customtkinter` assets | Bundled into the exe |
| `console` | `False` | Windowless app — no terminal window |
| `upx` | `True` | Compression applied to reduce file size |
| `icon` | `icon.ico` | Custom taskbar / window icon |

### Windows App Identity

On Windows, the app calls `SetCurrentProcessExplicitAppUserModelID` at startup to assign a custom Application User Model ID (`BestClick.nummersechs.autoclicker`). This ensures the taskbar icon matches the custom `.ico` rather than a default Python icon.

The icon is applied via a raw Tcl call (`wm iconbitmap`) deferred with `self.after(0, ...)` to bypass `customtkinter`'s built-in icon override that would otherwise replace it with the CTk default icon.

---

## 11. File Structure

```
AutoClicker/
├── main.py               ← Entire application (Config + Engine + GUI)
├── icon.ico              ← Application icon (window + taskbar + exe)
├── BestClick.spec        ← PyInstaller build specification
├── requirements.txt      ← Python dependencies
├── config.json           ← User settings (auto-generated at runtime)
├── docs/
│   └── PROJECT_DOCUMENTATION.md   ← This file
└── .venv/                ← Virtual environment (not distributed)
```

---

## 12. Known Limitations

| Limitation | Detail |
|---|---|
| **Windows-focused** | `_bring_front()` and the App User Model ID are Windows-only. The app runs on macOS/Linux but window focus behavior may differ. |
| **Icon override** | The workaround for customtkinter's icon injection relies on a raw Tcl call, which could break if future versions of customtkinter change their internal behavior. |
| **No multi-monitor awareness** | The centering logic uses the primary screen dimensions; it may not center correctly on secondary monitors. |
| **Click position** | Clicks are sent to the current mouse cursor position. There is no built-in option to click at a fixed screen coordinate. |
| **Single profile** | Only one configuration profile is supported. There is no profile switching or preset system. |
| **No click randomization** | The interval is fixed. There is no jitter/randomization option to simulate more human-like behavior. |
