# Tally Counter

A lightweight Windows system tray app that monitors how many instances of a chosen executable are running, samples every minute, and shows a calendar heatmap of daily maximum counts.

## Features

- **System tray** — runs silently in the background; single-click to open the dashboard
- **Instance counting** — correctly handles multi-process apps (e.g. Chrome) by counting only top-level parent processes
- **Calendar heatmap** — green gradient showing daily peak instance counts for the current month; click any cell for details
- **Live stat cards** — current instance count, today's max, system time, CPU usage, RAM usage
- **Persistent storage** — SQLite database records daily maximums across sessions
- **Portable** — can be packaged as a single `.exe` with no Python installation required on the target machine

## Requirements

- Windows 10/11
- Python 3.8+

## Setup

```bash
# 1. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python src/main.py
```

On first launch a configuration window will appear — browse to the `.exe` you want to monitor and click Save.

## Building a standalone .exe

```bash
.venv\Scripts\python.exe -m PyInstaller TallyCounter.spec
```

The output is at `dist\TallyCounter.exe`. Copy it to any Windows machine — no Python required.

> **Custom icon:** place `icon.ico` (or `icon.png`) in the `src/` directory before building to embed a custom tray/window icon.

## Project Structure

```
TallyCounter/
├── src/
│   ├── main.py             # App entry point — tray icon, window management
│   ├── monitor.py          # Background process monitoring (QThread)
│   ├── database.py         # SQLite persistence (config + daily counts)
│   ├── dashboard_window.py # Main dashboard UI (stat cards + heatmap)
│   ├── heatmap_widget.py   # Calendar heatmap widget
│   └── config_window.py    # First-run executable selection
├── testapp.py              # Dummy process for testing instance counting
├── TallyCounter.spec       # PyInstaller build spec
├── requirements.txt
└── .gitignore
```

## Tech Stack

| Library | Purpose |
|---------|---------|
| PyQt6 | UI framework, system tray, threading |
| psutil | Process enumeration, CPU/RAM stats |
| pywin32 | Windows process API (parent-process detection) |
| sqlite3 | Built-in — persistent storage |
| PyInstaller | Single-file .exe packaging |

## How Instance Counting Works

The monitor counts **top-level process instances** — processes whose parent is not the same executable. This means:

- **Chrome / Electron apps**: only the main browser process is counted; renderer, GPU, and extension helper subprocesses are excluded
- **python.exe / tally.exe**: every independently launched instance is counted correctly
