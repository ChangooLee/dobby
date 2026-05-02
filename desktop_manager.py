"""
DOBBY Desktop Manager — yabai 기반 macOS Space 전환 + 상태 조회

yabai -m space --focus N    정확한 Space 이동 (현재 위치 무관)
yabai -m query --spaces     현재 Space 실시간 조회
yabai -m query --windows    각 Space의 iTerm2 창 목록 조회
tmux list-sessions          dobby_* 세션 생존 여부 확인

자동 Space 배정:
  desktops.yaml에 있는 프로젝트 → 고정 Space 사용
  없는 프로젝트 → 빈 Space에 동적 배정 (YAML 미수정, 런타임만)
"""

import asyncio
import json
import logging
import shutil
import subprocess
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
TMUX_BIN  = shutil.which("tmux")  or "/opt/homebrew/bin/tmux"

DEFAULT_CONFIG = {
    "desktops": {
        1: {"name": "DOBBY 메인", "project_path": str(Path(__file__).parent), "role": "main_control"}
    }
}


# ── low-level helpers ─────────────────────────────────────────────────────────

async def _yabai(*args) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(
        YABAI_BIN, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return out.decode(errors="replace"), err.decode(errors="replace"), proc.returncode


async def _native_space_key(right: bool) -> bool:
    """Ctrl+→/← 키 시뮬레이션 — macOS 네이티브 슬라이딩 애니메이션 발동."""
    loop = asyncio.get_event_loop()
    direction = "right" if right else "left"
    try:
        import pyautogui
        await loop.run_in_executor(None, lambda: pyautogui.hotkey("ctrl", direction))
        log.debug(f"native space key: ctrl+{direction}")
        return True
    except Exception as e:
        log.warning(f"pyautogui failed: {e}, trying osascript")
    script = f'tell application "System Events" to key code {124 if right else 123} using {{control down}}'
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        log.warning(f"osascript space key failed: {err.decode()[:80]}")
        return False
    return True


async def _close_mission_control() -> None:
    """Mission Control이 열려 있으면 Escape로 닫는다."""
    script = 'tell application "System Events" to key code 53'  # Escape
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()


async def _tmux_sessions() -> set[str]:
    """현재 살아있는 tmux 세션 이름 집합 (dobby_* 만)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            TMUX_BIN, "list-sessions", "-F", "#{session_name}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        return {s for s in out.decode().splitlines() if s.startswith("dobby_")}
    except Exception:
        return set()


async def _iterm_spaces() -> set[int]:
    """iTerm2 창이 열려 있는 Space 번호 집합 (yabai query --windows)."""
    out, _, rc = await _yabai("-m", "query", "--windows")
    if rc != 0:
        return set()
    try:
        windows = json.loads(out)
        return {
            w["space"]
            for w in windows
            if "iTerm" in w.get("app", "") or "Terminal" in w.get("app", "")
        }
    except Exception:
        return set()


async def _all_spaces() -> list[int]:
    """yabai가 인식하는 모든 Space 번호 목록."""
    out, _, rc = await _yabai("-m", "query", "--spaces")
    if rc != 0:
        return list(range(1, 8))
    try:
        return [s["index"] for s in json.loads(out)]
    except Exception:
        return list(range(1, 8))


# ── session key helper (mirrors tmux_session.py) ──────────────────────────────

def _session_key(project_name: str) -> str:
    return "dobby_" + project_name.lower().strip().replace(" ", "_").replace("-", "_")


# ── DesktopManager ────────────────────────────────────────────────────────────

class DesktopManager:
    def __init__(self, config_path: str = "config/desktops.yaml"):
        self._config_path = Path(config_path)
        self._config: dict[int, dict] = {}        # Space idx → yaml entry
        self._runtime: dict[str, int] = {}        # project_name → Space idx (동적 배정)
        self._last_switch_time: float = 0.0
        self._switch_debounce: float = 0.25
        self._load_config()

    # ── config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        if _YAML_OK and self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    raw = yaml.safe_load(f)
                self._config = {int(k): v for k, v in raw.get("desktops", {}).items()}
                log.info(f"Loaded desktop config: {len(self._config)} desktops")
                return
            except Exception as e:
                log.warning(f"Failed to load desktop config: {e}")
        self._config = DEFAULT_CONFIG["desktops"]

    def reload_config(self):
        self._load_config()

    # ── current Space (live) ──────────────────────────────────────────────────

    async def current_index(self) -> int:
        out, _, rc = await _yabai("-m", "query", "--spaces", "--space")
        if rc == 0:
            try:
                return json.loads(out)["index"]
            except Exception:
                pass
        return 1

    @property
    def active_index(self) -> int:
        """동기 호환용. 정확한 값은 await current_index() 사용."""
        try:
            out = subprocess.check_output(
                [YABAI_BIN, "-m", "query", "--spaces", "--space"],
                timeout=2, stderr=subprocess.DEVNULL,
            )
            return json.loads(out)["index"]
        except Exception:
            return 1

    def set_active_index(self, index: int):
        pass  # yabai가 source of truth

    # ── project lookup ────────────────────────────────────────────────────────

    def get_project_by_name(self, name: str) -> Optional[tuple[int, dict]]:
        """config → runtime 순서로 프로젝트 Space를 찾는다."""
        name_lower = name.lower().strip()

        # 1) desktops.yaml 검색
        for idx, desktop in self._config.items():
            dname   = desktop.get("name", "").lower()
            dpath   = Path(desktop.get("project_path", "")).name.lower()
            if (name_lower in dname or name_lower in dpath or
                    dname in name_lower or dpath in name_lower):
                return idx, desktop

        # 2) 동적 배정 테이블 검색
        key = name_lower.replace("-", "_").replace(" ", "_")
        for proj, idx in self._runtime.items():
            if key in proj or proj in key:
                return idx, {"name": name, "project_path": "", "role": "development_project"}

        return None

    def get_current_project(self) -> Optional[dict]:
        idx = self.active_index
        desktop = self._config.get(idx)
        if not desktop:
            # 동적 배정된 Space인지 확인
            for proj, sidx in self._runtime.items():
                if sidx == idx:
                    return {"index": idx, "name": proj, "project_path": "", "role": "development_project"}
            return None
        return {
            "index": idx,
            "name": desktop.get("name", f"데스크톱 {idx}"),
            "project_path": desktop.get("project_path", ""),
            "role": desktop.get("role", "development_project"),
        }

    def list_desktops(self) -> list[dict]:
        current = self.active_index
        result = []
        for idx in sorted(self._config.keys()):
            d = self._config[idx]
            result.append({
                "index": idx,
                "name": d.get("name", f"데스크톱 {idx}"),
                "project_path": d.get("project_path", ""),
                "role": d.get("role", "development_project"),
                "active": idx == current,
            })
        # 동적 배정 항목 추가
        static_spaces = set(self._config.keys())
        for proj, idx in self._runtime.items():
            if idx not in static_spaces:
                result.append({
                    "index": idx, "name": proj,
                    "project_path": "", "role": "development_project",
                    "active": idx == current,
                })
        return result

    # ── auto Space assignment ─────────────────────────────────────────────────

    async def assign_space(self, project_name: str, project_dir: str = "") -> int:
        """프로젝트에 Space를 배정한다.

        1. desktops.yaml에 이미 매핑 있으면 그 Space 반환.
        2. runtime 테이블에 이미 배정됐으면 그 Space 반환.
        3. 없으면 빈 Space를 자동 탐색:
           - tmux 세션 없는 Space 우선
           - role=misc인 Space 우선 (설정 파일에서)
           - 모자라면 yabai로 새 Space 생성
        """
        # 1) static config
        result = self.get_project_by_name(project_name)
        if result:
            return result[0]

        # 2) runtime cache
        key = project_name.lower().replace("-", "_").replace(" ", "_")
        if key in self._runtime:
            return self._runtime[key]

        # 3) find a free Space
        all_spaces     = await _all_spaces()
        active_sessions = await _tmux_sessions()
        iterm_spaces   = await _iterm_spaces()

        # Spaces already claimed by config or runtime
        claimed = set(self._config.keys()) | set(self._runtime.values())

        # Prefer spaces that are: unclaimed > misc-role > empty (no tmux, no iterm)
        candidates = []
        for sidx in all_spaces:
            if sidx == 1:  # DOBBY 메인은 건드리지 않는다
                continue
            if sidx in claimed:
                continue
            has_tmux   = any(s.startswith("dobby_") for s in active_sessions)  # any session on this space
            has_iterm  = sidx in iterm_spaces
            candidates.append((sidx, has_iterm, has_tmux))

        # Sort: prefer no-iterm, no-tmux first
        candidates.sort(key=lambda x: (x[2], x[1]))

        if candidates:
            chosen = candidates[0][0]
        else:
            # All known spaces claimed — create a new one
            _, _, rc = await _yabai("-m", "space", "--create")
            if rc == 0:
                new_spaces = await _all_spaces()
                chosen = max(new_spaces)
                log.info(f"Created new Space {chosen} for {project_name}")
            else:
                # yabai create failed — use next integer beyond current max
                chosen = (max(all_spaces) if all_spaces else 8) + 1
                log.warning(f"yabai space create failed; using virtual Space {chosen}")

        self._runtime[key] = chosen
        log.info(f"Auto-assigned Space {chosen} to '{project_name}'")
        return chosen

    # ── status query ──────────────────────────────────────────────────────────

    async def get_space_status(self) -> list[dict]:
        """각 Space의 현재 상태를 반환한다.

        반환 항목:
          space       - Space 번호
          name        - 프로젝트 이름 (config 기준)
          role        - main_control / development_project / misc
          tmux_alive  - dobby_<key> 세션이 살아있는지
          has_window  - 해당 Space에 iTerm2 창이 있는지
          is_current  - 현재 포커스된 Space인지
        """
        sessions     = await _tmux_sessions()
        iterm_spaces = await _iterm_spaces()
        current      = await self.current_index()

        status = []
        for idx in sorted(self._config.keys()):
            d    = self._config[idx]
            name = d.get("name", f"데스크톱 {idx}")
            role = d.get("role", "development_project")
            key  = _session_key(name)
            status.append({
                "space":      idx,
                "name":       name,
                "role":       role,
                "tmux_alive": key in sessions,
                "has_window": idx in iterm_spaces,
                "is_current": idx == current,
            })

        # 동적 배정 Space
        for proj, idx in self._runtime.items():
            if idx not in self._config:
                key = _session_key(proj)
                status.append({
                    "space":      idx,
                    "name":       proj,
                    "role":       "development_project",
                    "tmux_alive": key in sessions,
                    "has_window": idx in iterm_spaces,
                    "is_current": idx == current,
                })

        return status

    async def format_status(self) -> str:
        """DOBBY 시스템 프롬프트에 삽입할 한 눈에 보이는 상태 문자열."""
        rows = await self.get_space_status()
        lines = []
        for r in rows:
            if r["role"] == "misc":
                continue
            icon = "▶" if r["is_current"] else " "
            tc   = "✅ Claude Code 실행 중" if r["tmux_alive"] else ("🪟 창만 있음" if r["has_window"] else "❌ 비어있음")
            lines.append(f"  {icon} Space {r['space']} [{r['name']}]: {tc}")
        return "\n".join(lines) if lines else "  (Space 정보 없음)"

    # ── switching ─────────────────────────────────────────────────────────────

    def _can_switch(self) -> bool:
        now = time.time()
        if now - self._last_switch_time < self._switch_debounce:
            return False
        self._last_switch_time = now
        return True

    async def switch_to(self, index: int) -> bool:
        """절대 Space 이동 — yabai 사용 (프로젝트 열기 등 정확한 위치 필요 시).
        Mission Control이 열려 있으면 닫고 재시도한다."""
        if not self._can_switch():
            await asyncio.sleep(self._switch_debounce)
        for attempt in range(2):
            _, err, rc = await _yabai("-m", "space", "--focus", str(index))
            if rc == 0:
                log.info(f"yabai: switched to space {index}")
                await asyncio.sleep(0.25)
                return True
            err_msg = err.strip()
            if "already focused" in err_msg:
                return True
            if "mission-control is active" in err_msg:
                log.info("Mission Control active — closing before space switch")
                await _close_mission_control()
                await asyncio.sleep(0.4)
                continue  # retry
            log.warning(f"yabai space --focus {index} failed: {err_msg}")
            return False
        return False

    async def switch_next(self) -> bool:
        """상대 이동 — Ctrl+→ 네이티브 애니메이션 사용."""
        if not self._can_switch():
            return False
        return await _native_space_key(right=True)

    async def switch_previous(self) -> bool:
        """상대 이동 — Ctrl+← 네이티브 애니메이션 사용."""
        if not self._can_switch():
            return False
        return await _native_space_key(right=False)

    async def switch_to_project(self, project_name: str) -> bool:
        result = self.get_project_by_name(project_name)
        if not result:
            log.warning(f"Project not found: {project_name}")
            return False
        return await self.switch_to(result[0])
