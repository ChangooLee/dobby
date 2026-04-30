"""
DOBBY Desktop Manager — yabai 기반 macOS Space 전환

yabai -m space --focus N  으로 현재 Space에 관계없이 정확히 N번 Space로 이동.
yabai -m query --spaces --space 로 현재 Space를 항상 정확히 읽음.
"""

import asyncio
import logging
import shutil
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("dobby.desktop")

try:
    import yaml
    _YAML_OK = True
except ImportError:
    _YAML_OK = False

YABAI_BIN = shutil.which("yabai") or "/opt/homebrew/bin/yabai"

DEFAULT_CONFIG = {
    "desktops": {
        1: {
            "name": "DOBBY 메인",
            "project_path": str(Path(__file__).parent),
            "role": "main_control"
        }
    }
}


async def _yabai(*args) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(
        YABAI_BIN, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return out.decode(errors="replace"), err.decode(errors="replace"), proc.returncode


class DesktopManager:
    def __init__(self, config_path: str = "config/desktops.yaml"):
        self._config_path = Path(config_path)
        self._config: dict = {}
        self._last_switch_time: float = 0.0
        self._switch_debounce: float = 0.5
        self._load_config()

    def _load_config(self):
        if _YAML_OK and self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    raw = yaml.safe_load(f)
                desktops = raw.get("desktops", {})
                self._config = {int(k): v for k, v in desktops.items()}
                log.info(f"Loaded desktop config: {len(self._config)} desktops")
                return
            except Exception as e:
                log.warning(f"Failed to load desktop config: {e}")
        self._config = DEFAULT_CONFIG["desktops"]
        log.info("Using default desktop config")

    def reload_config(self):
        self._load_config()

    # ── current space (live, from yabai) ──────────────────────────────────────

    async def current_index(self) -> int:
        """yabai로 현재 Space 번호를 정확히 읽는다."""
        import json
        out, _, rc = await _yabai("-m", "query", "--spaces", "--space")
        if rc == 0:
            try:
                return json.loads(out)["index"]
            except Exception:
                pass
        log.warning("yabai space query failed, falling back to 1")
        return 1

    @property
    def active_index(self) -> int:
        """동기 호환용 — 정확한 값이 필요하면 await current_index() 사용."""
        import json, subprocess
        try:
            out = subprocess.check_output(
                [YABAI_BIN, "-m", "query", "--spaces", "--space"],
                timeout=2, stderr=subprocess.DEVNULL
            )
            return json.loads(out)["index"]
        except Exception:
            return 1

    def set_active_index(self, index: int):
        pass  # yabai 사용 시 불필요 — 실제 Space 상태가 source of truth

    # ── config helpers ─────────────────────────────────────────────────────────

    def get_current_project(self) -> Optional[dict]:
        idx = self.active_index
        desktop = self._config.get(idx)
        if not desktop:
            return None
        return {
            "index": idx,
            "name": desktop.get("name", f"데스크톱 {idx}"),
            "project_path": desktop.get("project_path", ""),
            "role": desktop.get("role", "development_project"),
        }

    def get_project_by_name(self, name: str) -> Optional[tuple[int, dict]]:
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
        current = self.active_index
        result = []
        for idx in sorted(self._config.keys()):
            desktop = self._config[idx]
            result.append({
                "index": idx,
                "name": desktop.get("name", f"데스크톱 {idx}"),
                "project_path": desktop.get("project_path", ""),
                "role": desktop.get("role", "development_project"),
                "active": idx == current,
            })
        return result

    # ── switching ──────────────────────────────────────────────────────────────

    def _can_switch(self) -> bool:
        now = time.time()
        if now - self._last_switch_time < self._switch_debounce:
            return False
        self._last_switch_time = now
        return True

    async def switch_to(self, index: int) -> bool:
        """yabai로 지정 Space에 직접 이동 — 현재 위치 무관, 항상 정확."""
        if not self._can_switch():
            await asyncio.sleep(self._switch_debounce)
        _, err, rc = await _yabai("-m", "space", "--focus", str(index))
        if rc != 0:
            log.warning(f"yabai space focus {index} failed: {err.strip()}")
            return False
        log.info(f"yabai: switched to space {index}")
        await asyncio.sleep(0.4)  # Mission Control 애니메이션 대기
        return True

    async def switch_next(self) -> bool:
        current = await self.current_index()
        return await self.switch_to(current + 1)

    async def switch_previous(self) -> bool:
        current = await self.current_index()
        return await self.switch_to(max(1, current - 1))

    async def switch_to_project(self, project_name: str) -> bool:
        result = self.get_project_by_name(project_name)
        if not result:
            log.warning(f"Project not found: {project_name}")
            return False
        idx, _ = result
        return await self.switch_to(idx)
