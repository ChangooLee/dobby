"""
DOBBY tmux Session Manager — per-project Claude Code sessions in tmux.

Each project gets a named tmux session ('dobby_<key>') running
'claude --resume --dangerously-skip-permissions'.

iTerm2 (preferred) or Terminal.app attaches to the session so the user
can see Claude Code working interactively.

DOBBY sends prompts via 'tmux send-keys' and captures the response by:
  1. Recording the scroll position before sending
  2. Waiting for terminal output to stabilize (idle detection)
  3. Capturing new pane content and stripping ANSI escape codes
"""

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path

log = logging.getLogger("dobby.tmux")

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
TMUX_BIN = shutil.which("tmux") or "/opt/homebrew/bin/tmux"


def _key(project_name: str) -> str:
    return project_name.lower().strip().replace(" ", "_").replace("-", "_")


def session_name(project_name: str) -> str:
    return f"dobby_{_key(project_name)}"


# ── low-level tmux helpers ──────────────────────────────────────────────────

async def _tmux(*args, check=False) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(
        TMUX_BIN, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return out.decode(errors="replace"), err.decode(errors="replace"), proc.returncode


async def is_alive(project_name: str) -> bool:
    _, _, rc = await _tmux("has-session", "-t", session_name(project_name))
    return rc == 0


async def _history_size(sname: str) -> int:
    out, _, rc = await _tmux("display-message", "-t", sname, "-p", "#{history_size}")
    try:
        return int(out.strip()) if rc == 0 else 0
    except ValueError:
        return 0


# ── session lifecycle ───────────────────────────────────────────────────────

async def open_session(project_name: str, project_dir: str) -> bool:
    """Create (or recreate) a tmux session running 'claude -c'.

    Uses -c (--continue) instead of --resume to avoid the interactive
    session picker. -c auto-resumes the most recent session for the
    directory without prompting.
    """
    sname = session_name(project_name)

    claude_bin = (
        os.getenv("CLAUDE_BIN")
        or shutil.which("claude")
        or str(Path.home() / ".local" / "bin" / "claude")
    )
    if not Path(claude_bin).exists():
        log.error(f"claude not found: {claude_bin}")
        return False

    # Kill any stale tmux session
    await _tmux("kill-session", "-t", sname)
    await asyncio.sleep(0.2)

    # New detached session, wide enough for Claude Code TUI
    _, err, rc = await _tmux(
        "new-session", "-d",
        "-s", sname,
        "-c", project_dir,
        "-x", "220", "-y", "50",
    )
    if rc != 0:
        log.error(f"tmux new-session failed: {err}")
        return False

    # Try -c (continue) first; fall back to plain claude if no prior session exists
    claude_cmd = f"{claude_bin} -c --dangerously-skip-permissions"
    await _tmux("send-keys", "-t", sname, claude_cmd, "Enter")
    log.info(f"[{project_name}] tmux session '{sname}': {claude_cmd}")

    # Detect "No conversation found" and retry without -c
    await asyncio.sleep(3.0)
    out, _, _ = await _tmux("capture-pane", "-t", sname, "-p")
    if "No conversation found" in out:
        log.info(f"[{project_name}] no prior session — starting fresh claude")
        await _tmux("send-keys", "-t", sname, f"{claude_bin} --dangerously-skip-permissions", "Enter")

    return True


async def attach_in_terminal(project_name: str) -> bool:
    """Open iTerm2 (or Terminal.app) attached to the project's tmux session."""
    import asyncio as _asyncio

    sname = session_name(project_name)
    attach_cmd = f"tmux attach -t {sname}"

    # iTerm2 (preferred — supports native tmux integration)
    iterm_script = f'''
tell application "iTerm"
    activate
    set newWindow to (create window with default profile)
    tell current session of newWindow
        write text "{attach_cmd}"
    end tell
end tell
'''
    proc = await _asyncio.create_subprocess_exec(
        "osascript", "-e", iterm_script,
        stdout=_asyncio.subprocess.PIPE,
        stderr=_asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode == 0:
        log.info(f"[{project_name}] attached in iTerm2")
        return True

    # Fallback to Terminal.app
    log.warning(f"iTerm2 open failed ({err.decode()[:80]}), falling back to Terminal.app")
    term_script = f'''
tell application "Terminal"
    activate
    do script "{attach_cmd}"
end tell
'''
    proc2 = await _asyncio.create_subprocess_exec(
        "osascript", "-e", term_script,
        stdout=_asyncio.subprocess.PIPE,
        stderr=_asyncio.subprocess.PIPE,
    )
    await proc2.communicate()
    log.info(f"[{project_name}] attached in Terminal.app")
    return proc2.returncode == 0


# ── send + capture ──────────────────────────────────────────────────────────

async def send_and_capture(
    project_name: str,
    prompt: str,
    timeout: float = 300.0,
) -> str:
    """Type a prompt into the tmux session and return Claude's response.

    Completion detection: Claude Code returns to empty input prompt (❯ + nbsp)
    after finishing a response. We wait for that state to appear, then
    extract lines prefixed with ⏺ (Claude's response indicator).
    """
    sname = session_name(project_name)

    if not await is_alive(project_name):
        return f"{project_name} 세션이 없습니다, 주인님. 먼저 열어 주세요."

    # Record history size before sending (to extract only new content)
    hist_before = await _history_size(sname)

    # Send the prompt
    await _tmux("send-keys", "-t", sname, prompt, "Enter")
    log.info(f"[{project_name}] → {prompt[:80]}")

    # Wait for Claude Code to finish.
    # Two-phase detection:
    #   Phase 1: wait for a response line (⏺) to appear in scrollback
    #   Phase 2: wait for the empty input prompt (❯\xa0 with nothing after) to appear
    #            *after* the response — meaning Claude is done and waiting.
    loop = asyncio.get_event_loop()
    start = loop.time()
    await asyncio.sleep(3.0)  # give Claude Code time to start processing

    got_response = False
    got_final_marker = False
    stable_done_count = 0
    _FINAL_RE = re.compile(r"✻\s+(Worked|Cogitated|Churned|Misted|Inferred|Crafted|Thought)\s+for")

    while loop.time() - start < timeout:
        await asyncio.sleep(2.0)
        out, _, rc = await _tmux("capture-pane", "-t", sname, "-p", "-S", "-150")
        if rc != 0:
            break
        visible = ANSI_RE.sub("", out)
        lines = visible.splitlines()

        # Phase 1: detect that Claude started responding (⏺ bullet appeared)
        if not got_response:
            if any(l.strip().startswith("⏺") for l in lines):
                got_response = True
                log.info(f"[{project_name}] response started")
            continue

        # Phase 2: wait for final completion marker (all tool calls done)
        # "✳ Worked/Cogitated for Xs" only appears when the FULL response is complete,
        # unlike ❯ which flickers between sub-steps causing premature done detection.
        if not got_final_marker:
            if any(_FINAL_RE.search(l) for l in lines):
                got_final_marker = True
                log.info(f"[{project_name}] final marker seen")
            continue

        # Phase 3: confirm empty input prompt (Claude idle, waiting)
        empty_lines = [l for l in lines if l.strip() in ("❯ ", "❯ ", "❯", "❯ ")]
        if empty_lines:
            our_text_in_input = any(
                prompt[:20].lower() in l.lower()
                for l in lines[-5:]
            )
            if not our_text_in_input:
                stable_done_count += 1
                if stable_done_count >= 2:
                    log.info(f"[{project_name}] Claude Code done (idle)")
                    break
        else:
            stable_done_count = 0

    # Capture the new scrollback content
    hist_after = await _history_size(sname)
    new_lines = max(hist_after - hist_before + 60, 100)
    raw, _, _ = await _tmux("capture-pane", "-t", sname, "-p", "-S", f"-{new_lines}")
    full_text = ANSI_RE.sub("", raw)

    # Extract Claude's response lines (prefixed with ⏺)
    # Also include tool call summaries (lines with ⎿) and plain text responses
    response_lines = []
    in_response = False
    for line in full_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Start collecting after our prompt line
        if not in_response and prompt[:30].lower() in stripped.lower():
            in_response = True
            continue
        if in_response:
            # Stop at next user prompt or status bar
            if stripped.startswith("❯") or "bypass permissions" in stripped:
                break
            response_lines.append(line.rstrip())

    result = "\n".join(response_lines).strip()
    if not result:
        # Fallback: find any ⏺ lines in new content
        bullet_lines = [
            l.strip() for l in full_text.splitlines()
            if l.strip().startswith("⏺") or l.strip().startswith("⎿")
        ]
        result = "\n".join(bullet_lines[-20:]) if bullet_lines else "(응답 없음)"

    log.info(f"[{project_name}] ← {len(result)} chars")
    return result
