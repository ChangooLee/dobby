"""
도비일번 Desktop Manager — 데스크톱/Space와 프로젝트 매핑 관리

활성 데스크톱 인덱스를 추적하고, 프로젝트-데스크톱 매핑 설정을 관리한다.
실제 macOS Space 전환은 AppleScript를 통해 수행한다.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("dobby.desktop")

try:
    import yaml
    _YAML_OK = True
except ImportError:
    _YAML_OK = False
    log.warning("pyyaml not installed — using fallback desktop config")


DEFAULT_CONFIG = {
    "desktops": {
        1: {
            "name": "도비일번 메인",
            "project_path": str(Path(__file__).parent),
            "role": "main_control"
        }
    }
}


class DesktopManager:
    """데스크톱/Space와 프로젝트 매핑을 관리한다."""

    def __init__(self, config_path: str = "config/desktops.yaml"):
        self._config_path = Path(config_path)
        self._active_index: int = 1
        self._last_switch_time: float = 0.0
        self._switch_debounce: float = 1.0  # seconds
        self._config: dict = {}
        self._load_config()

    def _load_config(self):
        if _YAML_OK and self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    raw = yaml.safe_load(f)
                # Convert desktop keys to int
                desktops = raw.get("desktops", {})
                self._config = {
                    int(k): v for k, v in desktops.items()
                }
                log.info(f"Loaded desktop config: {len(self._config)} desktops")
                return
            except Exception as e:
                log.warning(f"Failed to load desktop config: {e}")

        self._config = DEFAULT_CONFIG["desktops"]
        log.info("Using default desktop config")

    def reload_config(self):
        self._load_config()

    @property
    def active_index(self) -> int:
        return self._active_index

    def set_active_index(self, index: int):
        self._active_index = index
        log.info(f"Active desktop set to {index}")

    def get_current_project(self) -> Optional[dict]:
        desktop = self._config.get(self._active_index)
        if not desktop:
            return None
        return {
            "index": self._active_index,
            "name": desktop.get("name", f"데스크톱 {self._active_index}"),
            "project_path": desktop.get("project_path", ""),
            "role": desktop.get("role", "development_project"),
        }

    def get_project_by_name(self, name: str) -> Optional[tuple[int, dict]]:
        """프로젝트 이름으로 데스크톱 인덱스와 설정을 찾는다."""
        name_lower = name.lower()
        for idx, desktop in self._config.items():
            desktop_name = desktop.get("name", "").lower()
            project_path = desktop.get("project_path", "").lower()
            project_name = Path(project_path).name.lower() if project_path else ""

            if (name_lower in desktop_name or
                    name_lower in project_name or
                    desktop_name in name_lower or
                    project_name in name_lower):
                return idx, desktop
        return None

    def list_desktops(self) -> list[dict]:
        result = []
        for idx in sorted(self._config.keys()):
            desktop = self._config[idx]
            result.append({
                "index": idx,
                "name": desktop.get("name", f"데스크톱 {idx}"),
                "project_path": desktop.get("project_path", ""),
                "role": desktop.get("role", "development_project"),
                "active": idx == self._active_index,
            })
        return result

    def _can_switch(self) -> bool:
        now = time.time()
        if now - self._last_switch_time < self._switch_debounce:
            return False
        self._last_switch_time = now
        return True

    async def switch_next(self) -> bool:
        """다음 데스크톱/Space로 이동한다 (Control + Right Arrow)."""
        if not self._can_switch():
            return False
        success = await _applescript_key(right=True)
        if success:
            self._active_index += 1
            log.info(f"Switched to next desktop → {self._active_index}")
        return success

    async def switch_previous(self) -> bool:
        """이전 데스크톱/Space로 이동한다 (Control + Left Arrow)."""
        if not self._can_switch():
            return False
        success = await _applescript_key(right=False)
        if success and self._active_index > 1:
            self._active_index -= 1
            log.info(f"Switched to previous desktop → {self._active_index}")
        return success

    async def switch_to(self, index: int) -> bool:
        """특정 데스크톱으로 이동한다 (여러 번 키 시뮬레이션)."""
        if not self._can_switch():
            return False
        diff = index - self._active_index
        if diff == 0:
            return True

        right = diff > 0
        steps = abs(diff)

        for i in range(steps):
            success = await _applescript_key(right=right)
            if not success:
                return False
            await asyncio.sleep(0.3)

        self._active_index = index
        log.info(f"Switched to desktop {index}")
        return True

    async def switch_to_project(self, project_name: str) -> bool:
        """프로젝트 이름으로 데스크톱을 찾아서 이동한다."""
        result = self.get_project_by_name(project_name)
        if not result:
            log.warning(f"Project not found: {project_name}")
            return False
        idx, _ = result
        return await self.switch_to(idx)


async def _applescript_key(right: bool) -> bool:
    """Control + Right/Left Arrow 키를 시뮬레이션한다.
    pyautogui를 우선 사용하고, 실패 시 osascript로 폴백한다.
    """
    loop = asyncio.get_event_loop()

    # 1차 시도: pyautogui (Accessibility 권한 없이도 동작)
    try:
        import pyautogui
        direction = "right" if right else "left"
        await loop.run_in_executor(None, lambda: pyautogui.hotkey("ctrl", direction))
        log.debug(f"pyautogui desktop switch: ctrl+{direction}")
        return True
    except Exception as e:
        log.warning(f"pyautogui key failed: {e}, falling back to osascript")

    # 2차 시도: osascript (Accessibility 권한 필요)
    script = f'''
tell application "System Events"
    key code {124 if right else 123} using {{control down}}
end tell
'''
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.warning(f"AppleScript key failed: {stderr.decode()[:100]}")
            return False
        return True
    except Exception as e:
        log.error(f"AppleScript error: {e}")
        return False
