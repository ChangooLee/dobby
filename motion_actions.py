"""
도비 Motion Actions — 모션 이벤트 핸들러

WebSocket으로 받은 모션 이벤트를 처리한다.
손동작으로 가능한 작업:
  - 데스크톱 이동
  - 프로젝트 선택
  - 마우스 이동/클릭/스크롤

임의 shell 명령 실행 금지 — 손동작으로 직접 명령 실행 불가.
"""

import asyncio
import logging
import os
import time
from typing import Optional

log = logging.getLogger("dobby.motion")

# motion_control_enabled 기본값 — env에서 읽기
MOTION_CONTROL_ENABLED_DEFAULT = os.getenv("MOTION_CONTROL_ENABLED", "true").lower() == "true"

# pyautogui for mouse control
try:
    import pyautogui
    pyautogui.PAUSE = 0  # no pause between calls
    pyautogui.FAILSAFE = True  # move to top-left corner to abort
    _PYAUTOGUI_OK = True
    log.info("pyautogui loaded — mouse control available")
except ImportError:
    _PYAUTOGUI_OK = False
    log.warning("pyautogui not installed — mouse control disabled. Run: pip install pyautogui")


class MotionController:
    """모션 제어 상태를 관리하고 이벤트를 처리한다."""

    def __init__(self, desktop_manager=None):
        self.enabled = MOTION_CONTROL_ENABLED_DEFAULT
        self.paused = False
        self._desktop_manager = desktop_manager
        self._websockets = []

        # Rate limiting
        self._last_click_time = 0.0
        self._click_debounce = 0.5  # seconds
        self._last_scroll_time = 0.0
        self._scroll_throttle = 0.05  # seconds

        log.info(f"MotionController initialized (enabled={self.enabled})")

    def set_desktop_manager(self, dm):
        self._desktop_manager = dm

    def register_websocket(self, ws):
        if ws not in self._websockets:
            self._websockets.append(ws)

    def unregister_websocket(self, ws):
        if ws in self._websockets:
            self._websockets.remove(ws)

    async def _broadcast(self, msg: dict):
        dead = []
        for ws in self._websockets:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._websockets.remove(ws)

    async def handle_event(self, event_type: str, payload: dict) -> Optional[str]:
        """모션 이벤트를 처리한다. 응답 메시지가 있으면 반환한다."""

        # Control events — always handled regardless of enabled state
        if event_type == "motion_control.enable":
            return await self._enable()
        elif event_type == "motion_control.disable":
            return await self._disable()
        elif event_type == "motion_control.pause":
            return await self._pause()
        elif event_type == "motion_control.resume":
            return await self._resume()
        elif event_type == "motion_control.calibrate":
            return await self._calibrate()
        elif event_type == "motion_control.status":
            return self._get_status()

        # 데스크톱 전환은 항상 허용 (모션 제어 활성화 불필요)
        if event_type == "motion.desktop.next":
            return await self._desktop_next()
        elif event_type == "motion.desktop.previous":
            return await self._desktop_previous()
        elif event_type == "motion.desktop.goto":
            return await self._desktop_goto(payload)

        # 마우스 / 클릭 / 타이핑 — enabled 상태 무관하게 항상 처리
        if event_type == "motion.gesture.mission_control":
            return await self._mission_control()
        elif event_type == "motion.mouse.move":
            return await self._mouse_move(payload)
        elif event_type == "motion.mouse.left_click":
            return await self._mouse_click(payload, right=False)
        elif event_type == "motion.type":
            return await self._type_text(payload)

        # 나머지 모션 이벤트는 enabled 상태일 때만 처리
        if not self.enabled or self.paused:
            return None
        elif event_type == "motion.project.activate":
            return await self._project_activate(payload)
        elif event_type == "motion.mouse.right_click":
            return await self._mouse_click(payload, right=True)
        elif event_type == "motion.mouse.scroll":
            return await self._mouse_scroll(payload)
        elif event_type == "motion.mouse.button_down":
            return await self._mouse_button_down(payload)
        elif event_type == "motion.mouse.button_up":
            return await self._mouse_button_up(payload)
        elif event_type == "motion.status.hand_lost":
            log.info("Hand tracking lost — auto-pausing motion control")
            self.paused = True
            await self._broadcast({"type": "motion_status", "state": "hand_lost"})
        elif event_type == "motion.status.hand_detected":
            if self.paused and self.enabled:
                log.info("Hand detected — resuming motion control")
                self.paused = False
                await self._broadcast({"type": "motion_status", "state": "active"})

        return None

    async def _enable(self) -> Optional[str]:
        if self.enabled and not self.paused:
            return None  # 이미 활성화 — WS 재연결 등으로 중복 요청 시 TTS 없음
        self.enabled = True
        self.paused = False
        log.info("Motion control enabled")
        await self._broadcast({"type": "motion_status", "state": "active"})
        return "모션 제어를 시작합니다, 주인님."

    async def _disable(self) -> str:
        self.enabled = False
        self.paused = False
        log.info("Motion control disabled")
        await self._broadcast({"type": "motion_status", "state": "disabled"})
        return "모션 제어를 끕니다, 주인님."

    async def _pause(self) -> str:
        self.paused = True
        log.info("Motion control paused")
        await self._broadcast({"type": "motion_status", "state": "paused"})
        return "모션 제어를 일시정지합니다, 주인님."

    async def _resume(self) -> str:
        if not self.enabled:
            return "모션 제어가 꺼져 있습니다. 먼저 켜주세요."
        self.paused = False
        log.info("Motion control resumed")
        await self._broadcast({"type": "motion_status", "state": "active"})
        return "모션 제어를 재개합니다, 주인님."

    async def _calibrate(self) -> str:
        await self._broadcast({"type": "motion_calibrate"})
        return "보정을 시작합니다. 오른손 검지를 화면 중앙에 놓아주세요, 주인님."

    def _get_status(self) -> str:
        if not self.enabled:
            return f"모션 제어 비활성화 상태입니다."
        if self.paused:
            return "모션 제어 일시정지 상태입니다."
        dm = self._desktop_manager
        if dm:
            project = dm.get_current_project()
            if project:
                return f"모션 제어 활성화 — 현재 데스크톱 {dm.active_index} ({project['name']})."
        return "모션 제어 활성화 상태입니다."

    async def _desktop_next(self) -> Optional[str]:
        if not self._desktop_manager:
            await self._broadcast({
                "type": "motion_ack",
                "event": "motion.desktop.next",
                "ok": False,
                "message": "데스크톱 관리자가 초기화되지 않았습니다.",
                "error_code": "NO_DESKTOP_MANAGER",
                "active_desktop_index": 1,
            })
            return None
        success = await self._desktop_manager.switch_next()
        idx = self._desktop_manager.active_index
        project = self._desktop_manager.get_current_project()
        name = project["name"] if project else f"데스크톱 {idx}"
        log.info(f"Desktop next → {idx} ({name}) success={success}")
        if success:
            await self._broadcast({
                "type": "desktop_changed",
                "index": idx,
                "name": name,
            })
            await self._broadcast({
                "type": "motion_ack",
                "event": "motion.desktop.next",
                "ok": True,
                "message": f"→ {name}",
                "active_desktop_index": idx,
            })
        else:
            await self._broadcast({
                "type": "motion_ack",
                "event": "motion.desktop.next",
                "ok": False,
                "message": "데스크톱 전환에 실패했습니다. macOS 접근성 권한과 Mission Control 단축키를 확인하세요.",
                "error_code": "DESKTOP_SWITCH_FAILED",
                "active_desktop_index": idx,
            })
        return None

    async def _desktop_previous(self) -> Optional[str]:
        if not self._desktop_manager:
            await self._broadcast({
                "type": "motion_ack",
                "event": "motion.desktop.previous",
                "ok": False,
                "message": "데스크톱 관리자가 초기화되지 않았습니다.",
                "error_code": "NO_DESKTOP_MANAGER",
                "active_desktop_index": 1,
            })
            return None
        success = await self._desktop_manager.switch_previous()
        idx = self._desktop_manager.active_index
        project = self._desktop_manager.get_current_project()
        name = project["name"] if project else f"데스크톱 {idx}"
        log.info(f"Desktop previous → {idx} ({name}) success={success}")
        if success:
            await self._broadcast({
                "type": "desktop_changed",
                "index": idx,
                "name": name,
            })
            await self._broadcast({
                "type": "motion_ack",
                "event": "motion.desktop.previous",
                "ok": True,
                "message": f"← {name}",
                "active_desktop_index": idx,
            })
        else:
            await self._broadcast({
                "type": "motion_ack",
                "event": "motion.desktop.previous",
                "ok": False,
                "message": "데스크톱 전환에 실패했습니다. macOS 접근성 권한과 Mission Control 단축키를 확인하세요.",
                "error_code": "DESKTOP_SWITCH_FAILED",
                "active_desktop_index": idx,
            })
        return None

    async def _desktop_goto(self, payload: dict) -> Optional[str]:
        if not self._desktop_manager:
            return None
        target = payload.get("target")
        if target is None:
            return None

        if isinstance(target, int):
            await self._desktop_manager.switch_to(target)
        elif isinstance(target, str):
            await self._desktop_manager.switch_to_project(target)
        return None

    async def _project_activate(self, payload: dict) -> Optional[str]:
        name = payload.get("name", "")
        if not self._desktop_manager or not name:
            return None
        await self._desktop_manager.switch_to_project(name)
        return None

    async def _mission_control(self) -> None:
        import subprocess
        subprocess.Popen(['osascript', '-e', 'tell application "Mission Control" to launch'])
        log.info("Mission Control launched via gesture")
        return None

    async def _mouse_move(self, payload: dict) -> None:
        if not _PYAUTOGUI_OK:
            return None

        x = payload.get("x")
        y = payload.get("y")
        if x is None or y is None:
            return None

        # Validate coordinates
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            return None

        try:
            pyautogui.moveTo(int(x), int(y), duration=0)
        except Exception as e:
            log.debug(f"Mouse move error: {e}")
        return None

    async def _mouse_click(self, payload: dict, right: bool = False) -> None:
        if not _PYAUTOGUI_OK:
            return None

        now = time.time()
        if now - self._last_click_time < self._click_debounce:
            return None
        self._last_click_time = now

        x = payload.get("x")
        y = payload.get("y")

        try:
            if x is not None and y is not None:
                button = "right" if right else "left"
                pyautogui.click(int(x), int(y), button=button)
                log.info(f"Click {button} at ({int(x)}, {int(y)})")
            else:
                if right:
                    pyautogui.rightClick()
                else:
                    pyautogui.click()
                log.info("Click (current pos)")
        except Exception as e:
            log.warning(f"Click error: {e}")
        return None

    async def _mouse_scroll(self, payload: dict) -> None:
        if not _PYAUTOGUI_OK:
            return None

        now = time.time()
        if now - self._last_scroll_time < self._scroll_throttle:
            return None
        self._last_scroll_time = now

        dy = payload.get("dy", 0)
        try:
            scroll_amount = int(dy * 3)
            if scroll_amount != 0:
                pyautogui.scroll(scroll_amount)
        except Exception as e:
            log.debug(f"Scroll error: {e}")
        return None

    async def _mouse_button_down(self, payload: dict) -> None:
        if not _PYAUTOGUI_OK:
            return None
        x, y = payload.get("x"), payload.get("y")
        try:
            if x is not None and y is not None:
                pyautogui.mouseDown(int(x), int(y), button="left")
            else:
                pyautogui.mouseDown(button="left")
        except Exception as e:
            log.debug(f"MouseDown error: {e}")
        return None

    async def _mouse_button_up(self, payload: dict) -> None:
        if not _PYAUTOGUI_OK:
            return None
        x, y = payload.get("x"), payload.get("y")
        try:
            if x is not None and y is not None:
                pyautogui.mouseUp(int(x), int(y), button="left")
            else:
                pyautogui.mouseUp(button="left")
        except Exception as e:
            log.debug(f"MouseUp error: {e}")
        return None

    async def _type_text(self, payload: dict) -> None:
        """STT 텍스트를 현재 포커스된 입력창에 타이핑."""
        text = payload.get("text", "").strip()
        if not text:
            return None
        import asyncio, subprocess, time

        def _do_type():
            from pynput.keyboard import Key, Controller as KbdCtrl
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            time.sleep(0.05)
            kbd = KbdCtrl()
            kbd.press(Key.cmd)
            kbd.press('v')
            kbd.release('v')
            kbd.release(Key.cmd)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _do_type)
            log.info(f"Typed via clipboard: {text!r}")
        except Exception as e:
            log.warning(f"Type error: {e}")
        return None


# Voice command → motion action mapping
MOTION_VOICE_TRIGGERS = {
    "모션 제어 시작": "motion_control.enable",
    "모션 제어 켜": "motion_control.enable",
    "모션 제어 멈춰": "motion_control.disable",
    "모션 제어 꺼": "motion_control.disable",
    "모션 제어 일시정지": "motion_control.pause",
    "모션 제어 재개": "motion_control.resume",
    "모션 제어 보정": "motion_control.calibrate",
    "hud 숨겨": "hud.hide",
    "hud 보여": "hud.show",
    "hud 작게": "hud.collapse",
    "hud 크게": "hud.expand",
}


def detect_motion_voice_command(text: str) -> Optional[str]:
    """음성 텍스트에서 모션 제어 명령을 감지한다."""
    text_lower = text.lower()
    for trigger, event_type in MOTION_VOICE_TRIGGERS.items():
        if trigger in text_lower:
            return event_type
    return None
