"""True Pi inside a pi-runner workspace container (card #1093).

Thin adapter: the same Pi RPC JSONL as ``SubprocessTransport``, but the
process lives in a gVisor box started by ``services/pi_runner`` and the
stdio travels over one WebSocket. Pi builtins (read/write/edit/bash) are
on inside the box; the host never runs model commands.

The box holds no long-lived secret. It gets two per-run tokens: one for
the model (``OPENAI_API_KEY``) and one for Pico gateway tools. Both only
work through pico-api ``/internal/ws-proxy`` while this run is alive.

Enable with ``PICO_RUNNER_URL`` (+ ``PICO_RUNNER_TOKEN``,
``PICO_RUNNER_PROXY_URL``). Unset = legacy in-process spawn (rollback).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pico_orchestrator.true_pi.client import (
    PI_AGENT_HOME_ENV,
    PI_MODELS_JSON,
    SubprocessTransport,
    TruePiClientError,
    official_compaction_settings,
)

logger = logging.getLogger(__name__)

RUNNER_URL_ENV = "PICO_RUNNER_URL"
RUNNER_TOKEN_ENV = "PICO_RUNNER_TOKEN"
RUNNER_PROXY_URL_ENV = "PICO_RUNNER_PROXY_URL"

WS_ROOT = "/workspace"
WS_AGENT = f"{WS_ROOT}/.pico/agent"
WS_SESSION = f"{WS_ROOT}/.pico/session"
WS_MEMORY = "/memory"
# Where the workspace image keeps services/true_pi_bridge.
WS_BRIDGE = "/opt/pico/true_pi_bridge"

WORKSPACE_SYSTEM = """## Workspace

You have an isolated Linux workspace at `/workspace` with read / write / edit / bash.
- The teacher's attached files for this conversation are in `/workspace/attachments/`.
- Save every file the teacher should receive in `/workspace/outputs/`. Files there are delivered to the teacher when you finish; nothing else is.
- Python 3 with python-docx, openpyxl, python-pptx, pandas, matplotlib and LibreOffice (`soffice`) are installed; you may `pip install` more and use the internet.
- Before you say a file is done, open it again and check it (re-read, render with `soffice --headless --convert-to pdf` or count slides/rows).
- The workspace persists across turns of this conversation, so you can revise earlier files in place.
"""


def runner_enabled(membership_id: str | None = None) -> bool:
    """Runner armed, and (if ``PICO_RUNNER_MEMBERSHIPS`` is set) this member is in it.

    The allowlist is only for staged rollout; empty = everyone.
    """
    if not os.environ.get(RUNNER_URL_ENV, "").strip():
        return False
    raw = os.environ.get("PICO_RUNNER_MEMBERSHIPS", "").strip()
    if not raw:
        return True
    allowed = {m.strip() for m in raw.split(",") if m.strip()}
    return str(membership_id or "") in allowed


def runner_url() -> str:
    return os.environ.get(RUNNER_URL_ENV, "").strip().rstrip("/")


def runner_token() -> str:
    return os.environ.get(RUNNER_TOKEN_ENV, "").strip()


def runner_proxy_url() -> str:
    return os.environ.get(RUNNER_PROXY_URL_ENV, "http://172.30.250.1:18791").strip().rstrip("/")


def _h(value: str, *, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:32]


@dataclass(frozen=True)
class WorkspaceKey:
    school: str
    member: str
    conv: str

    @classmethod
    def for_run(
        cls, *, school_id: str, membership_id: str, conversation_id: str | None, run_id: str
    ) -> WorkspaceKey:
        # Tenant fail-closed: no shared "none" workspace for missing ids.
        if not str(school_id or "").strip() or not str(membership_id or "").strip():
            raise TruePiClientError("workspace needs school and membership")
        # One workspace per conversation; a chat without a conversation id
        # gets a throwaway workspace per run.
        conv = conversation_id or f"run:{run_id}"
        return cls(
            school=_h(school_id, salt="school"),
            member=_h(membership_id, salt="member"),
            conv=_h(conv, salt="conv"),
        )

    def path(self) -> str:
        return f"{self.school}/{self.member}/{self.conv}"

    def as_dict(self) -> dict[str, str]:
        return {"school": self.school, "member": self.member, "conv": self.conv}


# --- per-run proxy registry (pico-api /internal/ws-proxy reads it) ----------


@dataclass
class ProxyEntry:
    run_id: str
    llm_token: str
    llm_upstream: str
    llm_key: str
    tool_url: str
    tool_token: str
    model: str = ""
    # Concurrent model calls one box may hold open through the proxy.
    slots: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(4))


_REGISTRY: dict[str, ProxyEntry] = {}


def register_proxy(entry: ProxyEntry) -> None:
    _REGISTRY[entry.run_id] = entry


def unregister_proxy(run_id: str) -> None:
    _REGISTRY.pop(run_id, None)


def proxy_entry(run_id: str) -> ProxyEntry | None:
    return _REGISTRY.get(run_id)


# --- transport ---------------------------------------------------------------


def _container_ext_path(path: Path) -> str:
    """Map a host services/true_pi_bridge/... path to the image copy."""
    parts = path.resolve().parts
    if "true_pi_bridge" in parts:
        idx = parts.index("true_pi_bridge")
        return "/".join([WS_BRIDGE, *parts[idx + 1 :]])
    raise TruePiClientError(f"extension outside true_pi_bridge: {path.name}")


@dataclass
class RunnerSpec:
    key: WorkspaceKey
    llm_upstream: str
    llm_key: str
    with_memory: bool = False
    attachments: list[tuple[str, bytes]] = field(default_factory=list)


class RunnerTransport(SubprocessTransport):
    """``SubprocessTransport`` whose process is a pi-runner container."""

    def __init__(self, *, runner: RunnerSpec, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runner = runner
        self.llm_token = secrets.token_urlsafe(32)
        self._ws: Any = None
        self._seed: dict[str, str] = {}
        self._exit_code: int | None = None
        # Model traffic goes to the runner proxy, never the real gateway.
        self.base_url = f"{runner_proxy_url()}/l/{self.run_id}/v1"

    # Pi settings live in the box, not on pico-api disk.
    def prepare_agent_home(self, home: Path | None = None) -> Path:
        del home
        models = json.dumps(self.models_document(), ensure_ascii=False, indent=2) + "\n"
        settings = (
            json.dumps(official_compaction_settings(self.max_context), ensure_ascii=False, indent=2)
            + "\n"
        )
        seed = {
            f".pico/agent/{PI_MODELS_JSON}": models,
            ".pico/agent/settings.json": settings,
            ".pi/settings.json": settings,
        }
        system_text = (self.system_prompt_text or "").strip()
        if system_text:
            seed[".pico/agent/SYSTEM.md"] = system_text + "\n"
            seed[".pi/SYSTEM.md"] = system_text + "\n"
        self._seed = seed
        self.agent_home = Path(WS_AGENT)
        return self.agent_home

    def pi_args(self) -> list[str]:
        """Pi argv inside the box: builtins ON, paths in /workspace."""
        from pico_orchestrator.true_pi.config import normalize_pi_thinking_level

        args = [
            "--mode",
            "rpc",
            "--no-context-files",
            "--no-extensions",
            "--session-dir",
            WS_SESSION,
            "--provider",
            self.provider,
            "--model",
            self.model,
            "--thinking",
            normalize_pi_thinking_level(self.thinking_level, thinking=self.thinking),
        ]
        if self.session_file is not None:
            args.extend(["--session", f"{WS_SESSION}/{self.session_file.name}"])
        elif self.continue_session:
            args.append("--continue")
        if self.plan_flag:
            args.append("--plan")
        args.extend(["-e", _container_ext_path(self.ext)])
        for extra in self.extra_extensions:
            args.extend(["-e", _container_ext_path(extra)])
        return args

    def spawn_command(self) -> list[str]:
        return ["pi", *self.pi_args()]

    def container_env(self) -> dict[str, str]:
        env = {
            "PICO_TRUE_PI_TOOL_URL": f"{runner_proxy_url()}/t/{self.run_id}",
            "PICO_TRUE_PI_TOOL_TOKEN": self.tool_token,
            "PICO_TRUE_PI_RUN_ID": self.run_id,
            "OPENAI_API_KEY": self.llm_token,
            PI_AGENT_HOME_ENV: WS_AGENT,
        }
        visible = str(self._env_extra.get("PICO_TRUE_PI_VISIBLE_TOOLS") or "")
        if visible:
            env["PICO_TRUE_PI_VISIBLE_TOOLS"] = visible
        if self.runner.with_memory:
            env["PI_MEMORY_DIR"] = WS_MEMORY
            env["PI_AUTOCOMMIT"] = "0"
        return env

    def _headers(self) -> dict[str, str]:
        return {"x-pico-runner-token": runner_token()}

    async def upload_attachments(self) -> None:
        if not self.runner.attachments:
            return
        import httpx

        base = f"{runner_url()}/v1/ws/{self.runner.key.path()}/file"
        async with httpx.AsyncClient(timeout=120.0) as client:
            for name, data in self.runner.attachments:
                safe = _safe_name(name)
                resp = await client.put(
                    base, params={"path": f"attachments/{safe}"}, content=data, headers=self._headers()
                )
                if resp.status_code >= 400:
                    raise TruePiClientError(f"attachment upload failed ({resp.status_code})")

    async def start(self) -> None:
        from websockets.asyncio.client import connect

        if not self._seed:
            self.prepare_agent_home()
        register_proxy(
            ProxyEntry(
                run_id=self.run_id,
                llm_token=self.llm_token,
                llm_upstream=self.runner.llm_upstream,
                llm_key=self.runner.llm_key,
                tool_url=self.tool_url,
                tool_token=self.tool_token,
                model=self.model,
            )
        )
        try:
            await self.upload_attachments()
        except Exception:
            unregister_proxy(self.run_id)
            raise
        ws_url = runner_url().replace("http://", "ws://").replace("https://", "wss://")
        try:
            self._ws = await connect(
                f"{ws_url}/v1/session",
                additional_headers=self._headers(),
                max_size=32 * 1024 * 1024,
                open_timeout=20,
                ping_interval=20,
                ping_timeout=60,
            )
        except Exception as exc:
            unregister_proxy(self.run_id)
            raise TruePiClientError(f"runner unreachable ({type(exc).__name__})") from exc
        await self._ws.send(
            json.dumps(
                {
                    "type": "start",
                    "run_id": self.run_id,
                    "key": self.runner.key.as_dict(),
                    "args": self.pi_args(),
                    "env": self.container_env(),
                    "files": self._seed,
                    "memory": self.runner.with_memory,
                }
            )
        )
        first = json.loads(await asyncio.wait_for(self._ws.recv(), timeout=60))
        if first.get("type") != "ready":
            await self._ws.close()
            unregister_proxy(self.run_id)
            raise TruePiClientError(
                f"runner refused: {first.get('code') or first.get('type')}"
            )
        logger.info(
            "true_pi runner start run_id=%s ws=%s", self.run_id, self.runner.key.path()[:24]
        )
        self._reader_task = asyncio.create_task(self._read_ws())

    async def _read_ws(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "out":
                    line = str(msg.get("line") or "").strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("true_pi runner non-json run_id=%s", self.run_id)
                        continue
                    if isinstance(obj, dict):
                        await self._ingest_rpc(obj)
                elif t == "err":
                    text = str(msg.get("line") or "")[-500:]
                    if text:
                        self._stderr_tail.append(text)
                        self._stderr_tail = self._stderr_tail[-40:]
                elif t == "error":
                    self._stderr_tail.append(f"runner: {msg.get('code')}: {msg.get('message')}")
                    await self._queue.put(
                        _runner_error_event(str(msg.get("code") or ""), str(msg.get("message") or ""))
                    )
                elif t == "exit":
                    # Keep reading: the runner closes the socket only after the
                    # container is gone, which is when outputs may be read.
                    self._exit_code = msg.get("code")
        except Exception as exc:  # noqa: BLE001 — connection drop ends the stream
            logger.info("true_pi runner stream ended run_id=%s (%s)", self.run_id, type(exc).__name__)
        finally:
            await self._queue.put(None)
            await self._resp_q.put({"type": "response", "command": "", "_eof": True})

    async def send(self, command: Mapping[str, Any]) -> None:
        if self._ws is None:
            raise TruePiClientError("runner session not started")
        if str(command.get("type") or "") == "prompt":
            self._stream_seen = 0
            self._think_seen = 0
        await self._ws.send(
            json.dumps({"type": "in", "line": json.dumps(dict(command), ensure_ascii=False)})
        )

    async def close(self, *, kill: bool = True) -> None:
        ws = self._ws
        if ws is None:
            unregister_proxy(self.run_id)
            return
        # stdin EOF lets Pi flush the session jsonl; then drop the socket,
        # which makes the runner kill + remove the container.
        with contextlib.suppress(Exception):
            await ws.send(json.dumps({"type": "close"}))
        # Wait for the runner to close the socket (= box stopped and removed).
        # Pi exits on stdin EOF; if it does not, dropping the socket makes the
        # runner kill it, and we still wait for that close.
        if self._reader_task is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(asyncio.shield(self._reader_task), timeout=5.0)
            if not self._reader_task.done():
                with contextlib.suppress(Exception):
                    await ws.close()
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(asyncio.shield(self._reader_task), timeout=45.0)
        with contextlib.suppress(Exception):
            await ws.close()
        if self._reader_task is not None:
            self._reader_task.cancel()
        self._ws = None
        unregister_proxy(self.run_id)


def _runner_error_event(code: str, message: str):
    from pico_orchestrator.true_pi.client import RpcEvent

    # Surfaces as an agent-level error so the run fails in teacher words.
    return RpcEvent(
        {
            "type": "agent_end",
            "messages": [
                {
                    "role": "assistant",
                    "stopReason": "error",
                    "errorMessage": message or code,
                    "content": [],
                }
            ],
        }
    )


def _safe_name(name: str) -> str:
    base = os.path.basename(str(name or "").replace("\\", "/")).strip() or "file"
    cleaned = "".join(ch for ch in base if ch not in '\x00/:*?"<>|').strip(". ")
    return (cleaned or "file")[:180]


# --- outputs → Pico ledger -----------------------------------------------------


async def list_outputs(key: WorkspaceKey) -> dict[str, dict[str, Any]]:
    """{path: {sha256, mtime, size}} of regular files under outputs/.

    The runner refuses (409) while a box is still running on the workspace;
    the box of this turn is being stopped, so wait briefly for it.
    """
    import httpx

    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(40):
            resp = await client.get(
                f"{runner_url()}/v1/ws/{key.path()}/outputs",
                headers={"x-pico-runner-token": runner_token()},
            )
            if resp.status_code != 409:
                break
            await asyncio.sleep(0.5 if attempt < 10 else 2.0)
    if resp.status_code != 200:
        raise TruePiClientError(f"runner outputs failed ({resp.status_code})")
    rows = resp.json().get("files") or []
    return {str(r["path"]): r for r in rows if r.get("path")}


async def fetch_output(key: WorkspaceKey, path: str) -> bytes:
    import httpx

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(
            f"{runner_url()}/v1/ws/{key.path()}/file",
            params={"path": path},
            headers={"x-pico-runner-token": runner_token()},
        )
    if resp.status_code != 200:
        raise TruePiClientError(f"runner file failed ({resp.status_code})")
    return resp.content


def output_kind(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    return ext or "bin"


async def land_outputs(
    *,
    key: WorkspaceKey,
    before: Mapping[str, Any] | None,
    since: float,
    artifact_store: Any,
    principal: Any,
) -> list[tuple[str, dict[str, Any]]]:
    """Write new/changed outputs into the ledger. Returns tool-style results.

    ``before`` is the pre-turn listing; if it could not be taken, only files
    modified since ``since`` count, so old files never pose as this turn's.
    """
    from pico_orchestrator.artifact_types import is_valid_ooxml_package, title_protected_extension

    after = await list_outputs(key)
    results: list[tuple[str, dict[str, Any]]] = []
    for path, row in sorted(after.items()):
        sha = str(row.get("sha256") or "")
        if before is not None:
            prev = before.get(path)
            if prev is not None and str(prev.get("sha256") or "") == sha:
                continue
        elif float(row.get("mtime") or 0) < since:
            continue
        title = os.path.basename(path)
        try:
            raw = await fetch_output(key, path)
        except TruePiClientError as exc:
            results.append(("workspace_output", {"title": title, "error": str(exc)}))
            continue
        protected = title_protected_extension(title)
        if protected in {".docx", ".xlsx", ".pptx"} and not is_valid_ooxml_package(raw, protected):
            results.append(
                ("workspace_output", {"title": title, "error": f"{title} 不是有效的 {protected} 文件"})
            )
            continue
        if artifact_store is None:
            continue
        written = await artifact_store.write(principal, title=title, content=raw, kind=output_kind(path))
        results.append(
            ("workspace_output", {**written, "title": title, "bytes": len(raw), "via": "workspace"})
        )
    return results
