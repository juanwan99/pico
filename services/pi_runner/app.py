"""pi-runner: per-session workspace containers for true Pi (card #1093).

Two listeners, one process:

* control (127.0.0.1:18790, pico-api only, ``X-Pico-Runner-Token``):
  WebSocket ``/v1/session`` pipes Pi RPC stdio of one container (when the
  runner is full the request waits in line and gets ``queued`` frames); file
  upload (attachments) / listing + download (outputs) — only while no box
  is running on that workspace.
* proxy (pico-ws gateway IP:18791, workspace containers only): forwards a
  fixed list of paths — model ``/l/<run>/v1/{chat/completions,responses,models}``
  and gateway tools ``/t/<run>/v1/tool`` — to pico-api's token-checked
  ``/internal/ws-proxy``. The only internal address a box can reach.

Not an orchestrator: Pi is the kernel, pico-api owns the ledger. The
runner only starts/stops containers and moves bytes. It runs as root with
the docker socket, so every workspace file access goes through ``fsafe``.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
import os
import shutil
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse

from pi_runner import fsafe
from pi_runner.policy import (
    DOWNLOAD_PREFIXES,
    SEED_PREFIXES,
    UPLOAD_PREFIXES,
    PolicyError,
    RunnerSettings,
    WorkspaceKey,
    container_name,
    docker_run_argv,
    filter_env,
    mem_available_mb,
    queue_order,
    safe_relpath,
    validate_pi_args,
    validate_run_id,
    write_resolv_conf,
)

logger = logging.getLogger("pi_runner")

MAX_UPLOAD = 100 * 1024 * 1024
MAX_OUTPUT_FILE = 60 * 1024 * 1024
MAX_OUTPUT_FILES = 200
MAX_OUTPUT_TOTAL = 200 * 1024 * 1024
# Pi RPC lines can carry a whole transcript (agent_end); stderr never needs much.
MAX_LINE = 16 * 1024 * 1024
MAX_ERR_LINE = 8 * 1024
MAX_PROXY_BODY = 16 * 1024 * 1024
PROXY_PER_RUN = 4
WATCH_EVERY_S = 5
# A queued request re-checks room this often (host memory frees without an
# event) and tells pico-api it is still in line at least every QUEUE_PING_S.
QUEUE_TICK_S = 2.0
QUEUE_PING_S = 15.0

MODEL_PATHS = frozenset({"v1/chat/completions", "v1/responses", "v1/models"})
TOOL_PATHS = frozenset({"v1/tool", "health"})


@dataclass
class Session:
    run_id: str
    key: WorkspaceKey
    proc: asyncio.subprocess.Process
    started: float = field(default_factory=time.monotonic)
    proxy_slots: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(PROXY_PER_RUN))
    proxy_waiting: int = 0


@dataclass(eq=False)
class Waiter:
    """One start request waiting for room (or holding a granted slot)."""

    key: WorkspaceKey
    since: float = field(default_factory=time.monotonic)
    granted: asyncio.Event = field(default_factory=asyncio.Event)


class Runner:
    def __init__(self, settings: RunnerSettings) -> None:
        self.settings = settings
        with contextlib.suppress(OSError):
            write_resolv_conf(settings)
        self.sessions: dict[str, Session] = {}
        # In line, and granted but not yet a session (a slot is held for them).
        self.waiting: list[Waiter] = []
        self.granted: list[Waiter] = []
        self.lock = asyncio.Lock()

    def busy(self, key: WorkspaceKey) -> bool:
        return any(s.key == key for s in self.sessions.values())

    # --- tenancy / capacity -------------------------------------------------

    def free_mb(self) -> int:
        root = self.settings.workspace_root
        root.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(root).free // (1024 * 1024)

    def avail_mb(self) -> int | None:
        try:
            with open("/proc/meminfo", encoding="ascii") as fh:
                return mem_available_mb(fh.read())
        except OSError:
            return None

    def _refuse_now(self, key: WorkspaceKey) -> None:
        """Reasons waiting cannot fix. Caller holds ``self.lock``."""
        if self.busy(key) or any(w.key == key for w in (*self.waiting, *self.granted)):
            # One box per workspace: no second box racing the first one's files.
            raise PolicyError("runner.workspace_busy", "这个对话上一轮还在运行，请等它结束再发。")
        if self.free_mb() < self.settings.min_free_mb:
            raise PolicyError("runner.disk_full", "服务器磁盘空间不足，暂时不能开工作区。")
        if len(self.waiting) >= self.settings.queue_max and not self._room():
            raise PolicyError("runner.busy", "排队的任务太多，请稍后再试。")

    def _held_schools(self) -> list[str]:
        return [s.key.school for s in self.sessions.values()] + [w.key.school for w in self.granted]

    def _room(self) -> bool:
        """Room for one more box anywhere (count ceiling + host memory floor)."""
        if len(self._held_schools()) >= self.settings.max_sessions:
            return False
        avail = self.avail_mb()
        return avail is None or avail >= self.settings.min_avail_mb

    def _school_room(self, school: str) -> bool:
        cap = self.settings.max_per_school
        return cap <= 0 or self._held_schools().count(school) < cap

    def _order(self) -> list[Waiter]:
        active: dict[str, int] = {}
        for school in self._held_schools():
            active[school] = active.get(school, 0) + 1
        idx = queue_order([(w.key.school, w.since) for w in self.waiting], active)
        return [self.waiting[i] for i in idx]

    def pump(self) -> None:
        """Grant held slots to waiters in fair order. Caller holds ``self.lock``."""
        while self.waiting and self._room():
            nxt = next((w for w in self._order() if self._school_room(w.key.school)), None)
            if nxt is None:
                return
            self.waiting.remove(nxt)
            self.granted.append(nxt)
            nxt.granted.set()

    async def admit(
        self, key: WorkspaceKey, on_queued: Callable[[int], Awaitable[None]] | None = None
    ) -> Waiter:
        """Hold a slot for ``key``; wait in line while the runner is full."""
        settings = self.settings
        async with self.lock:
            self._refuse_now(key)
            waiter = Waiter(key=key)
            self.waiting.append(waiter)
        deadline = time.monotonic() + settings.queue_wait_s
        told: int | None = None
        told_at = 0.0
        try:
            while True:
                async with self.lock:
                    self.pump()
                    if waiter.granted.is_set():
                        return waiter
                    ahead = self._order().index(waiter)
                now = time.monotonic()
                if now >= deadline:
                    raise PolicyError("runner.busy", "排队太久，请稍后再试。")
                if on_queued is not None and (ahead != told or now - told_at >= QUEUE_PING_S):
                    await on_queued(ahead)
                    told, told_at = ahead, now
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(waiter.granted.wait(), timeout=QUEUE_TICK_S)
        except BaseException:
            await self.release(waiter)
            raise

    async def release(self, waiter: Waiter) -> None:
        """Give back a queue place or a granted slot that never became a box."""
        async with self.lock:
            if waiter in self.waiting:
                self.waiting.remove(waiter)
            if waiter in self.granted:
                self.granted.remove(waiter)
            self.pump()

    def prepare_workspace(self, key: WorkspaceKey, *, with_memory: bool) -> Path:
        root = self.settings.workspace_root
        root.mkdir(parents=True, exist_ok=True)
        # Tenant levels are runner-owned; only the leaf belongs to the box.
        for d in (root / key.school, root / key.school / key.member):
            d.mkdir(mode=0o711, exist_ok=True)
        ws = key.workspace_dir(root)
        ws.mkdir(mode=0o755, exist_ok=True)
        with contextlib.suppress(OSError):
            os.lchown(ws, fsafe.WS_UID, fsafe.WS_UID)
        for sub in ("attachments", "outputs", ".pico/agent", ".pico/session", ".pi"):
            fsafe.ensure_dirs(ws, sub)
        if with_memory:
            mem = key.memory_dir(root)
            mem.mkdir(mode=0o755, exist_ok=True)
            with contextlib.suppress(OSError):
                os.lchown(mem, fsafe.WS_UID, fsafe.WS_UID)
        os.utime(ws)
        return ws

    def seed_files(self, ws: Path, files: dict[str, str] | None) -> None:
        for rel, text in (files or {}).items():
            path = safe_relpath(rel, prefixes=SEED_PREFIXES)
            fsafe.write_file(ws, path, str(text).encode("utf-8"))

    # --- container ------------------------------------------------------------

    async def start(
        self, spec: dict[str, Any], on_queued: Callable[[int], Awaitable[None]] | None = None
    ) -> Session:
        run_id = validate_run_id(str(spec.get("run_id") or ""))
        raw_key = spec.get("key") or {}
        key = WorkspaceKey.parse(
            str(raw_key.get("school") or ""),
            str(raw_key.get("member") or ""),
            str(raw_key.get("conv") or ""),
        )
        pi_args = validate_pi_args(spec.get("args"))
        env = filter_env(spec.get("env"))
        with_memory = bool(spec.get("memory"))
        member_dir = self.settings.workspace_root / key.school / key.member
        cap = self.settings.member_max_mb * 1024 * 1024
        member_used, _ = await asyncio.to_thread(fsafe.usage, [member_dir], stop_after_bytes=cap)
        if member_used > self.settings.member_max_mb * 1024 * 1024:
            raise PolicyError("runner.member_quota", "你的工作区总容量已满，请删掉旧对话后再试。")
        if run_id in self.sessions:
            raise PolicyError("runner.duplicate", "run already has a session")
        waiter = await self.admit(key, on_queued)
        try:
            return await self._spawn(run_id, key, pi_args, env, with_memory, spec.get("files"), waiter)
        except BaseException:
            await self.release(waiter)
            raise

    async def _spawn(
        self,
        run_id: str,
        key: WorkspaceKey,
        pi_args: list[str],
        env: dict[str, str],
        with_memory: bool,
        files: dict[str, str] | None,
        waiter: Waiter,
    ) -> Session:
        async with self.lock:
            if run_id in self.sessions:
                raise PolicyError("runner.duplicate", "run already has a session")
            ws = await asyncio.to_thread(self.prepare_workspace, key, with_memory=with_memory)
            await asyncio.to_thread(self.seed_files, ws, files)
            # Tokens go through a 0600 env-file, never argv (argv shows in ps).
            fd, env_path = tempfile.mkstemp(prefix="pico-ws-env-")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for k, v in env.items():
                    fh.write(f"{k}={v}\n")
            argv = docker_run_argv(
                self.settings,
                run_id=run_id,
                key=key,
                pi_args=pi_args,
                env_file=Path(env_path),
                with_memory=with_memory,
            )
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    limit=MAX_LINE,
                )
            finally:
                # docker reads --env-file before the container starts.
                asyncio.get_running_loop().call_later(10.0, _unlink_quiet, env_path)
            session = Session(run_id=run_id, key=key, proc=proc)
            # The held slot becomes this session in one step under the lock.
            self.granted.remove(waiter)
            self.sessions[run_id] = session
        logger.info("ws start run=%s school=%s runtime=%s", run_id, key.school[:8], self.settings.runtime)
        return session

    async def stop(self, session: Session) -> None:
        proc = session.proc
        name = container_name(session.run_id)
        if proc.returncode is None:
            with contextlib.suppress(Exception):
                await _docker("kill", name, timeout=15)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(proc.wait(), timeout=10)
            if proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(proc.wait(), timeout=5)
        # The CLI exiting is not proof: hold the session (busy gate, capacity)
        # until dockerd no longer has the container.
        for _ in range(30):
            if not await _container_exists(name):
                break
            with contextlib.suppress(Exception):
                await _docker("rm", "-f", name, timeout=15)
            await asyncio.sleep(1)
        # Container is gone before the workspace is released for file access.
        async with self.lock:
            self.sessions.pop(session.run_id, None)
            self.pump()
        logger.info(
            "ws stop run=%s code=%s wall=%.0fs",
            session.run_id,
            proc.returncode,
            time.monotonic() - session.started,
        )

    # --- housekeeping ---------------------------------------------------------

    def over_limits(self, session: Session) -> str | None:
        root = self.settings.workspace_root
        paths = [session.key.workspace_dir(root)]
        mem = session.key.memory_dir(root)
        if mem.is_dir():
            paths.append(mem)
        used, count = fsafe.usage(paths)
        if used > self.settings.workspace_max_mb * 1024 * 1024:
            return "工作区超过容量上限，已停止。"
        if count > self.settings.workspace_max_files:
            return "工作区文件数超过上限，已停止。"
        if self.free_mb() < self.settings.min_free_mb // 2:
            return "服务器磁盘空间不足，已停止。"
        if time.monotonic() - session.started > self.settings.max_session_s:
            return "工作区运行时间超过上限，已停止。"
        return None

    def sweep_expired(self) -> int:
        root = self.settings.workspace_root
        if not root.is_dir():
            return 0
        cutoff = time.time() - self.settings.ttl_days * 86400
        active = {s.key.workspace_dir(root) for s in self.sessions.values()}
        removed = 0
        for school in root.iterdir():
            if not school.is_dir() or school.is_symlink():
                continue
            for member in school.iterdir():
                if not member.is_dir() or member.is_symlink():
                    continue
                for conv in member.iterdir():
                    if conv.is_symlink() or not conv.is_dir() or conv.name == "_memory" or conv in active:
                        continue
                    with contextlib.suppress(OSError):
                        if conv.stat().st_mtime < cutoff:
                            shutil.rmtree(conv, ignore_errors=True)
                            removed += 1
        return removed


async def _docker(*args: str, timeout: float) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        return 124, ""
    return proc.returncode or 0, out.decode("utf-8", errors="replace")


async def _container_exists(name: str) -> bool:
    code, out = await _docker("ps", "-aq", "--filter", f"name=^{name}$", timeout=15)
    return code != 0 or bool(out.strip())


def _unlink_quiet(path: str) -> None:
    with contextlib.suppress(OSError):
        os.unlink(path)


def _authorized(settings: RunnerSettings, value: str | None) -> bool:
    return bool(value) and hmac.compare_digest(str(value), settings.token)


def _deny(code: str, status: int) -> JSONResponse:
    return JSONResponse({"ok": False, "code": code}, status_code=status)


def build_control_app(runner: Runner) -> FastAPI:
    settings = runner.settings
    app = FastAPI(title="pi-runner control", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "sessions": len(runner.sessions),
            "max_sessions": settings.max_sessions,
            "queued": len(runner.waiting),
            "mem_available_mb": runner.avail_mb(),
            "image": settings.image,
            "runtime": settings.runtime,
        }

    def _gate(request: Request, school: str, member: str, conv: str) -> WorkspaceKey | JSONResponse:
        if not _authorized(settings, request.headers.get("x-pico-runner-token")):
            return _deny("auth.denied", 401)
        try:
            key = WorkspaceKey.parse(school, member, conv)
        except PolicyError as exc:
            return _deny(exc.code, 400)
        if runner.busy(key):
            # Files are only touched while no box can race them.
            return _deny("runner.workspace_busy", 409)
        return key

    @app.put("/v1/ws/{school}/{member}/{conv}/file")
    async def put_file(school: str, member: str, conv: str, path: str, request: Request):
        key = _gate(request, school, member, conv)
        if isinstance(key, JSONResponse):
            return key
        try:
            rel = safe_relpath(path, prefixes=UPLOAD_PREFIXES)
        except PolicyError as exc:
            return _deny(exc.code, 400)
        body = await read_capped(request, MAX_UPLOAD)
        if body is None:
            return _deny("runner.too_large", 413)
        try:
            ws = await asyncio.to_thread(runner.prepare_workspace, key, with_memory=False)
            await asyncio.to_thread(fsafe.write_file, ws, rel, body)
        except OSError:
            return _deny("runner.bad_path", 400)
        return {"ok": True, "path": str(rel), "bytes": len(body)}

    @app.get("/v1/ws/{school}/{member}/{conv}/outputs")
    async def list_outputs(school: str, member: str, conv: str, request: Request):
        key = _gate(request, school, member, conv)
        if isinstance(key, JSONResponse):
            return key
        ws = key.workspace_dir(settings.workspace_root)
        if not ws.is_dir():
            return {"ok": True, "files": [], "truncated": False}
        rows, truncated = await asyncio.to_thread(
            fsafe.list_regular,
            ws,
            "outputs",
            max_files=MAX_OUTPUT_FILES,
            max_total=MAX_OUTPUT_TOTAL,
            max_file=MAX_OUTPUT_FILE,
        )
        return {"ok": True, "files": [r.__dict__ for r in rows], "truncated": truncated}

    @app.get("/v1/ws/{school}/{member}/{conv}/file")
    async def get_file(school: str, member: str, conv: str, path: str, request: Request):
        key = _gate(request, school, member, conv)
        if isinstance(key, JSONResponse):
            return key
        try:
            rel = safe_relpath(path, prefixes=DOWNLOAD_PREFIXES)
        except PolicyError as exc:
            return _deny(exc.code, 400)
        ws = key.workspace_dir(settings.workspace_root)
        try:
            data = await asyncio.to_thread(fsafe.read_file, ws, rel, max_bytes=MAX_OUTPUT_FILE)
        except FileNotFoundError:
            return _deny("runner.not_found", 404)
        except OSError:
            return _deny("runner.bad_path", 400)
        return Response(content=data, media_type="application/octet-stream")

    @app.websocket("/v1/session")
    async def session_ws(ws: WebSocket) -> None:
        if not _authorized(settings, ws.headers.get("x-pico-runner-token")):
            await ws.close(code=4401)
            return
        await ws.accept()
        try:
            spec = json.loads(await ws.receive_text())
            if spec.get("type") != "start":
                raise PolicyError("runner.bad_start", "first frame must be start")

            async def queued(ahead: int) -> None:
                await ws.send_text(json.dumps({"type": "queued", "ahead": ahead}))

            # pico-api sends nothing until "ready": any frame or a drop while
            # in line means it gave up, so the place in line goes back.
            start_t = asyncio.create_task(runner.start(spec, on_queued=queued))
            gone_t = asyncio.create_task(ws.receive())
            await asyncio.wait({start_t, gone_t}, return_when=asyncio.FIRST_COMPLETED)
            if not start_t.done():
                start_t.cancel()
                with contextlib.suppress(BaseException):
                    await start_t
                with contextlib.suppress(Exception):
                    await ws.close()
                return
            gone_t.cancel()
            with contextlib.suppress(BaseException):
                await gone_t
            session = start_t.result()
        except PolicyError as exc:
            await ws.send_text(
                json.dumps({"type": "error", "code": exc.code, "message": exc.message}, ensure_ascii=False)
            )
            await ws.close()
            return
        except Exception as exc:
            logger.exception("ws start failed")
            await ws.send_text(
                json.dumps({"type": "error", "code": "runner.start_failed", "message": type(exc).__name__})
            )
            await ws.close()
            return
        proc = session.proc
        stop_reason: list[str] = []

        async def send(obj: dict[str, Any]) -> None:
            await ws.send_text(json.dumps(obj, ensure_ascii=False))

        async def pump_out() -> None:
            assert proc.stdout is not None
            while True:
                try:
                    line = await proc.stdout.readline()
                except ValueError:
                    logger.warning("ws oversized stdout line run=%s dropped", session.run_id)
                    continue
                if not line:
                    return
                await send({"type": "out", "line": line.decode("utf-8", errors="replace").rstrip("\n")})

        async def pump_err() -> None:
            assert proc.stderr is not None
            while True:
                try:
                    line = await proc.stderr.readline()
                except ValueError:
                    continue
                if not line:
                    return
                text = line[:MAX_ERR_LINE].decode("utf-8", errors="replace").rstrip("\n")
                await send({"type": "err", "line": text})

        async def pump_in() -> None:
            # Runs until the socket closes, also after stdin EOF, so an abort
            # from pico-api (socket drop) always kills the box.
            assert proc.stdin is not None
            stdin_open = True
            while True:
                msg = json.loads(await ws.receive_text())
                t = msg.get("type")
                if t == "in" and stdin_open:
                    proc.stdin.write((str(msg.get("line") or "") + "\n").encode("utf-8"))
                    await proc.stdin.drain()
                elif t == "close" and stdin_open:
                    proc.stdin.close()
                    stdin_open = False

        async def watch() -> None:
            while proc.returncode is None:
                await asyncio.sleep(WATCH_EVERY_S)
                reason = await asyncio.to_thread(runner.over_limits, session)
                if reason:
                    logger.warning("ws limit run=%s: %s", session.run_id, reason)
                    stop_reason.append(reason)
                    return

        tasks: list[asyncio.Task[Any]] = []
        try:
            # Inside try: a socket dropped right after start still stops the box.
            await send({"type": "ready", "container": container_name(session.run_id)})
            out_t = asyncio.create_task(pump_out())
            err_t = asyncio.create_task(pump_err())
            in_t = asyncio.create_task(pump_in())
            watch_t = asyncio.create_task(watch())
            wait_t = asyncio.create_task(proc.wait())
            tasks = [out_t, err_t, in_t, watch_t, wait_t]
            done, _ = await asyncio.wait({out_t, wait_t, in_t, watch_t}, return_when=asyncio.FIRST_COMPLETED)
            if watch_t in done and stop_reason:
                with contextlib.suppress(Exception):
                    await send({"type": "error", "code": "runner.limit", "message": stop_reason[0]})
            elif in_t not in done:
                # Box finished on its own: drain, then report the exit code.
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(asyncio.gather(out_t, wait_t), timeout=5)
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(err_t, timeout=2)
                with contextlib.suppress(Exception):
                    await send({"type": "exit", "code": proc.returncode})
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("ws session error run=%s", session.run_id)
        finally:
            for t in tasks:
                t.cancel()
            await runner.stop(session)
            with contextlib.suppress(Exception):
                await ws.close()

    return app


_PROXY_KEEP = {"authorization", "content-type", "accept", "user-agent", "openai-beta"}


def proxy_path_ok(lane: str, path: str, raw_path: bytes) -> bool:
    """Fixed allow-list; no encoded separators or dot segments anywhere."""
    low = raw_path.lower()
    if b"%" in low or b".." in low or b"\\" in low or b"//" in low:
        return False
    if lane == "l":
        return path in MODEL_PATHS
    if lane == "t":
        return path in TOOL_PATHS
    return False


async def read_capped(request: Request, cap: int) -> bytes | None:
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > cap:
                return None
        except ValueError:
            return None
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > cap:
            return None
    return bytes(buf)


def build_proxy_app(runner: Runner) -> FastAPI:
    settings = runner.settings
    app = FastAPI(title="pi-runner proxy", docs_url=None, redoc_url=None, openapi_url=None)
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=None, write=60.0, pool=30.0),
        limits=httpx.Limits(max_connections=settings.max_sessions * PROXY_PER_RUN + 8),
        follow_redirects=False,
    )

    @app.api_route("/{lane}/{run_id}/{path:path}", methods=["GET", "POST"])
    async def forward(lane: str, run_id: str, path: str, request: Request) -> Response:
        try:
            validate_run_id(run_id)
        except PolicyError:
            return _deny("proxy.denied", 404)
        if not proxy_path_ok(lane, path, request.scope.get("raw_path") or b""):
            return _deny("proxy.denied", 404)
        session = runner.sessions.get(run_id)
        if session is None:
            return _deny("proxy.no_session", 403)
        # Slot first, body second: a box can hold at most PROXY_PER_RUN bodies
        # in runner memory, and only a few more requests may queue.
        if session.proxy_waiting >= PROXY_PER_RUN * 2:
            return _deny("proxy.busy", 429)
        session.proxy_waiting += 1
        try:
            await asyncio.wait_for(session.proxy_slots.acquire(), timeout=120)
        except TimeoutError:
            return _deny("proxy.busy", 429)
        finally:
            session.proxy_waiting -= 1
        try:
            body = await read_capped(request, MAX_PROXY_BODY)
        except BaseException:
            # Box dropped mid-body: the slot must come back or the run starves.
            session.proxy_slots.release()
            raise
        if body is None:
            session.proxy_slots.release()
            return _deny("proxy.too_large", 413)
        headers = {k: v for k, v in request.headers.items() if k.lower() in _PROXY_KEEP}
        headers["x-pico-runner-token"] = settings.token
        # Query strings are dropped: no allowed path needs one.
        target = f"{settings.upstream}/internal/ws-proxy/{lane}/{run_id}/{path}"
        try:
            upstream = client.build_request(request.method, target, headers=headers, content=body)
            resp = await client.send(upstream, stream=True)
        except Exception:  # noqa: BLE001 — any upstream failure is a 502 to the box
            session.proxy_slots.release()
            return _deny("proxy.upstream_unreachable", 502)

        async def body_iter():
            try:
                async for chunk in resp.aiter_raw():
                    yield chunk
            finally:
                try:
                    await resp.aclose()
                finally:
                    session.proxy_slots.release()

        out_headers = {k: v for k, v in resp.headers.items() if k.lower() in {"content-type", "cache-control"}}
        return StreamingResponse(body_iter(), status_code=resp.status_code, headers=out_headers)

    return app


async def _sweeper(runner: Runner) -> None:
    while True:
        with contextlib.suppress(Exception):
            removed = await asyncio.to_thread(runner.sweep_expired)
            if removed:
                logger.info("ws sweep removed=%s", removed)
        await asyncio.sleep(3600)


async def _reap_orphans(runner: Runner | None = None) -> None:
    """Remove workspace containers no live session owns."""
    with contextlib.suppress(Exception):
        code, out = await _docker(
            "ps", "-a", "--filter", "label=pico.ws=1", "--format", '{{.ID}} {{.Label "pico.ws.run"}}', timeout=15
        )
        if code != 0:
            return
        live = set(runner.sessions) if runner is not None else set()
        ids = [cid for cid, _, run in (ln.partition(" ") for ln in out.splitlines()) if cid and run not in live]
        if ids:
            await _docker("rm", "-f", *ids, timeout=30)
            logger.info("ws reaped orphans=%s", len(ids))


async def _orphan_loop(runner: Runner) -> None:
    while True:
        await asyncio.sleep(60)
        await _reap_orphans(runner)


async def serve() -> None:
    import signal

    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = RunnerSettings.from_env()
    runner = Runner(settings)
    await _reap_orphans(runner)
    control = uvicorn.Server(
        uvicorn.Config(
            build_control_app(runner),
            host=settings.control_host,
            port=settings.control_port,
            log_level="info",
            ws_max_size=32 * 1024 * 1024,
        )
    )
    proxy = uvicorn.Server(
        uvicorn.Config(
            build_proxy_app(runner),
            host=settings.proxy_host,
            port=settings.proxy_port,
            log_level="warning",
            access_log=False,
        )
    )
    # Two servers share one loop: one signal handler stops both.
    control.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    proxy.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, lambda: [setattr(s, "should_exit", True) for s in (control, proxy)])
    sweeper = asyncio.create_task(_sweeper(runner))
    reaper = asyncio.create_task(_orphan_loop(runner))
    try:
        await asyncio.gather(control.serve(), proxy.serve())
    finally:
        sweeper.cancel()
        reaper.cancel()
        for session in list(runner.sessions.values()):
            await runner.stop(session)


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
