# DOBBY

> **macOS 전용** — Apple Silicon / Intel Mac 모두 지원. Linux/Windows 미지원.

DOBBY는 한국어 음성 대화 기반의 AI 어시스턴트입니다. 말하면 대답하고, 손동작으로 조작하며, 파티클 오브가 목소리에 반응합니다.

Apple Calendar · Mail · Notes에 연결되고, 웹을 검색하고, Claude Code 세션을 열어 코드를 작성합니다.

---

## 구조 한눈에 보기

```
[ 마이크 ]
    │  Web Speech API (Electron Chromium)
    ▼
[ Motion HUD ] ── WebSocket ──► [ FastAPI 백엔드 (port 8340) ]
  Electron 창                        │
  ├─ Three.js 파티클 오브             ├─ Claude (AI 응답 생성)
  ├─ MediaPipe 손동작 인식            ├─ Fish Audio TTS
  ├─ 음성 인식 / 재생                 ├─ AppleScript (Calendar·Mail·Notes·Terminal)
  └─ 캘린더·태스크 정보 표시          └─ Claude Code 세션 관리
```

| 레이어 | 기술 |
|--------|------|
| HUD (UI 전체) | Electron + Three.js + MediaPipe Hands |
| 백엔드 | FastAPI + Python (`server.py`) |
| 통신 | WebSocket (`/ws/voice`, `/ws/motion`) |
| AI (빠른 응답) | Claude Haiku |
| AI (리서치·복잡한 태스크) | Claude Opus |
| TTS | Fish Audio (DOBBY 음성 모델) |
| macOS 연동 | AppleScript (OAuth 불필요) |
| 메모리 | SQLite + FTS5 |

---

## 요구사항

- **macOS 12 Monterey 이상** (AppleScript 의존)
- Python 3.11+
- Node.js 18+
- Anthropic API 키 ([발급](https://console.anthropic.com/))
- Fish Audio API 키 ([발급](https://fish.audio/))

> Google Chrome / 별도 브라우저는 필요 없습니다. 모든 UI는 Electron HUD가 담당합니다.

---

## 빠른 시작

```bash
git clone https://github.com/ChangooLee/dobby.git
cd dobby
```

Claude Code를 사용한다면 `claude` 를 실행하면 `CLAUDE.md`를 읽고 셋업을 안내합니다.

### 수동 설치

```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력

# 2. Python 의존성
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Motion HUD 의존성 빌드
cd motion-hud && npm install && npm run build && cd ..

# 4. 백엔드 시작
nohup .venv/bin/python server.py > /tmp/dobby_server.log 2>&1 &

# 5. Motion HUD 시작
cd motion-hud && npm start &>/tmp/hud.log &
```

> 자세한 실행·재시작·종료 절차는 **[RUNBOOK.md](RUNBOOK.md)** 를 참고하세요.

---

## 환경 변수 (`.env`)

```env
# 필수
ANTHROPIC_API_KEY=your-key-here
FISH_API_KEY=your-key-here

# 선택
FISH_VOICE_ID=            # Fish Audio 음성 모델 ID
USER_NAME=                # 이름 (DOBBY가 호칭에 사용)
CALENDAR_ACCOUNTS=        # 캘린더 이메일 (쉼표 구분, 비워두면 자동 탐색)
SAY_VOICE=Yuna            # 로컬 TTS 폴백 음성 (Fish 장애 시)
MOTION_CONTROL_ENABLED=false
```

---

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

---

## 기능 상세

### 음성 대화
DOBBY는 항상 듣고 있습니다. 자연어로 말하면 Haiku가 1–2문장으로 응답하고, Fish Audio가 음성으로 변환합니다.

### 손동작 제어 (MediaPipe Hands)

| 제스처 | 동작 |
|--------|------|
| ✊ 주먹 | Ctrl+C (터미널 인터럽트) |
| 🤚 손바닥 | y + Enter (Claude Code 승인) |
| ✌️ V사인 | 음성 인식 ON/OFF 토글 |
| ☝️ 검지 | 마우스 포인터 모드 |
| 👌 엄지+검지 핀치 | 좌클릭 |
| 손 좌우 스와이프 | macOS Space 전환 |

### 액션 태그
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

### Three.js 파티클 오브
2000개 파티클이 구형으로 모여 상태에 따라 움직입니다:
- **idle** — 넓게 퍼져 천천히 유영
- **listening** — 수축, 선명해짐
- **thinking** — 밀도 높아짐, 전자 이동 (연결선 사이를 흐르는 빛)
- **speaking** — 음성 bass에 반응해 파동

---

## 실행·재시작 절차

→ **[RUNBOOK.md](RUNBOOK.md)** 참고

---

## 라이선스

개인 비상업적 사용에 한해 무료. 상업적 사용은 별도 문의. [LICENSE](LICENSE) 참조.

---

## Credits

Powered by [Anthropic Claude](https://anthropic.com) · [Fish Audio](https://fish.audio) · [MediaPipe](https://mediapipe.dev) · [Three.js](https://threejs.org)
