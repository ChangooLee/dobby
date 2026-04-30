# DOBBY 문제 해결 가이드

## 손 스와이프로 데스크톱 전환이 안 될 때

### 1단계: 모션 제어가 활성화됐는지 확인
- HUD 우측 패널 MOTION → 제어 값이 `ACTIVE`인지 확인
- `ACTIVE`가 아니면: 카메라가 켜졌는지, WebSocket이 연결됐는지 확인

### 2단계: 스와이프가 감지되는지 확인 (D키 디버그)
1. HUD 창에서 `D` 키를 누르면 Debug Overlay가 표시됩니다
2. 손을 천천히 좌우로 스와이프해 보세요
3. `SWIPE dx`, `VELOCITY` 값이 변하는지 확인
4. 값이 `THRESHOLD` (d≥0.12, v≥0.45)에 미치지 못하면 더 빠르고 크게 스와이프하세요

### 3단계: WebSocket 이벤트가 전송되는지 확인
- Debug Overlay의 `LAST EVENT` 값이 `desktop.next` 또는 `desktop.previous`로 바뀌는지 확인
- `MOTION WS` 값이 `✓ 연결됨`인지 확인

### 4단계: Backend ack 확인
- Debug Overlay의 `ACK` 값이 `✓` 또는 `✗`로 바뀌는지 확인
- `✗`이면 백엔드 오류 — `/tmp/dobby_server.log`를 확인하세요

### 5단계: macOS 접근성 권한 확인
macOS는 다른 앱의 키 입력을 시뮬레이션하려면 접근성 권한이 필요합니다.

1. **시스템 설정** → **개인 정보 보호 및 보안** → **손쉬운 사용**
2. 다음 앱에 권한 허용:
   - Terminal
   - Python (또는 Python 3.x)
   - Electron (또는 dobby-motion-hud)

### 6단계: Mission Control 단축키 확인
1. **시스템 설정** → **키보드** → **키보드 단축키** → **Mission Control**
2. "왼쪽으로 Space 이동" = `⌃←` (Control + 왼쪽 화살표) 확인
3. "오른쪽으로 Space 이동" = `⌃→` (Control + 오른쪽 화살표) 확인
4. 단축키가 비활성화됐으면 활성화하세요

---

## Claude Code가 열리지 않을 때

### 1단계: claude 실행 파일 확인
```bash
which claude
claude --version
```

### 2단계: CLAUDE_BIN 환경 변수 설정
`which claude` 결과가 비어있거나 FastAPI 프로세스에서 찾지 못하면:
```bash
# .env 파일에 추가
CLAUDE_BIN=/opt/homebrew/bin/claude
```

### 3단계: /api/claude/status 확인
```bash
curl -sk https://localhost:8340/api/claude/status | python3 -m json.tool
```

기대 응답:
```json
{
  "available": true,
  "claude_bin": "/opt/homebrew/bin/claude",
  "version": "...",
  "last_error": null
}
```

### 4단계: Terminal 접근성 권한 확인
Terminal.app이 AppleScript를 실행하려면 권한이 필요합니다.
시스템 설정 → 개인 정보 보호 → 자동화 → Terminal → System Events 허용

---

## TTS 음성이 안 나올 때

1. Qwen3 TTS 서버 확인: `curl http://localhost:8000/v1/models`
2. Qwen3 실패 시 macOS say 폴백 확인: `.env`에서 `SAY_VOICE=Yuna` 설정
3. 백엔드 재시작: `kill $(lsof -ti :8340) && nohup .venv/bin/python server.py > /tmp/dobby_server.log 2>&1 &`

---

## HUD가 뜨지 않을 때

```bash
# TypeScript 빌드 확인
ls motion-hud/dist/main.js

# 없으면 빌드
cd motion-hud && npm run build

# 시작
npm start &>/tmp/hud.log &
```

---

## 로그 위치

| 컴포넌트 | 로그 경로 |
|----------|-----------|
| FastAPI 백엔드 | `/tmp/dobby_server.log` |
| Motion HUD (Electron) | `/tmp/hud.log` |
| Qwen3 TTS 서버 | `/tmp/qwen_tts.log` |

---

## 수동 QA 체크리스트

- [ ] FastAPI 서버 실행 (`lsof -i :8340 | grep LISTEN`)
- [ ] Motion HUD 실행 (`ps aux | grep "electron dist"`)
- [ ] HUD가 모든 데스크톱 위에 유지됨
- [ ] 카메라 권한 허용 후 손 landmark 표시됨
- [ ] 양손 fingertip Cat's Cradle string 표시됨
- [ ] D 키로 debug overlay 표시/숨김
- [ ] 오른손 open palm swipe right → HUD에 swipe confirmed 표시
- [ ] Debug Overlay LAST EVENT: `desktop.next` 표시됨
- [ ] Debug Overlay ACK: `✓` 표시됨
- [ ] 실제 macOS 데스크톱이 다음 Space로 이동함
- [ ] `/api/claude/status` 응답: `available: true`
- [ ] OPEN_CLAUDE → Terminal.app에서 올바른 프로젝트 경로로 claude 실행됨
- [ ] Escape 키로 모션 일시정지됨
