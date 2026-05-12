# D.O.B.B.Y — Desktop Operations Butler Built for You

**macOS voice + hand gesture AI assistant.**  
Control Claude Code with your voice. Navigate desktops with gestures. Hands-free, always-on.

> **macOS only** — Apple Silicon & Intel supported. Linux/Windows not supported.  
> 한국어 문서: [README_kr.md](README_kr.md)

![DOBBY HUD](dobby-connected.png)

---

## What is DOBBY?

DOBBY is a personal AI assistant that lives as a transparent always-on-top HUD overlay on your Mac. It combines:

- **Voice commands** — wake with "도비야", speak naturally, get spoken responses
- **Hand gesture control** — MediaPipe-powered gestures control your mouse, keyboard, and macOS Spaces
- **Claude integration** — Claude Haiku for instant responses, Claude Opus for deep research
- **Claude Code orchestration** — open projects, send prompts, manage tmux sessions by voice
- **macOS-native** — Calendar, Mail, Notes via AppleScript; Space switching via yabai; no OAuth

---

## Architecture

```
Motion HUD (Electron .app)
├── hud.html        — Three.js orb UI + MediaPipe hands + STT/TTS
├── src/main.ts     — BrowserWindow (always-on-top, all Spaces, transparent)
└── src/preload.ts  — contextBridge (electronAPI)
        │
        │  wss://localhost:8340/ws/voice   (voice conversation)
        │  wss://localhost:8340/ws/motion  (gesture events)
        ▼
FastAPI Backend (server.py · port 8340)
├── LLM  : Claude Haiku (voice responses) / Claude Opus (research)
├── TTS  : Qwen3 local → Fish Audio → macOS say (fallback chain)
├── STT  : faster-whisper (base, Korean, Silero VAD)
├── Actions: AppleScript · Claude Code CLI subprocess
└── Memory : SQLite + FTS5
        │
        │  [ACTION:OPEN_CLAUDE] → claude -c (interactive TUI)
        │  [ACTION:TYPE_TO_CLAUDE] → clipboard paste → Enter
        ▼
Terminal.app (per-project desktop)
└── claude -c --dangerously-skip-permissions
    (auto-resumes last session, interactive Claude Code TUI)
```

---

## Features

### Voice Interface
- **Wake word** — say "도비야" to activate (10-second listen window, auto-extends after responses)
- **Natural language commands** — any Korean phrase after the wake word
- **Barge-in** — interrupt Dobby mid-speech with a new command
- **TTS response** — spoken replies via Qwen3 (local) → Fish Audio → macOS `say` fallback
- **Type Mode** — gesture-activated voice-to-text that types directly into the focused app
- **STT** — 4-second chunks via faster-whisper with Silero VAD (filters silence/noise before transcription)

### Hand Gesture Control (Right Hand)
| Gesture | Action |
|---------|--------|
| Index finger pointing | Mouse cursor control |
| Dwell (hold still 400ms) | Left click |
| Dwell twice within 1s | Double click |
| Swipe left | Next macOS Space |
| Swipe right | Previous macOS Space |
| V-sign (✌️) hold | Activate Type Mode |
| Thumbs up (👍) | Deactivate Type Mode |
| Fist → open (spread) | Mission Control |

### Hand Gesture Control (Left Hand)
| Gesture | Action |
|---------|--------|
| Thumbs up (👍) | Enter |
| Thumbs down (👎) | Undo (Cmd+Z) |

### macOS Integration
- **Space switching** — yabai-based precise navigation (`yabai -m space --focus N`)
- **Project mapping** — `config/desktops.yaml` maps Space numbers to project directories
- **Claude Code sessions** — open, resume, and send prompts to per-project tmux sessions
- **Calendar** — read today's events and upcoming schedule
- **Mail** — read recent emails (read-only by design)
- **Notes** — read and write Apple Notes

### Memory
- Long-term memory stored in SQLite with full-text search (FTS5)
- Recalled automatically when relevant to the current conversation

---

## Requirements

- **macOS 12 Monterey or later** (AppleScript dependency)
- Python 3.11+
- Node.js 18+
- [Anthropic API key](https://console.anthropic.com/)
- [Claude Code CLI](https://claude.ai/code) — `npm install -g @anthropic-ai/claude-code`
- [yabai](https://github.com/koekeishiya/yabai) — for Space switching (`brew install koekeishiya/formulae/yabai`)

Optional:
- [Fish Audio API key](https://fish.audio/) — high-quality TTS (falls back to `say` if absent)
- Qwen3 TTS local server — fastest TTS (falls back to Fish Audio if absent)

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/ChangooLee/dobby.git
cd dobby

cp .env.example .env
# Fill in ANTHROPIC_API_KEY and optionally FISH_API_KEY
```

### 2. Python dependencies

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Motion HUD

```bash
cd motion-hud
npm install
npm run build      # TypeScript compile
npm run pack       # Build DOBBY.app (macOS arm64)
cd ..
```

### 4. SSL certificate (one-time)

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem \
  -days 365 -nodes -subj '/CN=localhost'
```

### 5. Configure desktops

```bash
cp config/desktops.example.json config/desktops.yaml
# Edit config/desktops.yaml — map Space numbers to your projects
```

### 6. Run

```bash
./start.sh   # starts TTS server + backend + HUD
./stop.sh    # stops everything
```

### Logs

```bash
tail -f /tmp/dobby_server.log   # backend
tail -f /tmp/hud.log            # Motion HUD
tail -f /tmp/qwen3_tts.log      # TTS server
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key (shared by server and Claude Code CLI) |
| `FISH_API_KEY` | — | Fish Audio TTS key |
| `FISH_VOICE_ID` | — | Fish Audio voice model ID |
| `QWEN3_TTS_URL` | — | Qwen3 local TTS server URL |
| `USER_NAME` | — | Your name (used in Dobby's address) |
| `SAY_VOICE` | — | macOS say fallback voice (default: `Yuna`) |
| `MOTION_CONTROL_ENABLED` | — | Enable gesture control on startup (`false`) |
| `CALENDAR_ACCOUNTS` | — | Calendar email addresses (comma-separated) |

---

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | FastAPI backend — WebSocket, LLM, action dispatch |
| `motion-hud/hud.html` | Entire HUD UI — Three.js orb + MediaPipe + voice |
| `motion-hud/src/main.ts` | Electron main process |
| `actions.py` | System actions (Terminal, Chrome, Claude Code) |
| `motion_actions.py` | Gesture → system action handlers |
| `memory.py` | SQLite long-term memory with FTS5 search |
| `desktop_manager.py` | macOS Space switching and project tracking |
| `calendar_access.py` | Apple Calendar via AppleScript |
| `mail_access.py` | Apple Mail (read-only) |
| `notes_access.py` | Apple Notes (read/write) |
| `work_mode.py` | Claude Code headless session management |
| `dispatch_registry.py` | Action tag → handler routing |
| `config/desktops.yaml` | Space number ↔ project directory mapping |
| `RUNBOOK.md` | Start / restart / stop procedures |

---

## Action Tags

The LLM embeds action tags in responses to trigger system behaviors:

### Claude Code
| Tag | Behavior |
|-----|----------|
| `[ACTION:OPEN_CLAUDE] name \| mode` | Open Claude Code session in iTerm2 (`new` / `here`) |
| `[ACTION:TYPE_TO_CLAUDE] name \|\|\| msg` | Type prompt into active Claude Code session |
| `[ACTION:PROMPT_PROJECT] name \|\|\| prompt` | Run Claude Code headlessly; voice the result |
| `[ACTION:OPEN_TERMINAL]` | Open a fresh Claude Code terminal |
| `[ACTION:SETUP_DESKTOPS]` | Visit all Spaces, open Claude Code in each |

### Session Management
| Tag | Behavior |
|-----|----------|
| `[ACTION:SESSION_OPEN]` | Open a named Claude Code session |
| `[ACTION:SESSION_SEND]` | Send a prompt to a specific session |
| `[ACTION:SESSION_BROADCAST]` | Broadcast a prompt to all sessions |
| `[ACTION:SESSION_AGGREGATE]` | Aggregate output from all sessions |
| `[ACTION:SESSION_LIST]` | List active sessions |
| `[ACTION:SESSION_CLOSE]` | Close a session |

### Desktop & HUD
| Tag | Behavior |
|-----|----------|
| `[ACTION:DESKTOP_GOTO] target` | Jump to Space number or project name |
| `[ACTION:HUD_SHOW]` | Show Motion HUD window |
| `[ACTION:HUD_HIDE]` | Hide Motion HUD window |
| `[ACTION:LAUNCH_HUD]` | Launch Motion HUD (no-op if already running) |

### Motion Control
| Tag | Behavior |
|-----|----------|
| `[ACTION:MOTION_ENABLE]` | Enable gesture control (camera on) |
| `[ACTION:MOTION_DISABLE]` | Disable gesture control |
| `[ACTION:MOTION_PAUSE]` | Pause gesture recognition (camera stays on) |
| `[ACTION:MOTION_RESUME]` | Resume after pause |
| `[ACTION:MOTION_CALIBRATE]` | Recalibrate mouse pointer mapping |

### Browsing & Research
| Tag | Behavior |
|-----|----------|
| `[ACTION:BUILD] description` | Create new project + open Claude Code |
| `[ACTION:BROWSE] url or query` | Open URL or search in Chrome |
| `[ACTION:RESEARCH] brief` | Deep research via Claude Opus |
| `[ACTION:SCREEN]` | Capture and describe what's on screen |

### Memory & Notes
| Tag | Behavior |
|-----|----------|
| `[ACTION:REMEMBER] content` | Persist fact to long-term memory |
| `[ACTION:ADD_TASK] priority \|\|\| title \|\|\| desc \|\|\| date` | Add task to tracker |
| `[ACTION:COMPLETE_TASK] task_id` | Mark task as done |
| `[ACTION:ADD_NOTE] topic \|\|\| content` | Save note to memory store |
| `[ACTION:CREATE_NOTE] title \|\|\| body` | Create Apple Note |
| `[ACTION:READ_NOTE] title search` | Read Apple Note by title keyword |

---

## Roadmap

### In Progress
- [ ] Stabilize VAD thresholds for reliable short-utterance detection
- [ ] Improve echo cancellation to eliminate TTS feedback loop

### Planned
- [ ] **Offline wake word** — replace Whisper-based chunked detection with a dedicated lightweight model (e.g. openWakeWord, Silero) for sub-100ms latency
- [ ] **Streaming STT** — real-time partial transcription to reduce perceived response delay
- [ ] **Screen context** — periodic screenshot → multimodal Claude prompt so Dobby can "see" what's on screen
- [ ] **Plugin system** — declarative action definitions loadable without modifying `server.py`
- [ ] **Web search** — integrate Brave Search / Perplexity for live information
- [ ] **Home automation** — HomeKit / Home Assistant integration via voice
- [ ] **Multi-language** — English wake word and response support
- [ ] **Gesture customization** — user-editable gesture bindings via config file
- [ ] **DMG installer** — signed and notarized macOS distribution package
- [ ] **Conversation history UI** — scrollable transcript panel in the HUD

---

## Known Limitations

- **macOS only** — AppleScript and yabai are macOS-specific; no Linux/Windows port planned
- **Camera / microphone permissions** — must be granted to `DOBBY.app` in System Settings on first launch
- **MediaPipe CDN** — hand tracking loads WASM from jsDelivr CDN; offline environments need local hosting
- **Whisper latency** — STT processing takes ~300–800ms per 4-second chunk; not real-time
- **yabai + SIP** — creating new Spaces programmatically requires partial SIP disable; pre-creating Spaces in Mission Control is the simpler workaround
- **TTS voice selection** — Fish Audio voice quality varies; `say` fallback is English-accented Korean

---

## License

MIT — see [LICENSE](LICENSE)

---

Powered by [Anthropic Claude](https://anthropic.com) · [MediaPipe](https://mediapipe.dev) · [Three.js](https://threejs.org) · [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
