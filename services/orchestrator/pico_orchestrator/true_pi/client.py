"""JSONL RPC client for ``pi --mode rpc``.

Framing: split on ``\\n`` only (no readline Unicode separators).
Transport is injectable for unit tests (FakeTransport).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pico_orchestrator.true_pi.config import extension_path, pi_bin

logger = logging.getLogger(__name__)

# Isolated PI_CODING_AGENT_DIR filename. Pi 0.73.1 has no --context CLI flag;
# the window is models.json contextWindow (see packages/coding-agent/docs/models.md).
PI_MODELS_JSON = "models.json"
PI_AGENT_HOME_ENV = "PI_CODING_AGENT_DIR"


def true_pi_windows_from_caps(caps: Any | None) -> tuple[int, int]:
    """Lane windows: context window, output cap. Never treat them as the same."""
    thinking = bool(getattr(caps, "thinking_on", False)) if caps is not None else False
    context = int(getattr(caps, "max_context", 0) or 0) if caps is not None else 0
    output = int(getattr(caps, "max_tokens", 0) or 0) if caps is not None else 0
    if context <= 0:
        context = 256_000 if thinking else 128_000
    if output <= 0:
        output = 32_000 if thinking else 8_000
    return context, output


def true_pi_models_document(
    *,
    provider: str,
    model: str,
    max_context: int,
    max_tokens: int,
) -> dict[str, Any]:
    """Pi 0.73.1 models.json overlay. Official path, not a invented CLI flag."""
    name = (provider or "deepseek").strip() or "deepseek"
    mid = (model or "deepseek-v4-flash").strip() or "deepseek-v4-flash"
    overlay = {
        "contextWindow": int(max_context),
        "maxTokens": int(max_tokens),
    }
    return {
        "providers": {
            name: {
                "modelOverrides": {mid: dict(overlay)},
                "models": [
                    {
                        "id": mid,
                        "reasoning": True,
                        "input": ["text"],
                        **overlay,
                    }
                ],
            }
        }
    }


class TruePiClientError(RuntimeError):
    """RPC / process failure (never silent success)."""


@dataclass
class RpcEvent:
    raw: dict[str, Any]

    @property
    def type(self) -> str:
        return str(self.raw.get("type") or "")


class TruePiTransport(ABC):
    """Abstract peer for RPC JSONL."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def send(self, command: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def events(self) -> AsyncIterator[RpcEvent]: ...

    @abstractmethod
    async def close(self, *, kill: bool = True) -> None: ...

    @abstractmethod
    async def wait_response(
        self, command_type: str, *, req_id: str | None = None, timeout: float = 30.0
    ) -> dict[str, Any]: ...


@dataclass
class FakeTransport(TruePiTransport):
    """Deterministic transport for unit tests without a real pi binary."""

    scripted: list[dict[str, Any]] = field(default_factory=list)
    sent: list[dict[str, Any]] = field(default_factory=list)
    assistant_text: str = "已写入 notes.md，请从产物列表下载。"
    _event_q: asyncio.Queue[RpcEvent | None] = field(default_factory=asyncio.Queue)
    _resp_q: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    _closed: bool = False

    async def start(self) -> None:
        for item in self.scripted:
            await self._event_q.put(RpcEvent(item))

    async def send(self, command: Mapping[str, Any]) -> None:
        cmd = dict(command)
        self.sent.append(cmd)
        ctype = str(cmd.get("type") or "")
        req_id = cmd.get("id")
        ack: dict[str, Any] = {
            "type": "response",
            "command": ctype,
            "success": True,
        }
        if req_id is not None:
            ack["id"] = req_id
        if ctype == "get_last_assistant_text":
            ack["data"] = {"text": self.assistant_text}
        await self._resp_q.put(ack)

    async def events(self) -> AsyncIterator[RpcEvent]:
        while True:
            item = await self._event_q.get()
            if item is None:
                return
            yield item

    async def close(self, *, kill: bool = True) -> None:
        del kill
        if not self._closed:
            self._closed = True
            await self._event_q.put(None)

    async def wait_response(
        self, command_type: str, *, req_id: str | None = None, timeout: float = 30.0
    ) -> dict[str, Any]:
        try:
            raw = await asyncio.wait_for(self._resp_q.get(), timeout=timeout)
        except TimeoutError as exc:
            raise TruePiClientError(f"timeout waiting for response {command_type}") from exc
        if raw.get("command") != command_type:
            raise TruePiClientError(f"unexpected response {raw.get('command')} for {command_type}")
        if req_id is not None and raw.get("id") != req_id:
            raise TruePiClientError("response id mismatch")
        return raw


class SubprocessTransport(TruePiTransport):
    """Spawn ``pi --mode rpc`` with isolated session dir and no built-in tools."""

    def __init__(
        self,
        *,
        session_dir: Path,
        tool_url: str,
        tool_token: str,
        run_id: str,
        provider: str = "deepseek",
        model: str = "deepseek-v4-flash",
        thinking: bool = False,
        max_context: int | None = None,
        max_tokens: int | None = None,
        env: Mapping[str, str] | None = None,
        binary: str | None = None,
        ext: Path | None = None,
        extra_extensions: list[Path] | None = None,
        continue_session: bool = False,
        plan_flag: bool = False,
        spawn_cwd: Path | None = None,
    ) -> None:
        self.session_dir = session_dir
        self.tool_url = tool_url
        self.tool_token = tool_token
        self.run_id = run_id
        self.provider = provider
        self.model = model
        self.thinking = thinking
        if max_context is None:
            max_context = 256_000 if thinking else 128_000
        if max_tokens is None:
            max_tokens = 32_000 if thinking else 8_000
        self.max_context = int(max_context)
        self.max_tokens = int(max_tokens)
        self.agent_home: Path | None = None
        self._env_extra = dict(env or {})
        self.binary = binary or pi_bin()
        self.ext = ext or extension_path()
        self.extra_extensions = list(extra_extensions or [])
        self.continue_session = bool(continue_session)
        self.plan_flag = bool(plan_flag)
        self.spawn_cwd = spawn_cwd or session_dir
        self.plan_execute_pending = False
        self._proc: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._queue: asyncio.Queue[RpcEvent | None] = asyncio.Queue()
        self._stderr_tail: list[str] = []

    def models_document(self) -> dict[str, Any]:
        return true_pi_models_document(
            provider=self.provider,
            model=self.model,
            max_context=self.max_context,
            max_tokens=self.max_tokens,
        )

    def prepare_agent_home(self, home: Path | None = None) -> Path:
        """Write isolated models.json so Pi compaction/requests see the lane window."""
        dest = home or (self.session_dir / "pi-agent")
        dest.mkdir(parents=True, exist_ok=True)
        payload = self.models_document()
        (dest / PI_MODELS_JSON).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.agent_home = dest
        return dest

    def spawn_command(self) -> list[str]:
        """Build the pi spawn argv (exposed for unit tests / F1 lock).

        Dual-mode contract: the true_pi kernel must receive the lane's
        thinking flag and the policy model — never a global hardcoded off.
        Context window is not a CLI flag in pi 0.73.1; see prepare_agent_home.
        """
        cmd = [
            self.binary,
            "--mode",
            "rpc",
            "--no-builtin-tools",
            "--no-context-files",
            "--no-extensions",
            "--session-dir",
            str(self.session_dir),
            "--provider",
            self.provider,
            "--model",
            self.model,
            "--thinking",
            "on" if self.thinking else "off",
        ]
        if self.continue_session:
            cmd.append("--continue")
        if self.plan_flag:
            cmd.append("--plan")
        cmd.extend(["-e", str(self.ext)])
        for extra in self.extra_extensions:
            cmd.extend(["-e", str(extra)])
        return cmd

    async def start(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        if not self.ext.is_file():
            raise TruePiClientError(f"true-pi extension missing: {self.ext}")
        env = os.environ.copy()
        env.update(self._env_extra)
        env["PICO_TRUE_PI_TOOL_URL"] = self.tool_url
        env["PICO_TRUE_PI_TOOL_TOKEN"] = self.tool_token
        env["PICO_TRUE_PI_RUN_ID"] = self.run_id
        agent_home = self.prepare_agent_home()
        env[PI_AGENT_HOME_ENV] = str(agent_home)
        cmd = self.spawn_command()
        logger.info(
            "true_pi spawn run_id=%s session_dir=%s bin=%s max_context=%s max_tokens=%s",
            self.run_id,
            self.session_dir,
            self.binary,
            self.max_context,
            self.max_tokens,
        )
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(self.spawn_cwd),
            start_new_session=True,
        )
        self._reader_task = asyncio.create_task(self._read_stdout())
        asyncio.create_task(self._read_stderr())

    async def _reply_extension_ui(self, raw: dict[str, Any]) -> None:
        """RPC dialogs: auto-execute official plan-mode; never hang the agent."""
        method = str(raw.get("method") or "")
        req_id = raw.get("id")
        if method not in {"select", "confirm", "input", "editor"}:
            return
        if method == "select":
            options = raw.get("options") or []
            value = ""
            for opt in options:
                if str(opt).startswith("Execute"):
                    value = str(opt)
                    break
            if not value and options:
                value = str(options[0])
            if value.startswith("Execute"):
                self.plan_execute_pending = True
            await self.send(
                {"type": "extension_ui_response", "id": req_id, "value": value}
            )
            return
        if method == "confirm":
            await self.send(
                {
                    "type": "extension_ui_response",
                    "id": req_id,
                    "confirmed": True,
                }
            )
            return
        await self.send(
            {"type": "extension_ui_response", "id": req_id, "cancelled": True}
        )

    async def _read_stdout(self) -> None:
        assert self._proc and self._proc.stdout
        buf = b""
        try:
            while True:
                chunk = await self._proc.stdout.read(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.rstrip(b"\r")
                    if not line:
                        continue
                    try:
                        obj = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        logger.warning(
                            "true_pi non-json stdout run_id=%s line=%s",
                            self.run_id,
                            line[:200],
                        )
                        continue
                    if isinstance(obj, dict):
                        t = str(obj.get("type") or "?")
                        if t == "extension_ui_request":
                            await self._reply_extension_ui(obj)
                        if t == "message_update":
                            # Streaming deltas carry the FULL accumulated content
                            # (up to ~40KB incl. the tool-call args while the
                            # model streams a large HTML body token-by-token) and
                            # arrive at ~100-400/sec (O(n²) over tokens).
                            # Enqueueing them bloats the RPC queue + the
                            # wait_response pending buffer, buries agent_end
                            # behind the flood, and balloons memory. Nothing
                            # consumes them (map_event + _consume skip them too),
                            # so drop at the source.
                            continue
                        await self._queue.put(RpcEvent(obj))
        finally:
            await self._queue.put(None)

    async def _read_stderr(self) -> None:
        assert self._proc and self._proc.stderr
        while True:
            line = await self._proc.stderr.readline()
            if not line:
                return
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                self._stderr_tail.append(text[-500:])
                if len(self._stderr_tail) > 40:
                    self._stderr_tail = self._stderr_tail[-40:]
                logger.debug("true_pi stderr run_id=%s: %s", self.run_id, text[:300])

    async def send(self, command: Mapping[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise TruePiClientError("process not started")
        line = json.dumps(dict(command), ensure_ascii=False) + "\n"
        self._proc.stdin.write(line.encode("utf-8"))
        await self._proc.stdin.drain()

    async def events(self) -> AsyncIterator[RpcEvent]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    async def wait_response(
        self, command_type: str, *, req_id: str | None = None, timeout: float = 30.0
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + max(1.0, timeout)
        pending: list[RpcEvent] = []
        try:
            while asyncio.get_running_loop().time() < deadline:
                remaining = max(0.05, deadline - asyncio.get_running_loop().time())
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                except TimeoutError as exc:
                    raise TruePiClientError(
                        f"timeout waiting for response {command_type}"
                    ) from exc
                if item is None:
                    raise TruePiClientError(
                        f"process ended before response {command_type}; "
                        f"stderr_tail={self._stderr_tail[-5:]}"
                    )
                raw = item.raw
                if (
                    raw.get("type") == "response"
                    and raw.get("command") == command_type
                    and (req_id is None or raw.get("id") == req_id)
                ):
                    for p in pending:
                        await self._queue.put(p)
                    return raw
                pending.append(item)
            raise TruePiClientError(f"timeout waiting for response {command_type}")
        except Exception:
            for p in pending:
                await self._queue.put(p)
            raise

    async def close(self, *, kill: bool = True) -> None:
        proc = self._proc
        if proc is None:
            return
        if proc.stdin and not proc.stdin.is_closing():
            try:
                proc.stdin.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("true_pi stdin close: %s", type(exc).__name__)
        if kill and proc.returncode is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except TimeoutError:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except TimeoutError:
                    pass
        if self._reader_task:
            self._reader_task.cancel()
        self._proc = None


class TruePiRpcClient:
    """High-level prompt / abort helpers over a transport."""

    def __init__(self, transport: TruePiTransport) -> None:
        self.transport = transport

    async def start(self) -> None:
        await self.transport.start()

    async def prompt(self, message: str, *, req_id: str | None = None) -> dict[str, Any]:
        rid = req_id or f"p-{uuid.uuid4().hex[:10]}"
        await self.transport.send({"id": rid, "type": "prompt", "message": message})
        resp = await self.transport.wait_response("prompt", req_id=rid, timeout=60.0)
        if not resp.get("success"):
            raise TruePiClientError(f"prompt rejected: {resp}")
        return resp

    async def abort(self) -> None:
        rid = f"a-{uuid.uuid4().hex[:8]}"
        try:
            await self.transport.send({"id": rid, "type": "abort"})
            await self.transport.wait_response("abort", req_id=rid, timeout=5.0)
        except TruePiClientError:
            logger.info("true_pi abort response missing (process may be dead)")

    async def get_last_assistant_text(self) -> str:
        rid = f"t-{uuid.uuid4().hex[:8]}"
        await self.transport.send({"id": rid, "type": "get_last_assistant_text"})
        resp = await self.transport.wait_response(
            "get_last_assistant_text", req_id=rid, timeout=15.0
        )
        data = resp.get("data") or {}
        text = data.get("text")
        return str(text or "")

    def events(self) -> AsyncIterator[RpcEvent]:
        return self.transport.events()

    async def close(self, *, kill: bool = True) -> None:
        await self.transport.close(kill=kill)


def scripted_open_domain_success() -> list[dict[str, Any]]:
    """Minimal happy-path event script for matrix tests.

    Mirrors pi 0.73.x: terminal signal is agent_end (willRetry false),
    not always agent_settled.
    """
    return [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {
            "type": "tool_execution_start",
            "toolName": "workspace_write_file",
            "toolCallId": "c1",
            "args": {"title": "notes.md", "content": "hello"},
        },
        {
            "type": "tool_execution_end",
            "toolName": "workspace_write_file",
            "toolCallId": "c1",
            "isError": False,
            "result": {"content": [{"type": "text", "text": '{"title":"notes.md"}'}]},
        },
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "已写入 notes.md，请从产物列表下载。"},
                ],
            },
        },
        {"type": "turn_end", "toolResults": [], "message": {"role": "assistant", "content": "已写入 notes.md，请从产物列表下载。"}},
        {"type": "agent_end", "willRetry": False, "messages": []},
    ]


TransportFactory = Callable[..., TruePiTransport]
