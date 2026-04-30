"""
DOBBY Action Executor — AppleScript-based system actions.

Execute actions IMMEDIATELY, before generating any LLM response.
Each function returns {"success": bool, "confirmation": str}.
"""

import asyncio
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger("dobby.actions")

DESKTOP_PATH = Path.home() / "Desktop"

# Track open Claude Code Terminal windows: project_name (lowercase) → Terminal window id
_claude_session_windows: dict[str, int] = {}


def get_active_claude_sessions_summary() -> str:
    """Return a one-line summary of open Claude Code sessions for the system prompt."""
    if not _claude_session_windows:
        return "없음"
    return ", ".join(f"{name} (창 #{wid})" for name, wid in _claude_session_windows.items())


async def _mark_terminal_as_dobby(revert_after: float = 5.0):
    """Temporarily set the front Terminal window to Ocean theme, then revert.

    Shows the user DOBBY is active in that terminal. Reverts after revert_after seconds.
    """
    # Save the current profile, switch to Ocean, then revert
    script_save = (
        'tell application "Terminal"\n'
        '    return name of current settings of front window\n'
        'end tell'
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script_save,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        original_profile = stdout.decode().strip()

        # Switch to Ocean
        script_set = (
            'tell application "Terminal"\n'
            '    set current settings of front window to settings set "Ocean"\n'
            'end tell'
        )
        proc2 = await asyncio.create_subprocess_exec(
            "osascript", "-e", script_set,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

        # Schedule revert
        if original_profile and original_profile != "Ocean":
            asyncio.get_event_loop().call_later(
                revert_after,
                lambda: asyncio.ensure_future(_revert_terminal_theme(original_profile))
            )
    except Exception:
        pass


async def _revert_terminal_theme(profile_name: str):
    """Revert a Terminal window back to its original profile."""
    escaped = profile_name.replace('"', '\\"')
    script = (
        'tell application "Terminal"\n'
        f'    set current settings of front window to settings set "{escaped}"\n'
        'end tell'
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    except Exception:
        pass


async def open_terminal(command: str = "") -> dict:
    """Open Terminal.app and optionally run a command. Marks it blue for DOBBY."""
    if command:
        escaped = command.replace('"', '\\"')
        script = (
            'tell application "Terminal"\n'
            "    activate\n"
            f'    do script "{escaped}"\n'
            "end tell"
        )
    else:
        script = (
            'tell application "Terminal"\n'
            "    activate\n"
            "end tell"
        )
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    success = proc.returncode == 0
    if not success:
        log.error(f"open_terminal failed: {stderr.decode()}")
    else:
        await _mark_terminal_as_dobby()
    return {
        "success": success,
        "confirmation": "터미널을 열었습니다, 주인님." if success else "터미널을 여는 데 실패했습니다, 주인님.",
    }


async def open_browser(url: str, browser: str = "chrome") -> dict:
    """Open URL in user's browser (Chrome or Firefox)."""
    escaped_url = url.replace('"', '\\"')

    if browser.lower() == "firefox":
        app_name = "Firefox"
        script = (
            'tell application "Firefox"\n'
            "    activate\n"
            f'    open location "{escaped_url}"\n'
            "end tell"
        )
    else:
        app_name = "Chrome"
        script = (
            'tell application "Google Chrome"\n'
            "    activate\n"
            f'    open location "{escaped_url}"\n'
            "end tell"
        )

    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    success = proc.returncode == 0
    if not success:
        log.error(f"open_browser ({app_name}) failed: {stderr.decode()}")
    return {
        "success": success,
        "confirmation": f"{app_name}에서 열었습니다, 주인님." if success else f"{app_name} 실행 중 문제가 발생했습니다, 주인님.",
    }


# Keep backward compat
async def open_chrome(url: str) -> dict:
    return await open_browser(url, "chrome")


async def open_claude_in_project(project_dir: str, prompt: str, bin_path: str = None) -> dict:
    """Open Terminal, cd to project dir, run Claude Code interactively."""
    import shutil as _shutil
    from pathlib import Path as _Path

    project_dir = str(_Path(project_dir).expanduser().resolve())
    project_key = _Path(project_dir).name.lower()

    if not bin_path:
        bin_path = (
            os.getenv("CLAUDE_BIN")
            or _shutil.which("claude")
            or next(
                (p for p in [
                    "/opt/homebrew/bin/claude",
                    "/usr/local/bin/claude",
                    str(_Path.home() / ".npm-global" / "bin" / "claude"),
                    str(_Path.home() / ".local" / "bin" / "claude"),
                    str(_Path.home() / "bin" / "claude"),
                ] if _Path(p).exists()),
                None
            )
        )
    if not bin_path:
        return {
            "success": False,
            "confirmation": "Claude Code 실행 파일을 찾지 못했습니다. `which claude` 결과를 확인한 뒤 CLAUDE_BIN 환경 변수에 등록해 주세요.",
        }

    safe_dir = project_dir.replace("\\", "\\\\").replace('"', '\\"')
    safe_bin = bin_path.replace("\\", "\\\\").replace('"', '\\"')

    # Open Terminal and return the new window's id for reliable targeting later
    script = (
        'tell application "Terminal"\n'
        "    activate\n"
        f'    set newTab to do script "cd " & quoted form of "{safe_dir}" & " && clear && echo \'◈ DOBBY Claude Code Session\' && {safe_bin} --dangerously-skip-permissions"\n'
        "    delay 0.3\n"
        "    return (id of window of newTab) as string\n"
        "end tell"
    )
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    success = proc.returncode == 0
    if success:
        try:
            wid = int(stdout.decode().strip())
            _claude_session_windows[project_key] = wid
            log.info(f"Opened Claude Code for '{project_key}', Terminal window id={wid}")
        except (ValueError, TypeError):
            log.warning(f"Could not parse Terminal window id: {stdout.decode()!r}")
        await _mark_terminal_as_dobby()
    else:
        log.error(f"open_claude_in_project failed: {stderr.decode()[:200]}")
    return {
        "success": success,
        "confirmation": "Claude Code를 터미널에서 실행했습니다, 주인님."
        if success
        else f"Claude Code 실행에 실패했습니다, 주인님: {stderr.decode()[:100]}",
    }


async def prompt_existing_terminal(project_name: str, prompt: str) -> dict:
    """Send a prompt to an open Claude Code Terminal session via clipboard paste."""
    import subprocess as _subprocess

    project_key = project_name.lower().strip()
    escaped_name = project_name.replace('"', '\\"')

    # Clipboard paste handles Korean and all Unicode (keystroke does not)
    try:
        _subprocess.run(["pbcopy"], input=prompt.encode("utf-8"), check=True, timeout=3)
    except Exception as e:
        log.error(f"pbcopy failed: {e}")
        return {"success": False, "confirmation": "클립보드 복사에 실패했습니다, 주인님."}

    wid = _claude_session_windows.get(project_key)

    if wid:
        # Try stored window id first, fall back to name search
        script = f'''
tell application "Terminal"
    set found to false
    try
        set w to window id {wid}
        set index of w to 1
        activate
        set found to true
    end try
    if not found then
        repeat with w2 in windows
            if name of w2 contains "{escaped_name}" then
                set index of w2 to 1
                activate
                set found to true
                exit repeat
            end if
        end repeat
    end if
    if not found then
        return "NOT_FOUND"
    end if
end tell
delay 0.5
tell application "System Events"
    tell process "Terminal"
        set frontmost to true
        delay 0.2
        keystroke "v" using command down
        delay 0.2
        key code 36
    end tell
end tell
return "OK"
'''
    else:
        script = f'''
set found to false
tell application "Terminal"
    repeat with w in windows
        if name of w contains "{escaped_name}" then
            set index of w to 1
            activate
            set found to true
            exit repeat
        end if
    end repeat
end tell
if not found then
    return "NOT_FOUND"
end if
delay 0.5
tell application "System Events"
    tell process "Terminal"
        set frontmost to true
        delay 0.2
        keystroke "v" using command down
        delay 0.2
        key code 36
    end tell
end tell
return "OK"
'''

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        result = stdout.decode().strip()

        if result == "NOT_FOUND":
            log.warning(f"No terminal window found for: {project_name}")
            return {
                "success": False,
                "confirmation": f"{project_name} 터미널 창을 찾지 못했습니다, 주인님. Claude Code가 열려 있는지 확인해 주세요.",
            }

        success = proc.returncode == 0
        if not success:
            log.error(f"prompt_existing_terminal failed: {stderr.decode()[:200]}")

        return {
            "success": success,
            "confirmation": f"{project_name}에 전달했습니다, 주인님." if success
            else f"{project_name} 터미널에 접근하지 못했습니다, 주인님.",
        }

    except asyncio.TimeoutError:
        return {"success": False, "confirmation": "터미널 접근 시간이 초과되었습니다, 주인님."}
    except Exception as e:
        log.error(f"prompt_existing_terminal failed: {e}")
        return {"success": False, "confirmation": "터미널 접근 중 오류가 발생했습니다, 주인님."}


async def get_chrome_tab_info() -> dict:
    """Read the current Chrome tab's title and URL via AppleScript."""
    script = (
        'tell application "Google Chrome"\n'
        "    set tabTitle to title of active tab of front window\n"
        "    set tabURL to URL of active tab of front window\n"
        '    return tabTitle & "|" & tabURL\n'
        "end tell"
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            result = stdout.decode().strip()
            parts = result.split("|", 1)
            if len(parts) == 2:
                return {"title": parts[0], "url": parts[1]}
        return {}
    except Exception as e:
        log.warning(f"get_chrome_tab_info failed: {e}")
        return {}


async def monitor_build(project_dir: str, ws=None, synthesize_fn=None) -> None:
    """Monitor a Claude Code build for completion. Notify via WebSocket when done."""
    import base64

    output_file = Path(project_dir) / ".dobby_output.txt"
    start = time.time()
    timeout = 600  # 10 minutes

    while time.time() - start < timeout:
        await asyncio.sleep(5)
        if output_file.exists():
            content = output_file.read_text()
            if "--- DOBBY TASK COMPLETE ---" in content:
                log.info(f"Build complete in {project_dir}")
                if ws and synthesize_fn:
                    try:
                        msg = "빌드가 완료되었습니다, 주인님."
                        audio_bytes = await synthesize_fn(msg)
                        if audio_bytes:
                            encoded = base64.b64encode(audio_bytes).decode()
                            await ws.send_json({"type": "status", "state": "speaking"})
                            await ws.send_json({"type": "audio", "data": encoded, "text": msg})
                            await ws.send_json({"type": "status", "state": "idle"})
                    except Exception as e:
                        log.warning(f"Build notification failed: {e}")
                return

    log.warning(f"Build timed out in {project_dir}")


async def execute_action(intent: dict, projects: list = None) -> dict:
    """Route a classified intent to the right action function.

    Args:
        intent: {"action": str, "target": str} from classify_intent()
        projects: list of known project dicts for resolving working dirs

    Returns: {"success": bool, "confirmation": str, "project_dir": str | None}
    """
    action = intent.get("action", "chat")
    target = intent.get("target", "")

    if action == "open_terminal":
        result = await open_terminal("claude --dangerously-skip-permissions")
        result["project_dir"] = None
        return result

    elif action == "browse":
        if target.startswith("http://") or target.startswith("https://"):
            url = target
        else:
            url = f"https://www.google.com/search?q={quote(target)}"

        # Detect which browser user wants
        target_lower = target.lower()
        if "firefox" in target_lower:
            browser = "firefox"
        else:
            browser = "chrome"

        result = await open_browser(url, browser)
        result["project_dir"] = None
        return result

    elif action == "build":
        # Create project folder on Desktop, spawn Claude Code
        project_name = _generate_project_name(target)
        project_dir = str(DESKTOP_PATH / project_name)
        os.makedirs(project_dir, exist_ok=True)
        result = await open_claude_in_project(project_dir, target)
        result["project_dir"] = project_dir
        return result

    else:
        return {"success": False, "confirmation": "", "project_dir": None}


def _generate_project_name(prompt: str) -> str:
    """Generate a kebab-case project folder name from the prompt."""
    # First: check for a quoted name like "tiktok-analytics-dashboard"
    quoted = re.search(r'"([^"]+)"', prompt)
    if quoted:
        name = quoted.group(1).strip()
        # Already kebab-case or close to it
        name = re.sub(r"[^a-zA-Z0-9\s-]", "", name).strip()
        if name:
            return re.sub(r"[\s]+", "-", name.lower())

    # Second: check for "called X" or "named X" pattern
    called = re.search(r'(?:called|named)\s+(\S+(?:[-_]\S+)*)', prompt, re.IGNORECASE)
    if called:
        name = re.sub(r"[^a-zA-Z0-9-]", "", called.group(1))
        if len(name) > 3:
            return name.lower()

    # Fallback: extract meaningful words
    words = re.sub(r"[^a-zA-Z0-9\s]", "", prompt.lower()).split()
    skip = {"a", "the", "an", "me", "build", "create", "make", "for", "with", "and",
            "to", "of", "i", "want", "need", "new", "project", "directory", "called",
            "on", "desktop", "that", "application", "app", "full", "stack", "simple",
            "web", "page", "site", "named"}
    meaningful = [w for w in words if w not in skip and len(w) > 2][:4]
    return "-".join(meaningful) if meaningful else "dobby-project"
