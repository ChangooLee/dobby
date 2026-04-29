# 도비일번 Motion Control — 모션 제어 가이드

MacBook 카메라를 사용해 손동작으로 macOS 데스크톱/Space를 이동하고 마우스를 제어하는 기능입니다.

---

## 왜 Motion HUD를 메인 화면과 분리했나

도비일번 메인 화면은 Chrome 탭(http://localhost:5173)에서 실행됩니다. macOS 데스크톱/Space를 전환하면 Chrome 탭도 다른 Space로 이동하거나 보이지 않게 됩니다. 이 경우 카메라/모션 인식이 중단됩니다.

**해결 방법: Electron HUD** (`motion-hud/`)

- Electron으로 만든 별도의 작은 창
- `setAlwaysOnTop(true, 'screen-saver')` — 항상 화면 위에 표시
- `setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })` — 모든 macOS Space에서 보임
- Dock 아이콘 없음, 완전히 독립적으로 동작

---

## 필요한 macOS 권한

| 권한 | 이유 | 확인 방법 |
|------|------|-----------|
| 카메라 | MediaPipe 손 추적 | 시스템 환경설정 > 개인정보 > 카메라 |
| 손쉬운 사용 (Accessibility) | pyautogui 마우스 제어 | 시스템 환경설정 > 개인정보 > 손쉬운 사용 → Terminal 또는 Python 허용 |
| 자동화 (Automation) | AppleScript 데스크톱 전환 | 최초 실행 시 팝업으로 요청됨 |

> Screen Recording 권한은 **요구하지 않습니다.**

---

## 설치

### Electron HUD 설치
```bash
cd motion-hud
npm install
npm run build
```

### Python 의존성 (서버)
```bash
pip install pyautogui  # 또는: pip install -r requirements.txt
```

pyautogui는 macOS에서 Quartz 기반으로 마우스를 제어합니다. 접근성 권한이 필요합니다.

---

## 실행 방법

### 1. 도비일번 백엔드 시작
```bash
python server.py
```

### 2. 도비일번 프론트엔드 시작
```bash
cd frontend && npm run dev
```

### 3. Motion HUD 시작
```bash
cd motion-hud && npm start
```

또는 빌드 후:
```bash
cd motion-hud && node_modules/.bin/electron dist/main.js
```

HUD는 화면 우측 상단에 작은 창으로 떠 있습니다. 모든 macOS 데스크톱/Space에서 보입니다.

### 4. 모션 제어 활성화
음성 명령: **"도비일번, 모션 제어 시작해"**
또는 HUD의 **켜기** 버튼 클릭

---

## 지원 제스처

### 데스크톱 이동 (스와이프)

| 제스처 | 동작 |
|--------|------|
| 손을 빠르게 오른쪽으로 스와이프 | 다음 데스크톱 (Ctrl+→) |
| 손을 빠르게 왼쪽으로 스와이프 | 이전 데스크톱 (Ctrl+←) |

- 스와이프는 손목 위치를 추적
- 디바운스: 900ms (연속 입력 방지)
- 양손 모두 사용 가능

### 마우스 포인터

오른손 검지를 펴고 나머지 손가락을 접으면 포인터 모드가 활성화됩니다.

| 제스처 | 동작 |
|--------|------|
| 검지 펴기 + 나머지 접기 | 포인터 모드 활성화 |
| 검지 이동 | 마우스 커서 이동 |
| 엄지 + 검지 pinch | 좌클릭 |
| 엄지 + 중지 pinch | 우클릭 |

### 스크롤

오른손을 수직으로 이동하면 스크롤됩니다.

| 제스처 | 동작 |
|--------|------|
| 손 위로 이동 | 위로 스크롤 |
| 손 아래로 이동 | 아래로 스크롤 |

---

## 음성 명령

### 모션 제어 기본

| 음성 명령 | 동작 |
|-----------|------|
| "도비일번, 모션 제어 시작해" | 카메라 켜기, 손동작 인식 시작 |
| "도비일번, 모션 제어 켜" | 동일 |
| "도비일번, 모션 제어 꺼" | 카메라 끄기, 모션 제어 종료 |
| "도비일번, 모션 제어 멈춰" | 모션 제어 비활성화 |
| "도비일번, 모션 제어 일시정지" | 카메라는 유지, 제스처만 무시 |
| "도비일번, 모션 제어 재개" | 일시정지 해제 |
| "도비일번, 모션 제어 보정해" | 마우스 포인터 보정 |

### 데스크톱/프로젝트 이동

| 음성 명령 | 동작 |
|-----------|------|
| "도비일번, 2번 데스크톱으로 이동해" | 2번 Space로 전환 |
| "도비일번, agent-portal로 이동해" | agent-portal 프로젝트 Space로 전환 |
| "도비일번, mcp-opendart 프로젝트로 이동해" | mcp-opendart Space로 전환 |
| "도비일번, sourceport로 이동해" | sourceport Space로 전환 |
| "도비일번, 현재 데스크톱을 3번으로 맞춰" | 내부 인덱스를 3으로 동기화 |

### HUD 제어

| 음성 명령 | 동작 |
|-----------|------|
| "도비일번, HUD 숨겨" | Motion HUD 숨기기 |
| "도비일번, HUD 보여줘" | Motion HUD 보이기 |

---

## 프로젝트/데스크톱 매핑 설정

`config/desktops.yaml` 파일을 편집합니다:

```yaml
desktops:
  1:
    name: "도비일번 메인"
    project_path: "~/Workspace/dobby"
    role: main_control

  2:
    name: "agent-portal"
    project_path: "~/Workspace/agent-portal"
    role: development_project

  3:
    name: "mcp-opendart"
    project_path: "~/Workspace/mcp-opendart"
    role: development_project
```

**데스크톱 번호 = macOS Mission Control의 Space 순서**  
왼쪽부터 1번, 2번, 3번...

---

## 민감도 조정

`config/desktops.yaml`의 `settings` 섹션에서 조정합니다:

```yaml
settings:
  swipe_velocity_threshold: 0.8   # 낮추면 더 쉽게 스와이프 인식
  swipe_distance_threshold: 0.2   # 낮추면 짧은 스와이프도 인식
  pinch_threshold: 0.06           # 높이면 더 느슨한 pinch 인식
  desktop_switch_debounce: 1.0    # 낮추면 더 빠른 연속 전환 가능
  mouse_smooth_alpha: 0.4         # 낮추면 더 반응적, 높이면 더 부드러움
```

---

## 데스크톱 인덱스 동기화

도비일번은 데스크톱 전환 기록을 내부적으로 추적합니다. 하지만 트랙패드나 키보드로 직접 Space를 전환하면 내부 인덱스가 어긋날 수 있습니다.

**재동기화 방법:**
- 음성: "도비일번, 현재 데스크톱을 3번으로 맞춰"
  - 이 경우 `[ACTION:DESKTOP_GOTO] 3` 태그로 처리됩니다

---

## 일시정지 및 안전 정지

아래 방법으로 모션 제어를 일시정지할 수 있습니다:

1. **Escape 키** — HUD 창에서 Escape
2. **음성 명령** — "모션 제어 일시정지" / "모션 제어 꺼"
3. **HUD 버튼** — HUD의 끄기 버튼
4. **자동 일시정지** — 손이 3초 이상 인식되지 않으면 자동 일시정지
5. **카메라 오류** — 카메라 권한이 끊기면 자동 정지

---

## 안전 제한사항

손동작으로 **직접 실행할 수 없는** 작업:
- 파일 수정 / 코드 변경
- Claude Code 실행
- 터미널 명령 실행
- 테스트 실행

이러한 작업은 반드시 **음성 명령** 또는 **명확한 텍스트 명령**을 통해서만 실행됩니다.

손동작으로 가능한 작업:
- 데스크톱/Space 이동
- 프로젝트 선택 (Space 이동만)
- 마우스 이동, 클릭, 스크롤
- 모션 제어 일시정지/재개

---

## 수동 QA 체크리스트

1. [ ] 도비일번 백엔드 실행 (`python server.py`)
2. [ ] 도비일번 프론트엔드 실행 (`cd frontend && npm run dev`)
3. [ ] Motion HUD 실행 (`cd motion-hud && npm start`)
4. [ ] Chrome에서 http://localhost:5173 접속
5. [ ] HUD 창이 화면 우측 상단에 뜨는지 확인
6. [ ] "도비일번, 모션 제어 시작해" 명령
7. [ ] HUD의 켜기 버튼 클릭 (카메라 권한 허용)
8. [ ] HUD에 카메라 영상 + 손 랜드마크 + 네온 문자열 표시 확인
9. [ ] 손 스와이프로 데스크톱 이동 확인
10. [ ] 데스크톱 이동 후에도 HUD가 계속 떠 있는지 확인
11. [ ] "도비일번, agent-portal로 이동해" 명령 확인
12. [ ] 검지 포인터로 마우스 이동 확인
13. [ ] pinch 좌클릭/우클릭 확인
14. [ ] 두 손가락 스크롤 확인
15. [ ] Escape로 모션 제어 일시정지 확인
16. [ ] "도비일번, 모션 제어 꺼"로 카메라 종료 확인

---

## 문제 해결

### HUD 창이 다른 창 뒤에 가려진다
- macOS에서 `screen-saver` 레벨의 창은 일반 앱 창보다 항상 위에 표시됨
- 전체화면 앱(예: Keynote)에서는 HUD가 보이지 않을 수 있음 — 전체화면 앱에서 ESC로 전체화면 종료 후 확인

### 카메라가 시작되지 않는다
- HUD를 처음 실행하면 Chrome 또는 Electron이 카메라 권한을 요청함
- 시스템 환경설정 > 개인정보 > 카메라에서 허용

### 마우스 제어가 작동하지 않는다
- 시스템 환경설정 > 개인정보 > 손쉬운 사용에서 Terminal (또는 Python) 허용
- pyautogui 설치 확인: `pip install pyautogui`

### 데스크톱 전환이 안 된다
- 시스템 환경설정 > 개인정보 > 자동화에서 Terminal 허용
- 시스템 환경설정 > 키보드 > 단축키 > 미션 컨트롤에서 Control+화살표 단축키가 활성화되어 있는지 확인

### 손 인식이 불안정하다
- 조명이 밝은 환경 권장
- 배경이 단순할수록 인식률 향상
- `config/desktops.yaml`의 `minDetectionConfidence` 값 낮추기 (현재 0.7)

---

## 알려진 한계

- macOS 전체화면 앱(Mission Control 적용 전) 위에 HUD가 표시되지 않을 수 있음
- Space 번호는 도비일번 내부에서 추적하며, 키보드/트랙패드로 직접 전환한 경우 어긋날 수 있음 → 음성으로 재동기화 가능
- MediaPipe 모델 초기 로딩에 2~5초 소요될 수 있음
- 햇빛이 강하거나 역광 환경에서 손 인식률 저하
- pyautogui 마우스 제어는 macOS 접근성 권한 필요

---

## 기술 스택

- **Electron** — Motion HUD 창 (항상 위에 + 모든 Space)
- **MediaPipe Hands** — 손 관절 추적 (21개 랜드마크)
- **Canvas 2D** — 네온 시각화 (Three.js 없음)
- **pyautogui** — macOS 마우스 제어 (Quartz 기반)
- **AppleScript** — 데스크톱/Space 전환 (Control+화살표)
- **WebSocket** — HUD ↔ 도비일번 백엔드 통신 (`/ws/motion`)
