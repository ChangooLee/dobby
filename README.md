# D.O.B.B.Y — Desktop Operations Butler Built for You

macOS 전용 음성 + 손동작 AI 비서.
음성으로 Claude Code를 제어하고, 손동작으로 macOS 데스크톱을 이동합니다.

> **macOS 전용** — Apple Silicon / Intel Mac 모두 지원. Linux/Windows 미지원.

## 빠른 시작

### 최초 설치

```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY 등 입력

# 2. Python 의존성
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Motion HUD 빌드
cd motion-hud && npm install && npm run build && cd ..

# 4. SSL 인증서 생성 (최초 1회)
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=localhost'
```

### 실행 / 종료

```bash
./start.sh   # 전체 시작 (TTS 서버 + 백엔드 + HUD)
./stop.sh    # 전체 종료
```

### 로그 확인

```bash
tail -f /tmp/dobby_server.log   # 백엔드
tail -f /tmp/hud.log            # Motion HUD
tail -f /tmp/qwen3_tts.log      # TTS 서버
```

> 자세한 내용은 **[RUNBOOK.md](RUNBOOK.md)** 참고

## 아키텍처

```
Motion HUD (Electron)
├── hud.html     — JARVIS-like UI, Three.js AI Core, MediaPipe 손동작, 음성 인식/재생
├── src/main.ts  — BrowserWindow (항상 맨 위, 모든 Space에 표시, 투명)
└── src/preload.ts
        │
        │  wss://localhost:8340/ws/voice  (음성 대화)
        │  wss://localhost:8340/ws/motion (손동작 이벤트)
        ▼
FastAPI 백엔드 (server.py, port 8340)
├── LLM: Claude Haiku (음성 응답) / Claude Opus (리서치)
├── TTS: Qwen3 로컬 → macOS say 폴백
├── STT: faster-whisper (base, ko)
└── Memory: SQLite + FTS5
```

| 레이어 | 기술 |
|--------|------|
| HUD (UI 전체) | Electron + Three.js + MediaPipe Hands |
| 백엔드 | FastAPI + Python (`server.py`) |
| 통신 | WebSocket (`/ws/voice`, `/ws/motion`) |
| AI (빠른 응답) | Claude Haiku |
| AI (리서치·복잡한 태스크) | Claude Opus |
| TTS | Qwen3 (로컬) → macOS say 폴백 |
| STT | faster-whisper |
| macOS 연동 | AppleScript (OAuth 불필요) |
| 메모리 | SQLite + FTS5 |

## HUD 화면 구성

- **중앙**: Three.js AI Core Orb — 상태에 따라 색상/크기 변동
- **좌측 패널**: WORKSPACE(현재 데스크톱/프로젝트) + STATUS + SCHEDULE
- **우측 패널**: MOTION + GESTURE + ACTION + SYSTEM
- **손동작 오버레이**: MediaPipe 랜드마크 + Cat's Cradle 연결선

## 손동작

| 제스처 | 동작 |
|--------|------|
| ← 왼쪽 스와이프 | 다음 macOS Space |
| → 오른쪽 스와이프 | 이전 macOS Space |

D 키 → Debug Overlay | Esc → 모션 일시정지

→ 자세한 내용: [docs/MOTION_CONTROL.md](docs/MOTION_CONTROL.md)

## Claude Code 연동

```
"도비야, [프로젝트명] 클로드 코드 열어줘"
→ Terminal.app에서 해당 프로젝트 경로로 claude 실행
```

`CLAUDE_BIN` 환경 변수로 실행 파일 경로를 직접 지정할 수 있습니다:
```
CLAUDE_BIN=/opt/homebrew/bin/claude
```

확인: `curl -sk https://localhost:8340/api/claude/status`

## 액션 태그

LLM 응답에 삽입되어 시스템 동작을 트리거합니다:

| 태그 | 동작 |
|------|------|
| `[ACTION:BUILD]` | Claude Code로 프로젝트 생성 |
| `[ACTION:BROWSE]` | Chrome으로 URL/검색 열기 |
| `[ACTION:RESEARCH]` | Claude Opus 심층 리서치 |
| `[ACTION:OPEN_CLAUDE]` | 프로젝트 디렉토리에서 Claude Code 실행 |
| `[ACTION:TYPE_TO_CLAUDE]` | 열린 Claude Code 창에 명령 입력 |
| `[ACTION:ADD_TASK]` | 태스크 추가 |
| `[ACTION:REMEMBER]` | 장기 메모리에 저장 |

## 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API 키 |
| `QWEN3_TTS_URL` | — | Qwen3 TTS 서버 URL |
| `QWEN3_TTS_KEY` | — | Qwen3 TTS API 키 |
| `CLAUDE_BIN` | — | claude 실행 파일 경로 (자동 탐색) |
| `DESKTOP_SWITCH_METHOD` | — | auto\|applescript\|pyautogui |
| `MOTION_CONTROL_ENABLED` | — | 시작 시 모션 활성화 여부 |
| `SAY_VOICE` | — | macOS say 폴백 음성 (기본: Yuna) |
| `USER_NAME` | — | 사용자 이름 |

## 주요 파일

| 파일 | 역할 |
|------|------|
| `server.py` | FastAPI 백엔드 — WebSocket, LLM, 액션 시스템 |
| `motion-hud/hud.html` | Electron HUD 전체 UI (Three.js 오브 + 손동작 + 음성) |
| `motion-hud/src/main.ts` | Electron 메인 프로세스 |
| `actions.py` | 시스템 액션 (Terminal, Chrome, Claude Code) |
| `memory.py` | SQLite 기반 장기 메모리 (FTS5 검색) |
| `calendar_access.py` | Apple Calendar 연동 (AppleScript) |
| `mail_access.py` | Apple Mail 연동 (읽기 전용) |
| `notes_access.py` | Apple Notes 연동 |
| `work_mode.py` | Claude Code 세션 관리 |
| `desktop_manager.py` | macOS Space 전환 관리 |
| `config/desktops.yaml` | 데스크톱 ↔ 프로젝트 매핑 |
| `RUNBOOK.md` | 실행·재시작·종료 절차 |

## 재시작 절차

→ [RUNBOOK.md](RUNBOOK.md) 참고

## 문제 해결

→ [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## 포트 및 로그

| 컴포넌트 | 포트 | 로그 |
|----------|------|------|
| FastAPI 백엔드 | 8340 | `/tmp/dobby_server.log` |
| Motion HUD (Electron) | — | `/tmp/hud.log` |
| Qwen3 TTS 서버 | 8000 | `/tmp/qwen_tts.log` |

## 요구사항

- **macOS 12 Monterey 이상** (AppleScript 의존)
- Python 3.11+
- Node.js 18+
- Anthropic API 키 ([발급](https://console.anthropic.com/))

> Google Chrome / 별도 브라우저는 필요 없습니다. 모든 UI는 Electron HUD가 담당합니다.

## 라이선스

개인 비상업적 사용에 한해 무료. 상업적 사용은 별도 문의. [LICENSE](LICENSE) 참조.

---

Powered by [Anthropic Claude](https://anthropic.com) · [MediaPipe](https://mediapipe.dev) · [Three.js](https://threejs.org)
