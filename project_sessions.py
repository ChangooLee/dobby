"""
DOBBY Project Session Pool — per-project Claude Code session management.

Each project has a terminal_bridge.sh running in its Terminal window.
send() communicates via the named pipe; if the bridge is not running,
falls back to a WorkSession subprocess.
"""

import logging
from pathlib import Path

import bridge_session as _bridge
from work_mode import WorkSession

log = logging.getLogger("dobby.project_sessions")

# project_key (lowercase) → {"dir": str, "session": WorkSession | None}
_pool: dict[str, dict] = {}


async def open_session(project_name: str, project_dir: str) -> None:
    """Record that a project session is open.

    The actual session lives in terminal_bridge.sh; we just note the project_dir
    so fallback WorkSession can use it later if needed.
    """
    key = project_name.lower().strip()
    _pool[key] = {"dir": project_dir, "session": None}
    log.info(f"[{project_name}] session registered: {project_dir}")


async def send(project_name: str, project_dir: str, prompt: str) -> str:
    """Send a prompt and return the full response.

    Routes to terminal_bridge when available, falls back to WorkSession.
    """
    key = project_name.lower().strip()

    # Register project_dir if not yet tracked
    if key not in _pool:
        _pool[key] = {"dir": project_dir, "session": None}

    # Prefer bridge (visible terminal output + capture)
    if _bridge.is_ready(project_name):
        log.info(f"[{project_name}] → bridge: {prompt[:80]}")
        response = await _bridge.send(project_name, prompt)
        log.info(f"[{project_name}] ← {len(response)}자")
        return response

    # Fallback: WorkSession subprocess (silent, no visible terminal)
    log.warning(f"[{project_name}] bridge not ready — using WorkSession fallback")
    entry = _pool[key]
    session = entry.get("session")
    if session is None or not session.active:
        session = WorkSession()
        proj_dir = project_dir or entry.get("dir", "")
        await session.start(proj_dir, project_name)
        _pool[key]["session"] = session

    log.info(f"[{project_name}] → WorkSession: {prompt[:80]}")
    response = await session.send(prompt)
    log.info(f"[{project_name}] ← {len(response)}자")
    return response


def get_active_sessions() -> list[str]:
    active = []
    for key, entry in _pool.items():
        if _bridge.is_ready(key):
            active.append(key)
        elif entry.get("session") and entry["session"].active:
            active.append(key)
    return active


def get_sessions_summary() -> str:
    active = get_active_sessions()
    if not active:
        return "없음"
    return ", ".join(active)
