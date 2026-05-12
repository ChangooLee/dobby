# DOBBY Runbook

> **위치**: 프로젝트 루트 `/Users/changoo/Workspace/dobby/RUNBOOK.md`
>
> 이 문서는 DOBBY 시스템의 실행·재시작·종료 절차를 기록한다.
> Claude Code가 재기동 절차를 변경할 때마다 이 파일을 업데이트해야 한다.

---

## 구성 요소

| 컴포넌트 | 포트 | 로그 경로 |
|----------|------|-----------|
| 백엔드 (FastAPI) | 8340 | `/tmp/dobby_server.log` |
| Motion HUD (Electron) | — | `/tmp/hud.log` |

> Motion HUD가 음성 인식(STT) · 음성 재생(TTS) · 손동작(MediaPipe) · 시각화(Three.js 오브)를 모두 담당한다.
> 별도 브라우저 프론트엔드는 불필요하다.

---

## 전체 시작 순서

```bash
cd ~/Workspace/dobby
```

### 1. 백엔드 시작

```bash
nohup .venv/bin/python server.py > /tmp/dobby_server.log 2>&1 &
echo "Backend PID: $!"
```

### 2. Motion HUD 시작

```bash
cd motion-hud && npm start &>/tmp/hud.log &
cd ..
```

> HUD가 뜨면 1.5초 후 카메라와 손동작 인식이 자동으로 시작된다.

---

## 상태 확인

```bash
# 백엔드 포트 확인
lsof -i :8340 | grep LISTEN

# Motion HUD 프로세스 확인
ps aux | grep "electron dist" | grep -v grep

# 백엔드 로그 실시간 확인
tail -f /tmp/dobby_server.log

# HUD 로그 확인
cat /tmp/hud.log
```

---

## 개별 재시작

### 백엔드만 재시작

```bash
kill $(lsof -ti :8340) 2>/dev/null; sleep 1
cd ~/Workspace/dobby
nohup .venv/bin/python server.py > /tmp/dobby_server.log 2>&1 &
echo "Backend PID: $!"
```

### Motion HUD만 재시작

```bash
pkill -f "electron dist/main.js" 2>/dev/null; sleep 0.5
cd ~/Workspace/dobby/motion-hud
npm start &>/tmp/hud.log &
```

### Motion HUD TypeScript 수정 후 재시작

```bash
pkill -f "electron dist/main.js" 2>/dev/null; sleep 0.5
cd ~/Workspace/dobby/motion-hud
npm run build && npm start &>/tmp/hud.log &
```

---

## 전체 종료

```bash
kill $(lsof -ti :8340) 2>/dev/null
pkill -f "electron dist/main.js" 2>/dev/null
echo "All stopped"
```

---

## 설정 파일

| 파일 | 용도 |
|------|------|
| `.env` | API 키, 음성 설정 |
| `config/desktops.yaml` | 데스크톱 Space ↔ 프로젝트 디렉토리 매핑 |
| `~/Library/Application Support/Electron/hud-settings.json` | HUD 창 위치 (자동 저장) |

### HUD 창 위치 초기화

```bash
cat > ~/Library/Application\ Support/Electron/hud-settings.json << 'EOF'
{
  "x": 0,
  "y": 0,
  "width": 1920
}
EOF
```

---

## 주요 설정값 (`.env`)

```env
ANTHROPIC_API_KEY=...           # Claude API (필수)
USER_NAME=...                   # 사용자 이름

# Qwen3 TTS (우선 사용, 실패 시 macOS say로 폴백)
QWEN3_TTS_URL=http://100.72.205.44:8000/v1   # Tailscale 또는 localhost
QWEN3_TTS_KEY=...               # API 키
QWEN3_TTS_VOICE=serena          # serena / vivian / ryan / aiden 등
QWEN3_TTS_MODEL=mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-bf16

SAY_VOICE=Yuna                  # 한국어 폴백 TTS (Qwen3 불가 시)
```

---

## 음성 인식 (STT)

- Whisper `large-v3-turbo` (int8, CPU) 사용 — 첫 요청 시 모델 로드 (~2s)
- MediaRecorder 4초 청크 → ffmpeg webm→WAV + noisereduce 전처리 → `/api/stt` → Whisper
- Silero VAD (`threshold=0.3`, `min_speech_duration_ms=100`) 으로 묵음 자동 제거
- 브라우저단 80Hz 하이패스 필터로 저주파 노이즈(AC, 키보드 진동) 제거

---

## 알려진 이슈 및 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| TTS 음성이 안 나옴 | Qwen3 서버 미응답 + say 폴백도 실패 | `.env`에서 `SAY_VOICE=Yuna` 확인 후 백엔드 재시작 |
| Qwen3 TTS 느림 | 서버 불응 → 10초 timeout 후 say로 폴백 | Qwen3 서버 기동 여부 확인 (`curl http://<ip>:8000/v1/models`) |
| 음성 인식이 배경음도 인식 | Whisper VAD threshold | 조용한 환경에서 사용 또는 STT_CHUNK_MS 늘리기 |
| 데스크톱 전환 안 됨 | osascript Accessibility 권한 없음 | 시스템 설정 → 개인 정보 → 손쉬운 사용에서 터미널 허용 |
| HUD가 뜨지 않음 | Electron 빌드 없음 | `cd motion-hud && npm run build && npm start` |
| 백엔드 포트 충돌 | 이전 프로세스 잔존 | `kill $(lsof -ti :8340)` 후 재시작 |

---

## 음성 명령 요약

| 명령 | 동작 |
|------|------|
| "HUD 띄워" / "모션 HUD 실행해" | Motion HUD Electron 창 실행 |
| "모션 제어 시작해" | 카메라 켜고 손동작 인식 시작 |
| "모션 제어 꺼" | 카메라 끄기 |
| "2번 데스크톱으로 이동해" | macOS Space 2로 전환 |
| "현재 프로젝트 클로드 코드 실행해" | 활성 프로젝트에서 Claude Code 실행 |

## 손동작 요약

| 제스처 | 동작 |
|--------|------|
| ✊ 주먹 | Ctrl+C (터미널 인터럽트) — 1.5s 디바운스 |
| 🤚 손바닥 | y + Enter (Claude Code 승인) — 2s 디바운스 |
| ✌️ V사인 | 음성 인식 ON/OFF 토글 |
| ☝️ 검지 펴기 | 마우스 포인터 모드 |
| 👌 엄지+검지 핀치 | 좌클릭 |
| 엄지+중지 핀치 | 우클릭 |
| 손 좌우 스와이프 | macOS Space 전환 |

---

*마지막 업데이트: 2026-05-12*
