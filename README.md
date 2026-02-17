# 🤖 LLM Cursor Automation Tool

An intelligent background automation tool that captures your screen, analyzes it with a local LLM (via **LM Studio**), identifies interactive UI elements, and automatically moves & clicks the cursor on the correct option.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🖥️ Screen Capture | Automatically screenshots your display in the background |
| 🧠 LLM Analysis | Sends screenshots to LM Studio for intelligent UI element detection |
| 🎯 Auto-Cursor | Moves the mouse to the identified "best" element and clicks it |
| ⌨️ Hotkey Control | **Ctrl+M** to start, **Ctrl+;** to stop — works globally |
| 🔧 System Tray | Runs silently in the background with a tray icon (green = running, red = stopped) |
| 📦 EXE Build | Compile to a standalone `.exe` with one command |

---

## 📋 Prerequisites

1. **Python 3.10+** installed
2. **LM Studio** installed and running with:
   - A **vision-capable model** loaded (e.g., `gemma3:4b`)
   - Local server enabled at `http://localhost:1234`

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install openai pyautogui Pillow keyboard pystray pyinstaller
```

### 2. Start LM Studio

- Open LM Studio
- Load a vision model (e.g., **Gemma 3 4B**)
- Go to **Local Server** tab → click **Start Server**
- Verify it's running at `http://localhost:1234`

### 3. Run the Tool

```bash
python llm_cursor_tool.py
```

> ⚠️ **Run as Administrator** — The `keyboard` library requires admin privileges on Windows for global hotkey registration.

### 4. Use the Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl + M` | **Start** automation — begins screen capture → LLM analysis → cursor movement loop |
| `Ctrl + ;` | **Stop** automation — halts the loop immediately |

### 5. System Tray

Once running, a small icon appears in your system tray:
- 🟢 **Green** = Automation is active
- 🔴 **Red** = Automation is stopped
- **Right-click** the icon for Start / Stop / Quit options

---

## 📦 Build to EXE

To compile the tool into a standalone executable:

```bash
python build.py
```

The EXE will be generated at:
```
dist/LLM_Cursor_Tool.exe
```

The EXE runs without a console window and operates entirely from the system tray.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM Cursor Tool                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌────────────────┐    ┌────────────┐  │
│  │ HotkeyManager│───▶│AutomationEngine│───▶│  System     │  │
│  │              │    │                │    │  Tray Icon  │  │
│  │ Ctrl+M Start │    │  Main Loop:    │    │             │  │
│  │ Ctrl+; Stop  │    │  1. Capture    │    │ 🟢 Running  │  │
│  └──────────────┘    │  2. Analyze    │    │ 🔴 Stopped  │  │
│                      │  3. Move/Click │    └────────────┘  │
│                      └───────┬────────┘                     │
│                              │                              │
│                    ┌─────────┴─────────┐                    │
│                    ▼                   ▼                    │
│           ┌───────────────┐   ┌────────────────┐           │
│           │ScreenAnalyzer │   │CursorController│           │
│           │               │   │                │           │
│           │ Screenshot    │   │ Parse coords   │           │
│           │ → Base64      │   │ → Move mouse   │           │
│           │ → LM Studio   │   │ → Click        │           │
│           │ → Parse JSON  │   │                │           │
│           └───────────────┘   └────────────────┘           │
│                    │                                        │
│                    ▼                                        │
│           ┌───────────────┐                                 │
│           │  LM Studio    │                                 │
│           │  localhost:1234│                                 │
│           │  (Gemma 3 4B) │                                 │
│           └───────────────┘                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
📂 LLM Cursor Tool/
├── 📄 llm_cursor_tool.py    # Main application
├── 📄 build.py              # EXE compiler script
├── 📄 open.py               # Original screen monitor (legacy)
├── 📄 requiretmen.txt       # Dependencies & setup notes
└── 📄 README.md             # This documentation
```

---

## ⚙️ Configuration

You can adjust these constants at the top of `llm_cursor_tool.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LM_STUDIO_URL` | `http://localhost:1234/v1` | LM Studio API endpoint |
| `SCREENSHOT_MAX_SIZE` | `(1280, 1280)` | Max screenshot resolution sent to LLM |
| `SCREENSHOT_QUALITY` | `85` | JPEG quality for encoding (lower = faster) |
| `ANALYSIS_INTERVAL` | `3` | Seconds between each automation cycle |
| `CURSOR_MOVE_DURATION` | `0.4` | Seconds for smooth cursor movement animation |

---

## 🔄 How It Works (Cycle)

1. **Capture** — Takes a screenshot of the entire display
2. **Encode** — Resizes and converts the image to base64 JPEG
3. **Analyze** — Sends the image to LM Studio with a structured prompt asking the LLM to:
   - Describe what's on screen
   - List all interactive elements with pixel coordinates
   - Recommend the best element to click (with reasoning)
4. **Parse** — Extracts the JSON response (handles markdown fences, raw JSON, etc.)
5. **Execute** — Moves the cursor smoothly to the recommended coordinates and clicks
6. **Repeat** — Waits `ANALYSIS_INTERVAL` seconds, then loops back to step 1

### Example LLM Response

```json
{
  "screen_description": "A dialog box asking to save changes",
  "elements": [
    {"label": "Save", "x": 450, "y": 380, "type": "button"},
    {"label": "Don't Save", "x": 560, "y": 380, "type": "button"},
    {"label": "Cancel", "x": 670, "y": 380, "type": "button"}
  ],
  "recommended": {
    "label": "Save",
    "x": 450,
    "y": 380,
    "action": "click",
    "reason": "Save is the primary action to preserve changes"
  }
}
```

---

## 🛑 Troubleshooting

| Problem | Solution |
|---------|----------|
| Hotkeys not working | Run as Administrator |
| "Connection refused" error | Ensure LM Studio local server is running at port 1234 |
| LLM returns bad coordinates | Try a higher-quality vision model or increase `SCREENSHOT_MAX_SIZE` |
| Cursor moves to wrong spot | Adjust `SCREENSHOT_MAX_SIZE` to match your display resolution |
| Tool doesn't stop | Press `Ctrl+;` or right-click tray icon → Quit |

---

## 📜 License

This project is for personal/educational use.
"# stwich_run" 
