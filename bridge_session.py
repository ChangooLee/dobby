"""
DOBBY Bridge Session — communicate with terminal_bridge.sh via named pipes.

terminal_bridge.sh runs in a Terminal window for each project. It waits for
commands via a FIFO, executes 'claude -p [--continue] "$prompt"', and writes
the full output to a capture file with ===DOBI_DONE=== as the completion marker.

Flow:
  1. open_claude_in_project() launches terminal_bridge.sh in Terminal
  2. bridge.send(project_name, prompt) writes prompt to /tmp/dobi_<id>.cmd
  3. Sends the file path to /tmp/dobi_cmd_<key>_pipe (the bridge reads it)
  4. Bridge runs claude -p, tees output to /tmp/dobi_<id>.out
  5. Bridge appends ===DOBI_DONE=== when done
  6. bridge.send() polls the .out file and returns the captured text
"""

import asyncio
import logging
import uuid
from pathlib import Path

log = logging.getLogger("dobby.bridge_session")

SEND_TIMEOUT = 600.0   # max seconds to wait for claude -p response
PIPE_WAIT_TIMEOUT = 30.0  # max seconds to wait for bridge to start
POLL_INTERVAL = 2.0


def _normalize(project_name: str) -> str:
    return project_name.lower().strip().replace(" ", "_").replace("-", "_")


def pipe_path(project_name: str) -> str:
    return f"/tmp/dobi_cmd_{_normalize(project_name)}_pipe"


def is_ready(project_name: str) -> bool:
    """Return True if the terminal bridge for this project is running."""
    return Path(pipe_path(project_name)).exists()


async def wait_ready(project_name: str, timeout: float = PIPE_WAIT_TIMEOUT) -> bool:
    """Wait until the bridge pipe appears. Returns False on timeout."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if is_ready(project_name):
            return True
        await asyncio.sleep(0.5)
    return False


async def send(project_name: str, prompt: str, timeout: float = SEND_TIMEOUT) -> str:
    """Send a prompt to the running terminal bridge and return the captured response."""
    pipe = pipe_path(project_name)

    # Wait for bridge to start if it was just launched
    if not is_ready(project_name):
        log.info(f"[{project_name}] waiting for bridge to start...")
        ready = await wait_ready(project_name)
        if not ready:
            return (
                f"{project_name} 브리지가 시작되지 않았습니다, 주인님. "
                "먼저 Claude Code를 열어 주세요."
            )

    cmd_id = uuid.uuid4().hex[:12]
    cmd_file = f"/tmp/dobi_{cmd_id}.cmd"
    out_file = f"/tmp/dobi_{cmd_id}.out"

    Path(cmd_file).write_text(prompt, encoding="utf-8")
    log.info(f"[{project_name}] sending prompt ({len(prompt)} chars) → {cmd_file}")

    # Write file path to FIFO — blocks until bridge is in its read loop
    loop = asyncio.get_event_loop()
    try:
        def _write_pipe():
            with open(pipe, "w") as f:
                f.write(cmd_file + "\n")

        await asyncio.wait_for(
            loop.run_in_executor(None, _write_pipe),
            timeout=60.0,  # wait up to 60s for bridge to be ready (may be busy)
        )
    except asyncio.TimeoutError:
        Path(cmd_file).unlink(missing_ok=True)
        log.warning(f"[{project_name}] pipe write timed out — bridge may be busy")
        return f"{project_name} 브리지가 응답하지 않습니다, 주인님. 이전 작업이 진행 중일 수 있습니다."
    except Exception as e:
        Path(cmd_file).unlink(missing_ok=True)
        log.error(f"[{project_name}] pipe write failed: {e}")
        return f"파이프 전송 실패, 주인님: {e}"

    # Poll output file for completion marker
    start = loop.time()
    while loop.time() - start < timeout:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            if Path(out_file).exists():
                content = Path(out_file).read_text(encoding="utf-8", errors="replace")
                if "===DOBI_DONE===" in content:
                    result = content.replace("===DOBI_DONE===", "").strip()
                    Path(out_file).unlink(missing_ok=True)
                    log.info(f"[{project_name}] response received: {len(result)} chars")
                    return result
        except Exception as e:
            log.warning(f"[{project_name}] output file read error: {e}")

    log.error(f"[{project_name}] bridge timeout after {timeout}s")
    return f"{project_name} 작업이 시간 초과되었습니다, 주인님."
