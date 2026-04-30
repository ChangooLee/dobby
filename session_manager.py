"""
도비 Session Manager

여러 Claude Code 세션을 관리합니다.
- iTerm2 탭: 시각용 (사람이 보는 용도)
- claude -p 서브프로세스: 오디오 캡처용 (TTS로 읽어주는 용도)

세션 전략:
  single   — 특정 세션 하나에 명령
  broadcast — 모든 세션에 동시 전송, 완료 순서대로 읽어줌
  aggregate — 모든 세션 완료 후 Claude Haiku가 요약해서 읽어줌
"""

import asyncio
import logging
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import anthropic

log = logging.getLogger("dobi.sessions")

CLAUDE_BIN = "claude"  # PATH에 있다고 가정
RESPONSE_TIMEOUT = 120  # 초
MAX_TTS_CHARS = 400    # 이 이상은 요약


@dataclass
class SessionResponse:
    session_id: str
    session_name: str
    raw: str
    summary: str
    elapsed: float
    success: bool


@dataclass
class ClaudeSession:
    id: str
    name: str
    project_path: str
    status: Literal["idle", "running", "done", "error"] = "idle"
    last_response: str = ""
    created_at: float = field(default_factory=time.time)
    iterm_window_id: Optional[str] = None


class SessionManager:
    def __init__(self, anthropic_client: anthropic.AsyncAnthropic):
        self._client = anthropic_client
        self._sessions: dict[str, ClaudeSession] = {}

    # ------------------------------------------------------------------
    # 세션 관리
    # ------------------------------------------------------------------

    def list_sessions(self) -> list[ClaudeSession]:
        return list(self._sessions.values())

    def get_session(self, session_id: str) -> Optional[ClaudeSession]:
        return self._sessions.get(session_id)

    def find_by_name(self, name: str) -> Optional[ClaudeSession]:
        name_lower = name.lower()
        for s in self._sessions.values():
            if name_lower in s.name.lower():
                return s
        return None

    async def open_session(self, name: str, project_path: str) -> ClaudeSession:
        """새 Claude Code 세션을 iTerm2에서 엽니다."""
        session_id = str(uuid.uuid4())[:8]
        session = ClaudeSession(
            id=session_id,
            name=name,
            project_path=project_path,
        )
        self._sessions[session_id] = session

        # iTerm2에 새 탭/윈도우 열기
        await self._open_iterm2(session)
        log.info(f"세션 열림: [{session_id}] {name} @ {project_path}")
        return session

    async def _open_iterm2(self, session: ClaudeSession):
        """iTerm2에 Claude Code 탭을 엽니다 (시각용)."""
        script = f'''
tell application "iTerm2"
    activate
    set newWindow to (create window with default profile)
    tell current session of newWindow
        write text "cd '{session.project_path}' && echo '=== 도비 세션: {session.name} ===' && claude"
    end tell
end tell
'''
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        window_id = stdout.decode().strip()
        session.iterm_window_id = window_id

    def close_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            log.info(f"세션 닫힘: {session_id}")

    # ------------------------------------------------------------------
    # 명령 전송
    # ------------------------------------------------------------------

    async def send_command(
        self,
        command: str,
        session_id: Optional[str] = None,
        strategy: Literal["single", "broadcast", "aggregate"] = "single",
    ) -> str:
        """
        명령을 세션에 전송하고, TTS용 응답 문자열을 반환합니다.

        strategy:
          single    — session_id 지정 세션 하나
          broadcast — 모든 세션, 완료 순서대로 TTS
          aggregate — 모든 세션 완료 후 요약 TTS
        """
        if strategy == "single":
            if not session_id:
                # 가장 최근 세션 선택
                if not self._sessions:
                    return "열려있는 세션이 없습니다, 주인님."
                session_id = list(self._sessions.keys())[-1]
            session = self._sessions.get(session_id)
            if not session:
                return f"세션 {session_id}를 찾을 수 없습니다."
            resp = await self._run_claude(session, command)
            return self._format_for_tts(resp)

        elif strategy == "broadcast":
            if not self._sessions:
                return "열려있는 세션이 없습니다, 주인님."
            tasks = [
                self._run_claude(s, command)
                for s in self._sessions.values()
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            parts = []
            for resp in responses:
                if isinstance(resp, SessionResponse) and resp.success:
                    parts.append(f"{resp.session_name}: {self._format_for_tts(resp)}")
            return " — ".join(parts) if parts else "모든 세션에서 응답이 없습니다."

        elif strategy == "aggregate":
            if not self._sessions:
                return "열려있는 세션이 없습니다, 주인님."
            tasks = [
                self._run_claude(s, command)
                for s in self._sessions.values()
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            valid = [r for r in responses if isinstance(r, SessionResponse) and r.success]
            if not valid:
                return "세션들로부터 응답을 받지 못했습니다."
            return await self._aggregate_responses(command, valid)

        return "알 수 없는 전략입니다."

    async def _run_claude(self, session: ClaudeSession, command: str) -> SessionResponse:
        """claude -p 로 명령을 실행하고 응답을 캡처합니다."""
        session.status = "running"
        start = time.time()

        # claude는 VM 기반 바이너리라 shell을 통해야 실행됨
        safe_command = command.replace("'", "'\\''")
        shell_cmd = f"cd {session.project_path!r} && claude -p '{safe_command}'"

        try:
            proc = await asyncio.create_subprocess_exec(
                "/bin/zsh", "-c", shell_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
            )
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=RESPONSE_TIMEOUT
                )
            except asyncio.TimeoutError:
                proc.kill()
                session.status = "error"
                return SessionResponse(
                    session_id=session.id,
                    session_name=session.name,
                    raw="",
                    summary="시간 초과",
                    elapsed=time.time() - start,
                    success=False,
                )

            raw = stdout.decode("utf-8", errors="replace").strip()
            session.last_response = raw
            session.status = "done"

            return SessionResponse(
                session_id=session.id,
                session_name=session.name,
                raw=raw,
                summary="",
                elapsed=time.time() - start,
                success=True,
            )

        except Exception as e:
            session.status = "error"
            log.error(f"claude -p 실패 ({session.name}): {e}")
            return SessionResponse(
                session_id=session.id,
                session_name=session.name,
                raw="",
                summary=str(e),
                elapsed=time.time() - start,
                success=False,
            )

    # ------------------------------------------------------------------
    # TTS 포맷팅 / 요약
    # ------------------------------------------------------------------

    def _format_for_tts(self, resp: SessionResponse) -> str:
        """긴 응답을 TTS에 적합하게 정리합니다."""
        if not resp.success:
            return resp.summary or "오류가 발생했습니다."

        text = resp.raw

        # 코드 블록 제거
        import re
        text = re.sub(r"```[\s\S]*?```", "[코드 블록]", text)
        text = re.sub(r"`[^`]+`", "", text)
        # 마크다운 헤더/불릿 정리
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
        # 연속 공백 정리
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        if len(text) > MAX_TTS_CHARS:
            # 첫 문단만 읽어주고 나머지는 생략
            first_para = text.split("\n\n")[0]
            if len(first_para) > MAX_TTS_CHARS:
                first_para = first_para[:MAX_TTS_CHARS] + "..."
            return first_para + f" (전체 응답은 {resp.session_name} 탭에서 확인하세요.)"

        return text

    async def _aggregate_responses(
        self, original_command: str, responses: list[SessionResponse]
    ) -> str:
        """여러 세션 응답을 Claude Haiku로 요약합니다."""
        combined = "\n\n".join(
            f"=== {r.session_name} ({r.elapsed:.1f}초) ===\n{r.raw[:1000]}"
            for r in responses
        )
        prompt = (
            f"다음은 '{original_command}' 명령에 대한 여러 Claude Code 세션의 응답입니다.\n\n"
            f"{combined}\n\n"
            "위 내용을 2-3문장으로 요약해주세요. 음성으로 읽힐 내용이므로 "
            "마크다운 없이, 간결하게 한국어로 작성하세요."
        )
        try:
            msg = await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            log.error(f"집합 요약 실패: {e}")
            return " / ".join(
                f"{r.session_name}: {r.raw[:100]}" for r in responses
            )
