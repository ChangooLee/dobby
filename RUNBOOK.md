# 도비일번 Runbook

> 이 문서는 도비일번 시스템의 실행 절차를 기록한다.
> Claude Code가 재기동 절차를 변경할 때마다 자동으로 업데이트한다.

---

## 구성 요소

| 컴포넌트 | 포트 | 로그 |
|----------|------|------|
| 백엔드 (FastAPI) | 8340 | `/tmp/dobby_server.log` |
| Motion HUD (Electron) | — | `/tmp/hud.log` |

> Motion HUD가 음성(Voice WebSocket) + 모션(MediaPipe) + 시각화(Arc Reactor)를 모두 담당한다.
> 별도 브라우저 프론트엔드(포트 5173) 불필요.

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

---

## 상태 확인

```bash
# 백엔드
lsof -i :8340 | grep LISTEN

# Motion HUD
ps aux | grep "electron dist" | grep -v grep

# 백엔드 로그 tail
tail -f /tmp/dobby_server.log

# HUD 로그
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
npm run build 2>/dev/null  # TypeScript 변경 시에만 필요
npm start &>/tmp/hud.log &
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
| `.env` | API 키, 음성 설정 (`SAY_VOICE=Yuna`) |
| `config/desktops.yaml` | 데스크톱-프로젝트 매핑 |
| `~/Library/Application Support/Electron/hud-settings.json` | HUD 창 위치 저장 |

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

## 주요 설정값

```env
SAY_VOICE=Yuna          # 한국어 TTS (Eddy, Reed, Sandy, Flo, Shelley 도 가능)
MOTION_CONTROL_ENABLED=false  # 모션 제어 기본 OFF
```

---

## 알려진 이슈 및 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| 음성(TTS) 안 나옴 | `SAY_VOICE=Daniel` (영어 음성) | `SAY_VOICE=Yuna` 로 변경 후 서버 재시작 |
| 데스크톱 전환 안 됨 | osascript Accessibility 권한 없음 | pyautogui fallback 자동 사용 (현재 설정) |
| Motion HUD cat's cradle 안 보임 | MediaPipe handedness 레이블 미감지 | hand index 기반으로 수정됨 (현재 설정) |
| 음성 인식 안 됨 | AudioContext suspended | HUD 창 클릭 후 자동 활성화 |

---

## 음성 명령 요약

| 명령 | 동작 |
|------|------|
| "모션 HUD 실행해" / "HUD 띄워" | Motion HUD Electron 창 실행 |
| "모션 제어 시작해" | 카메라 켜기, 손동작 인식 |
| "모션 제어 꺼" | 카메라 끄기 |
| "agent-portal로 이동해" | 해당 Space로 데스크톱 전환 |
| "2번 데스크톱으로 이동해" | 데스크톱 2로 전환 |
| "현재 프로젝트 클로드 코드 실행해" | 현재 active 프로젝트에서 Claude Code 실행 |

## 손동작 요약

| 제스처 | 동작 |
|--------|------|
| ✊ 주먹 | Ctrl+C (터미널 인터럽트) — 1.5s 디바운스 |
| 🤚 손바닥 | y + Enter (승인) — 2s 디바운스 |
| ✌️ V사인 | 음성 인식 ON/OFF 토글 |
| ☝️ 검지 펴기 | 마우스 포인터 모드 |
| 👌 엄지+검지 핀치 | 좌클릭 |
| 엄지+중지 핀치 | 우클릭 |
| 손 좌우 스와이프 | 데스크톱 전환 |

---

*마지막 업데이트: 2026-04-29*
