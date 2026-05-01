# D.O.B.B.Y — Desktop Operations Butler Built for You

macOS 전용 음성 + 손동작 AI 비서.  
음성으로 Claude Code를 제어하고, 손동작으로 macOS 데스크톱을 이동합니다.

> **macOS 전용** — Apple Silicon / Intel Mac 모두 지원. Linux/Windows 미지원.

---

## 필수 요건

DOBBY가 동작하려면 **두 가지**가 모두 필요합니다.

### 1. Anthropic API 키

DOBBY 서버(FastAPI)가 Claude API를 직접 호출합니다.

- 발급: [console.anthropic.com](https://console.anthropic.com)
- `.env` 파일에 설정: `ANTHROPIC_API_KEY=sk-ant-...`

### 2. Claude Code CLI (이 맥북에 설치 + 로그인)

프로젝트 코드 분석·수정·개발 작업은 **Claude Code CLI**(`claude` 명령어)가 실행합니다.  
DOBBY 서버가 아니라, Terminal.app에서 직접 `claude`가 실행됩니다.

```bash
# 설치
npm install -g @anthropic-ai/claude-code

# 로그인 (1회)
claude login
# 또는 ANTHROPIC_API_KEY 환경 변수가 있으면 자동 인증
```

**API 키 하나로 둘 다 해결 가능:**  
`ANTHROPIC_API_KEY`가 `.env`에 있으면 DOBBY 서버와 Claude Code CLI 모두 이 키를 사용합니다.  
별도 `claude login` 불필요.

### 선택 사항

| 항목 | 용도 |
|------|------|
| Fish Audio API 키 | 고품질 TTS (없으면 macOS `say` 폴백) |
| Qwen3 TTS 로컬 서버 | 더 빠른 TTS (없으면 Fish Audio → say 폴백) |

---

## Claude Code 연동 방식

DOBBY가 Claude Code를 제어하는 방식:

```
사용자 음성: "agent-portal 열어줘"
    ↓
DOBBY → desktops.yaml에서 agent-portal의 Space 번호 조회
       → yabai로 해당 Space로 정확히 이동
       → tmux 세션(dobby_agent_portal) 생성/재개
       → iTerm2 창을 해당 Space에서 열어 tmux attach
       → claude -c --dangerously-skip-permissions 자동 실행

사용자 음성: "API 엔드포인트 추가해줘"
    ↓
DOBBY → tmux send-keys로 해당 세션에 프롬프트 직접 입력
       → tmux capture-pane으로 Claude Code 응답 캡처
       → Haiku로 요약 후 TTS 음성 출력

사용자 음성: "전체 프로젝트 설정해줘"
    ↓
DOBBY → desktops.yaml 순서대로 각 Space 방문
       → 각 프로젝트에 Claude Code tmux 세션 생성

사용자 음성: "지금 어디에 뭐 떠있어?"
    ↓
DOBBY → yabai + tmux 상태 결합 조회
       → "Space 2(agent-portal) Claude Code 실행 중,
          Space 5(mcp-kr-legislation) Claude Code 실행 중,
          Space 4(sourceport) 비어있음" 음성 보고
```

**핵심**: 실제 코드 작업은 DOBBY 서버가 아니라 Terminal의 `claude` CLI가 수행합니다.  
DOBBY는 어떤 터미널 창에 무엇을 입력할지 오케스트레이션합니다.

### claude -c 사용 이유 (--resume 대신)

- `claude --resume` : 세션 ID 선택 화면이 뜨는 인터랙티브 picker → 자동화 불가
- `claude -c` (`--continue`) : 해당 디렉토리의 마지막 세션을 자동으로 재개 → DOBBY에 적합

### 배경 작업 (PROMPT_PROJECT)

"agent-portal 리서치해줘"처럼 결과를 DOBBY가 직접 요약해야 할 때는  
`claude -p --continue` (헤드리스 print mode)를 별도로 실행해 결과를 캡처합니다.  
이때는 터미널 창이 보이지 않으며, 완료 시 DOBBY가 음성으로 요약을 보고합니다.

---

## macOS Space(데스크톱) 관리

DOBBY는 **yabai**를 통해 macOS Space를 제어합니다.

### Space 전환 방식

`yabai -m space --focus N` 명령으로 현재 위치에 관계없이 항상 정확한 Space로 이동합니다.  
기존의 `Ctrl+→` 키 반복 방식은 사용자가 수동으로 Space를 바꾸면 카운터가 틀어지는 문제가 있어 폐기했습니다.

### Space 자동 배정

`config/desktops.yaml`에 등록된 프로젝트는 고정 Space를 사용합니다.  
등록되지 않은 프로젝트를 열 때는 DOBBY가 빈 Space를 자동으로 찾아 배정합니다.

### Space 생성 제약 (중요)

**macOS SIP(시스템 무결성 보호)가 활성화된 상태에서는 프로그램적으로 새 Space를 생성할 수 없습니다.**

yabai의 Space 생성(`yabai -m space --create`)은 scripting-addition이 필요하며,  
scripting-addition 로드에는 SIP 부분 비활성화가 필요합니다.

**권장 설정 (방법 1): Mission Control에서 Space를 미리 생성**

프로젝트 수보다 여유있게 Space를 미리 만들어두면 DOBBY가 빈 Space를 자동으로 활용합니다.

```
Mission Control(F3) → 화면 상단 Space 바 → "+" 버튼으로 Space 추가
```

예: 프로젝트 5개 → Space를 7~10개 미리 생성해두기

**선택 설정 (방법 2): SIP 부분 비활성화**

SIP를 부분 비활성화하면 yabai가 필요할 때 자동으로 Space를 생성합니다.

```bash
# 1. Mac 전원 끄기 → 전원 버튼 길게 눌러 복구 모드 진입
# 2. 터미널에서:
csrutil enable --without debug --without fs
# 3. 재부팅 후:

# sudoers 등록 (1회)
echo "$(whoami) ALL=(root) NOPASSWD: sha256:$(shasum -a 256 $(which yabai) | cut -d ' ' -f 1) $(which yabai) --load-sa" \
  | sudo tee /private/etc/sudoers.d/yabai

# yabai config 생성
mkdir -p ~/.config/yabai
cat > ~/.config/yabai/yabairc << 'EOF'
sudo yabai --load-sa
yabai -m signal --add event=dock_did_restart action="sudo yabai --load-sa"
EOF
chmod +x ~/.config/yabai/yabairc
```

방법 2 적용 후에는 `assign_space()`에서 `yabai -m space --create`가 정상 작동합니다.

---

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

---

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
├── TTS: Qwen3 로컬 → Fish Audio → macOS say 폴백
├── STT: faster-whisper (base, ko)
├── Actions: AppleScript, Claude Code CLI 제어
└── Memory: SQLite + FTS5
        │
        │  [ACTION:OPEN_CLAUDE] → claude -c (인터랙티브 TUI)
        │  [ACTION:TYPE_TO_CLAUDE] → 클립보드 붙여넣기 → Enter
        ▼
Terminal.app (각 프로젝트 데스크톱)
└── claude -c --dangerously-skip-permissions
    ← 마지막 세션 자동 재개, 인터랙티브 Claude Code TUI
```

| 레이어 | 기술 |
|--------|------|
| HUD (UI 전체) | Electron + Three.js + MediaPipe Hands |
| 백엔드 | FastAPI + Python (`server.py`) |
| 통신 | WebSocket (`/ws/voice`, `/ws/motion`) |
| AI (빠른 응답) | Claude Haiku |
| AI (리서치·복잡한 태스크) | Claude Opus |
| TTS | Qwen3 (로컬) → Fish Audio → macOS say 폴백 |
| STT | faster-whisper |
| macOS 연동 | AppleScript (OAuth 불필요) |
| 코드 작업 | Claude Code CLI (`claude -c`) |
| 메모리 | SQLite + FTS5 |

---

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

---

## 액션 태그

LLM 응답에 삽입되어 시스템 동작을 트리거합니다:

| 태그 | 동작 |
|------|------|
| `[ACTION:BUILD]` | 새 프로젝트 생성 + Claude Code 실행 |
| `[ACTION:BROWSE]` | Chrome으로 URL/검색 열기 |
| `[ACTION:RESEARCH]` | Claude Opus 심층 리서치 |
| `[ACTION:OPEN_CLAUDE]` | 프로젝트 데스크톱으로 이동 + `claude -c` 실행 |
| `[ACTION:TYPE_TO_CLAUDE]` | 열린 Claude Code 창에 프롬프트 직접 입력 |
| `[ACTION:SETUP_DESKTOPS]` | 모든 데스크톱 순회, 각 프로젝트에 Claude Code 열기 |
| `[ACTION:ADD_TASK]` | 태스크 추가 |
| `[ACTION:REMEMBER]` | 장기 메모리에 저장 |

---

## 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API 키 (서버 + Claude Code CLI 공용) |
| `FISH_API_KEY` | — | Fish Audio TTS API 키 |
| `FISH_VOICE_ID` | — | Fish Audio 음성 모델 ID |
| `QWEN3_TTS_URL` | — | Qwen3 TTS 서버 URL |
| `QWEN3_TTS_KEY` | — | Qwen3 TTS API 키 |
| `CLAUDE_BIN` | — | claude 실행 파일 경로 (자동 탐색) |
| `DESKTOP_SWITCH_METHOD` | — | `auto`\|`applescript`\|`pyautogui` |
| `MOTION_CONTROL_ENABLED` | — | 시작 시 모션 활성화 여부 |
| `SAY_VOICE` | — | macOS say 폴백 음성 (기본: Yuna) |
| `USER_NAME` | — | 사용자 이름 |

---

## 주요 파일

| 파일 | 역할 |
|------|------|
| `server.py` | FastAPI 백엔드 — WebSocket, LLM, 액션 시스템 |
| `motion-hud/hud.html` | Electron HUD 전체 UI (Three.js 오브 + 손동작 + 음성) |
| `motion-hud/src/main.ts` | Electron 메인 프로세스 |
| `actions.py` | 시스템 액션 (Terminal, Chrome, Claude Code) |
| `bridge_session.py` | PROMPT_PROJECT용 헤드리스 Claude Code 출력 캡처 |
| `terminal_bridge.sh` | 헤드리스 모드에서 `claude -p` 실행·캡처 브리지 |
| `memory.py` | SQLite 기반 장기 메모리 (FTS5 검색) |
| `calendar_access.py` | Apple Calendar 연동 (AppleScript) |
| `mail_access.py` | Apple Mail 연동 (읽기 전용) |
| `notes_access.py` | Apple Notes 연동 |
| `work_mode.py` | Claude Code 헤드리스 세션 관리 |
| `project_sessions.py` | 프로젝트별 세션 풀 |
| `desktop_manager.py` | macOS Space 전환 관리 |
| `config/desktops.yaml` | 데스크톱 ↔ 프로젝트 매핑 |
| `RUNBOOK.md` | 실행·재시작·종료 절차 |

---

## 재시작 절차

→ [RUNBOOK.md](RUNBOOK.md) 참고

## 문제 해결

→ [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## 포트 및 로그

| 컴포넌트 | 포트 | 로그 |
|----------|------|------|
| FastAPI 백엔드 | 8340 | `/tmp/dobby_server.log` |
| Motion HUD (Electron) | — | `/tmp/hud.log` |
| Qwen3 TTS 서버 | 8000 | `/tmp/qwen_tts.log` |

---

## 요구사항

- **macOS 12 Monterey 이상** (AppleScript 의존)
- Python 3.11+
- Node.js 18+
- Anthropic API 키 ([발급](https://console.anthropic.com/))
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)

> Google Chrome / 별도 브라우저는 필요 없습니다. 모든 UI는 Electron HUD가 담당합니다.

---

## 라이선스

개인 비상업적 사용에 한해 무료. 상업적 사용은 별도 문의. [LICENSE](LICENSE) 참조.

---

Powered by [Anthropic Claude](https://anthropic.com) · [MediaPipe](https://mediapipe.dev) · [Three.js](https://threejs.org)
