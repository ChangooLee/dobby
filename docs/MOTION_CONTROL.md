# DOBBY Motion Control — 손동작 제어 가이드

## 개요

DOBBY의 Motion HUD는 MediaPipe Hands를 사용해 양손을 실시간 추적합니다.
손동작으로 macOS 데스크톱 전환, 마우스 제어, 음성 ON/OFF 등을 할 수 있습니다.

## 손동작 목록

| 제스처 | 동작 | 디바운스 |
|--------|------|---------|
| ✊ 주먹 (Fist) | Ctrl+C 전송 (터미널 인터럽트) | 1.5초 |
| 🤚 손바닥 (Palm) | y + Enter (Claude Code 승인) | 2초 |
| ✌️ V사인 | 음성 인식 ON/OFF 토글 | 0.8초 |
| ☝️ 검지 펴기 | 마우스 포인터 모드 | — |
| 👌 엄지+검지 핀치 | 좌클릭 | 0.5초 |
| 엄지+중지 핀치 | 우클릭 | 0.5초 |
| **손 좌우 스와이프** | **macOS Space 전환** | 0.7초 |

## 데스크톱 스와이프

오른쪽 스와이프 → 다음 Space  
왼쪽 스와이프 → 이전 Space

### 스와이프 요령
- 손바닥(Palm)을 펴고 빠르게 좌우로 이동
- 최소 이동 거리: 화면 너비의 12% (CONFIG.SWIPE_DISTANCE = 0.12)
- 최소 속도: 0.45 (정규화 단위/초)
- 수평 이동이 수직보다 1.5배 이상 커야 함

## Debug Overlay

키보드 `D`로 Debug Overlay를 켜고 끌 수 있습니다.

표시 항목:
- MOTION WS / VOICE WS: WebSocket 연결 상태
- MOTION: 활성/일시정지/비활성
- HAND L/R: 각 손의 히스토리 프레임 수
- SWIPE dx / VELOCITY: 스와이프 이동량과 속도
- THRESHOLD: 현재 설정된 임계값
- LAST EVENT: 마지막으로 백엔드에 보낸 이벤트
- ACK: 백엔드 응답 (✓ 성공 / ✗ 실패)
- CLAUDE: Claude Code 실행 파일 상태

## 키보드 단축키

| 키 | 동작 |
|----|------|
| `D` | Debug Overlay 토글 |
| `R` | 제스처 히스토리 리셋 |
| `Esc` | 모션 일시정지 |

## 설정 파일

`config/desktops.yaml`:
```yaml
desktops:
  1:
    name: "DOBBY Main"
    project_path: "~/Workspace/dobby"
    role: main_control
  2:
    name: "project-name"
    project_path: "~/Workspace/project-name"
    role: development_project
```

## 스와이프 파이프라인

```
HUD 감지 → WS 이벤트 전송 → 백엔드 수신
→ AppleScript/pyautogui 실행 → macOS Space 이동 → ACK 반환 → HUD 표시
```

## 권한 설정

macOS 접근성 권한 필요 항목:
- 시스템 설정 → 개인 정보 보호 → 손쉬운 사용 → Terminal/Python 허용
- 시스템 설정 → 키보드 → 단축키 → Mission Control → Space 이동 단축키 활성화

자세한 문제 해결: `docs/TROUBLESHOOTING.md`
