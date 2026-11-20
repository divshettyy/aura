# 🎙️ Aura — Local Voice Assistant for Windows

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![Windows](https://img.shields.io/badge/platform-Windows-blue)](https://microsoft.com/windows)
[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-505%20passing-brightgreen)](tests/)
[![Last Commit](https://img.shields.io/github/last-commit/divshettyy/aura)](https://github.com/divshettyy/aura/commits)

> Wake word → offline STT → permission-gated actions → Claude brain.  
> No cloud. No subscription. No data leaves your machine.

---

## ✨ Features

| Feature | Detail |
|---------|--------|
| 🔊 Wake word | "Hey Jarvis" — configurable threshold, local detection |
| 🎤 Offline STT | Vosk — speech-to-text with no internet |
| ⚡ 44 built-in tools | Volume, brightness, apps, files, clipboard, calculator, timers, and more |
| 🔒 Permission gate | Every destructive action requires spoken confirmation |
| 🧠 Claude brain | Free-form requests answered by Claude via WSL |
| ⌨️ Hotkey | Ctrl+Alt+J for instant activation without wake word |
| 🚀 Fast | Built-in phrases: 1.5–1.8s · Claude responses: ~5.5s |

---

## 🏗️ Architecture

```
Microphone
  └── Wake word detector (local, Vosk keyword)
        └── Speech-to-text (Vosk — fully offline)
              ├── Built-in phrase matcher ──► response in 1.5s
              └── Claude brain (WSL) ──────► response in 5.5s
                    └── Action executor (permission-gated)
                          └── TTS output (Windows SAPI)
```

---

## 🚀 Quick Start

**Requirements:** Windows 10/11, Python 3.9+, [Vosk model](https://alphacephei.com/vosk/models)

```powershell
# 1. Clone and install
git clone https://github.com/divshettyy/aura
cd aura
.\install.ps1

# 2. Health check
aura doctor

# 3. Test a command (no mic needed)
aura once "what time is it"
aura once "set volume to 40"

# 4. Full voice mode
aura run
```

---

## 🛠️ 44 Built-in Tools

### System & Hardware
| Tool | What it does |
|------|-------------|
| `volume_set / volume_change` | Set or adjust speaker volume |
| `mute` | Toggle mute |
| `brightness_set / brightness_change` | Adjust screen brightness |
| `dark_mode` | Toggle Windows dark/light mode |
| `media` | Play, pause, next, previous |
| `lock_screen` | Lock the PC |
| `power` | Sleep, restart, shutdown |
| `screenshot` | Capture screen |
| `system_status` | CPU, RAM, disk, battery, uptime |

### Apps & Windows
| Tool | What it does |
|------|-------------|
| `open_app` | Launch any app by name |
| `close_app` | Close a running app |
| `list_apps` | List configured apps |
| `window` | Minimize, maximize, close focused window |
| `empty_recycle_bin` | Empty the recycle bin |

### Web & Browser
| Tool | What it does |
|------|-------------|
| `open_url` | Open any URL in default browser |
| `open_site` | Open a named site (google, github, …) |
| `search_site` | Search a site by name + query |
| `compose_email` | Open Gmail draft (never auto-sends) |
| `calendar_draft` | Pre-fill a Google Calendar event |

### Files & Clipboard
| Tool | What it does |
|------|-------------|
| `files_search` | Search within allowed folders |
| `clipboard_read` | Read clipboard content |
| `clipboard_write` | Write text to clipboard |
| `type_text` | Type text into the focused window |

### Time & Utility
| Tool | What it does |
|------|-------------|
| `get_time` | Current time and date |
| `date_info` | Weekday of a date, days until/since |
| `calculate` | Safe math expression evaluator |
| `stopwatch` | Start, stop, lap |
| `reminder_set` | Set a spoken reminder |
| `reminders_list` | List pending reminders |
| `reminder_cancel` | Cancel a reminder |

### Aura Controls
| Tool | What it does |
|------|-------------|
| `run_routine` | Run a named routine (sequence of commands) |
| `list_routines` | List available routines |
| `run_command` | Run a trusted saved command |
| `stop_listening` | Put Aura to sleep |
| `capabilities` | List all available tools |

---

## ⚙️ Configuration

Edit `%APPDATA%\Aura\config.yaml`:

```yaml
voice:
  wake_phrase: "hey jarvis"
  wake_threshold: 0.30      # lower = more sensitive
  language: en-us

brain:
  # Claude via WSL — runs locally, no cloud API
  claude_command: [wsl, -d, kali-linux, --, bash, -lic]

files:
  roots:
    - "%USERPROFILE%\\Documents"
    - "%USERPROFILE%\\Desktop"

apps:
  notepad: notepad.exe
  browser: msedge.exe
```

---

## 🔒 Privacy

- **No audio upload** — Vosk STT runs entirely on-device
- **No cloud dependency** — Claude brain runs in local WSL
- **No telemetry** — zero outbound connections from Aura itself
- **Permission gate** — file writes, app launches, power ops all require spoken confirmation

---

## 🧪 Tests

```powershell
%LOCALAPPDATA%\Aura\venv\Scripts\python.exe -m pytest -q tests/
# 505 passed, 1 skipped
```

Test suite includes 318+ phrase sentences with must-not-match cases to prevent over-triggering.

---

## 🤝 Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md). Ideas for new tools: file a [Feature Request](../../issues/new?template=feature_request.md).

---

## 📄 License

MIT © Divith Shetty
