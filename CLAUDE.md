# DOBBY — macOS Voice AI Assistant

> **플랫폼**: macOS 전용 (AppleScript 의존). Linux/Windows 미지원.

## 프로젝트 개요

DOBBY는 음성 대화 + 손동작 제어 기반 AI 어시스턴트입니다.
- **Electron HUD**가 UI 전체를 담당 (Three.js 오브, MediaPipe 손동작, 음성 인식/재생)
- **FastAPI 백엔드**(port 8340)가 LLM·TTS·macOS 연동을 처리
- 브라우저(Chrome 등) 불필요 — Electron이 Chromium을 내장

## 실행·재시작 절차

→ **[RUNBOOK.md](RUNBOOK.md)** 를 항상 먼저 확인할 것.

재기동 절차가 변경될 때마다 RUNBOOK.md를 업데이트해야 한다.

## 빠른 셋업 (신규 클론 시)

1. `.env.example` → `.env` 복사 후 API 키 입력
2. Anthropic API 키: [console.anthropic.com](https://console.anthropic.com)
3. Fish Audio API 키: [fish.audio](https://fish.audio)
4. Python 의존성: `python -m venv .venv && .venv/bin/pip install -r requirements.txt`
5. Motion HUD 빌드: `cd motion-hud && npm install && npm run build && cd ..`
6. 백엔드 실행: `nohup .venv/bin/python server.py > /tmp/dobby_server.log 2>&1 &`
7. HUD 실행: `cd motion-hud && npm start &>/tmp/hud.log &`

SSL 인증서(key.pem, cert.pem)가 없으면:
```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=localhost'
```

## 아키텍처

```
Motion HUD (Electron)
├── hud.html          — Three.js 오브 + MediaPipe 손동작 + 음성 인식/재생
├── src/main.ts       — BrowserWindow 생성, 항상 맨 위, 모든 Space에 표시
└── src/preload.ts    — contextBridge (electronAPI 노출)
        │
        │ WebSocket ws://localhost:8340/ws/voice   (음성 대화)
        │ WebSocket ws://localhost:8340/ws/motion  (손동작 이벤트)
        ▼
FastAPI 백엔드 (server.py, port 8340)
├── LLM: Claude Haiku (빠른 응답) / Claude Opus (리서치)
├── TTS: Fish Audio → WAV → base64 → WebSocket
├── Actions: AppleScript, Claude Code subprocess
└── Memory: SQLite + FTS5
```

## 주요 파일

| 파일 | 역할 |
|------|------|
| `server.py` | FastAPI 메인 서버 (WebSocket, LLM, TTS, 액션 디스패치) |
| `motion-hud/hud.html` | Electron HUD 전체 (Three.js + MediaPipe + 음성) |
| `motion-hud/src/main.ts` | Electron 메인 프로세스 |
| `actions.py` | 시스템 액션 (Terminal, Chrome, Claude Code 실행) |
| `memory.py` | SQLite 장기 메모리 (FTS5 검색) |
| `calendar_access.py` | Apple Calendar (AppleScript, 읽기) |
| `mail_access.py` | Apple Mail (읽기 전용) |
| `notes_access.py` | Apple Notes (읽기/쓰기) |
| `work_mode.py` | Claude Code 세션 관리 |
| `desktop_manager.py` | macOS Space 전환, 활성 프로젝트 추적 |
| `dispatch_registry.py` | 액션 태그 → 핸들러 라우팅 |
| `config/desktops.yaml` | Space 번호 ↔ 프로젝트 디렉토리 매핑 |
| `RUNBOOK.md` | 실행·재시작·종료 절차 (항상 최신 유지) |

## 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API |
| `FISH_API_KEY` | ✅ | Fish Audio TTS |
| `FISH_VOICE_ID` | — | 음성 모델 ID |
| `USER_NAME` | — | 사용자 이름 (DOBBY 호칭) |
| `CALENDAR_ACCOUNTS` | — | 캘린더 이메일 (쉼표 구분) |
| `SAY_VOICE` | — | 로컬 TTS 폴백 (기본: `Yuna`) |
| `MOTION_CONTROL_ENABLED` | — | 모션 제어 기본값 (기본: `false`) |

## 코딩 컨벤션

- DOBBY 퍼소나: 영국식 집사, 건조한 위트, 간결한 언어
- 음성 응답은 최대 1–2문장
- 액션 태그: `[ACTION:BUILD]`, `[ACTION:BROWSE]`, `[ACTION:RESEARCH]`, `[ACTION:OPEN_CLAUDE]`, `[ACTION:TYPE_TO_CLAUDE]` 등
- 모든 macOS 연동은 AppleScript (OAuth 없음)
- Mail은 읽기 전용 (설계 원칙)
- 로컬 데이터는 SQLite

## Motion HUD TypeScript 수정 시

```bash
cd motion-hud
npm run build   # tsc
# 그 다음 HUD 재시작 (RUNBOOK.md 참고)
```

## 알려진 제약

- macOS Accessibility 권한 필요 (손동작으로 마우스/키보드 제어 시)
- Fish Audio TTS 장애 시 `say` 명령어로 자동 폴백
- MediaPipe는 인터넷 CDN 로드 (오프라인 환경 주의)
- Three.js는 `motion-hud/three.module.min.js` 로컬 번들 사용
