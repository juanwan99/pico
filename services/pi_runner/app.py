"""pi-runner: per-session workspace containers for true Pi (card #1093).

Two listeners, one process:

* control (127.0.0.1:18790, pico-api only, ``X-Pico-Runner-Token``):
  WebSocket ``/v1/session`` pipes Pi RPC stdio of one container; file
  upload (attachments) / listing + download (outputs).
* proxy (pico-ws gateway IP:18791, workspace containers only): forwards
  ``/l/<run>/...`` (model) and ``/t/<run>/...`` (Pico gateway tools) to
  pico-api's token-checked ``/internal/ws-proxy``. This is the only
  internal address a workspace can reach.

Not an orchestrator: Pi is the kernel, pico-api owns the ledger. The
runner only starts/stops containers and moves bytes.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse

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
    safe_relpath,
    validate_pi_args,
    validate_run_id,
)

logger = logging.getLogger("pi_runner")

MAX_UPLOAD = 100 * 1024 * 1024
MAX_OUTPUT_FILE = 60 * 1024 * 1024
MAX_OUTPUT_FILES = 200
MAX_LINE = 32 * 1024 * 1024
WS_UID = 65532


@dataclass
class Session:
    run_id: str
    key: WorkspaceKey
    proc: asyncio.subprocess.Process
    started: float = field(default_factory=time.monotonic)


class Runner:
    def __init__(self, settings: RunnerSettings) -> None:
        self.settings = settings
        self.sessions: dict[str, Session] = {}
        self.lock = asyncio.Lock()

    # --- tenancy / capacity -------------------------------------------------

    def _check_capacity(self, key: WorkspaceKey) -> None:
        if len(self.sessions) >= self.settings.max_sessions:
            raise PolicyError("runner.busy", "too many workspace sessions")
        per_school = sum(1 for s in self.sessions.values() if s.key.school == key.school)
        if per_school >= self.settings.max_per_school:
            raise PolicyError("runner.school_busy", "too many sessions for this school")
        root = self.settings.workspace_root
        root.mkdir(parents=True, exist_ok=True)
        free_mb = shutil.disk_usage(root).free // (1024 * 1024)
        if free_mb < self.settings.min_free_mb:
            raise PolicyError("runner.disk_full", "host disk too full for a workspace")

    def _own(self, path: Path) -> None:
        # lchown: never follow a model-made symlink out of the workspace.
        with contextlib.suppress(PermissionError, OSError):
            os.lchown(path, WS_UID, WS_UID)

    def ensure_dir(self, path: Path) -> None:
        """mkdir that replaces a model-made symlink instead of following it."""
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            path.unlink()
        path.mkdir(exist_ok=True)
        self._own(path)

    def safe_dest(self, ws: Path, rel) -> Path:
        """Writable target under ``ws`` with no symlink on the way."""
        cur = ws
        for part in rel.parts[:-1]:
            cur = cur / part
            self.ensure_dir(cur)
        dest = cur / rel.parts[-1]
        if dest.is_symlink() or dest.is_dir():
            if dest.is_dir() and not dest.is_symlink():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        if not dest.parent.resolve().is_relative_to(ws.resolve()):
            raise PolicyError("runner.bad_path", "path escapes workspace")
        return dest

    def write_file(self, ws: Path, rel, data: bytes) -> Path:
        dest = self.safe_dest(ws, rel)
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        self._own(dest)
        return dest

    def prepare_workspace(self, key: WorkspaceKey, *, with_memory: bool) -> Path:
        root = self.settings.workspace_root
        root.mkdir(parents=True, exist_ok=True)
        ws = key.workspace_dir(root)
        # Tenant levels are runner-owned (root); only the leaf is the box's.
        for d in (root / key.school, root / key.school / key.member):
            d.mkdir(exist_ok=True)
        ws.mkdir(exist_ok=True)
        self._own(ws)
        for sub in ("attachments", "outputs", ".pico", ".pico/agent", ".pico/session", ".pi"):
            cur = ws
            for part in sub.split("/"):
                cur = cur / part
                self.ensure_dir(cur)
        if with_memory:
            mem = key.memory_dir(root)
            mem.mkdir(exist_ok=True)
            self._own(mem)
        os.utime(ws)
        return ws

    def seed_files(self, ws: Path, files: dict[str, str] | None) -> None:
        for rel, text in (files or {}).items():
            path = safe_relpath(rel, prefixes=SEED_PREFIXES)
            self.write_file(ws, path, str(text).encode("utf-8"))

    # --- container ------------------------------------------------------------

    async def start(self, spec: dict[str, Any]) -> tuple[Session, Path]:
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
        async with self.lock:
            if run_id in self.sessions:
                raise PolicyError("runner.duplicate", "run already has a session")
            self._check_capacity(key)
            ws = self.prepare_workspace(key, with_memory=with_memory)
            self.seed_files(ws, spec.get("files"))
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
                # docker reads --env-file before the container starts; give
                # the CLI a moment, then remove it regardless.
                asyncio.get_running_loop().call_later(10.0, _unlink_quiet, env_path)
            session = Session(run_id=run_id, key=key, proc=proc)
            self.sessions[run_id] = session
        logger.info(
            "ws start run=%s school=%s image=%s runtime=%s",
            run_id,
            key.school[:8],
            self.settings.image,
            self.settings.runtime,
        )
        return session, ws

    async def stop(self, session: Session) -> None:
        proc = session.proc
        if proc.returncode is None:
            with contextlib.suppress(Exception):
                kill = await asyncio.create_subprocess_exec(
                    "docker",
                    "kill",
                    container_name(session.run_id),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(kill.wait(), timeout=15)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(proc.wait(), timeout=10)
            if proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
        async with self.lock:
            self.sessions.pop(session.run_id, None)
        logger.info(
            "ws stop run=%s code=%s wall=%.0fs",
            session.run_id,
            proc.returncode,
            time.monotonic() - session.started,
        )

    # --- housekeeping ---------------------------------------------------------

    def workspace_mb(self, ws: Path) -> int:
        total = 0
        for dirpath, _dirs, files in os.walk(ws):
            for name in files:
                with contextlib.suppress(OSError):
                    total += os.lstat(os.path.join(dirpath, name)).st_size
        return total // (1024 * 1024)

    def sweep_expired(self) -> int:
        root = self.settings.workspace_root
        if not root.is_dir():
            return 0
        cutoff = time.time() - self.settings.ttl_days * 86400
        active = {s.key.workspace_dir(root) for s in self.sessions.values()}
        removed = 0
        for school in root.iterdir():
            if not school.is_dir():
                continue
            for member in school.iterdir():
                if not member.is_dir():
                    continue
                for conv in member.iterdir():
                    if not conv.is_dir() or conv.name == "_memory" or conv in active:
                        continue
                    with contextlib.suppress(OSError):
                        if conv.stat().st_mtime < cutoff:
                            shutil.rmtree(conv, ignore_errors=True)
                            removed += 1
        return removed


def _unlink_quiet(path: str) -> None:
    with contextlib.suppress(OSError):
        os.unlink(path)


def _authorized(settings: RunnerSettings, value: str | None) -> bool:
    return bool(value) and hmac.compare_digest(str(value), settings.token)


def _key_from_path(school: str, member: str, conv: str) -> WorkspaceKey:
    return WorkspaceKey.parse(school, member, conv)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_control_app(runner: Runner) -> FastAPI:
    settings = runner.settings
    app = FastAPI(title="pi-runner control", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "sessions": len(runner.sessions),
            "max_sessions": settings.max_sessions,
            "image": settings.image,
            "runtime": settings.runtime,
        }

    def _deny(request: Request) -> JSONResponse | None:
        if not _authorized(settings, request.headers.get("x-pico-runner-token")):
            return JSONResponse({"ok": False, "code": "auth.denied"}, status_code=401)
        return None

    @app.put("/v1/ws/{school}/{member}/{conv}/file")
    async def put_file(school: str, member: str, conv: str, path: str, request: Request):
        denied = _deny(request)
        if denied:
            return denied
        try:
            key = _key_from_path(school, member, conv)
            rel = safe_relpath(path, prefixes=UPLOAD_PREFIXES)
        except PolicyError as exc:
            return JSONResponse({"ok": False, "code": exc.code}, status_code=400)
        body = await request.body()
        if len(body) > MAX_UPLOAD:
            return JSONResponse({"ok": False, "code": "runner.too_large"}, status_code=413)
        ws = runner.prepare_workspace(key, with_memory=False)
        try:
            runner.write_file(ws, rel, body)
        except PolicyError as exc:
            return JSONResponse({"ok": False, "code": exc.code}, status_code=400)
        return {"ok": True, "path": str(rel), "bytes": len(body)}

    @app.get("/v1/ws/{school}/{member}/{conv}/outputs")
    async def list_outputs(school: str, member: str, conv: str, request: Request):
        denied = _deny(request)
        if denied:
            return denied
        try:
            key = _key_from_path(school, member, conv)
        except PolicyError as exc:
            return JSONResponse({"ok": False, "code": exc.code}, status_code=400)
        out_dir = key.workspace_dir(settings.workspace_root) / "outputs"
        rows: list[dict[str, Any]] = []
        if out_dir.is_dir():
            for dirpath, _dirs, files in os.walk(out_dir):
                for name in sorted(files):
                    full = Path(dirpath) / name
                    if full.is_symlink() or not full.is_file():
                        continue
                    size = full.stat().st_size
                    if size > MAX_OUTPUT_FILE:
                        continue
                    rows.append(
                        {
                            "path": str(full.relative_to(out_dir.parent)),
                            "size": size,
                            "mtime": full.stat().st_mtime,
                            "sha256": _sha256(full),
                        }
                    )
                    if len(rows) >= MAX_OUTPUT_FILES:
                        break
        return {"ok": True, "files": rows}

    @app.get("/v1/ws/{school}/{member}/{conv}/file")
    async def get_file(school: str, member: str, conv: str, path: str, request: Request):
        denied = _deny(request)
        if denied:
            return denied
        try:
            key = _key_from_path(school, member, conv)
            rel = safe_relpath(path, prefixes=DOWNLOAD_PREFIXES)
        except PolicyError as exc:
            return JSONResponse({"ok": False, "code": exc.code}, status_code=400)
        ws = key.workspace_dir(settings.workspace_root)
        full = ws / rel
        # Resolve after join: a model-made symlink must not escape the box dir.
        try:
            real = full.resolve(strict=True)
        except OSError:
            return JSONResponse({"ok": False, "code": "runner.not_found"}, status_code=404)
        if not real.is_relative_to(ws.resolve()) or not real.is_file():
            return JSONResponse({"ok": False, "code": "runner.bad_path"}, status_code=400)
        if real.stat().st_size > MAX_OUTPUT_FILE:
            return JSONResponse({"ok": False, "code": "runner.too_large"}, status_code=413)
        return Response(content=real.read_bytes(), media_type="application/octet-stream")

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
            session, wsdir = await runner.start(spec)
        except PolicyError as exc:
            await ws.send_text(json.dumps({"type": "error", "code": exc.code, "message": exc.message}))
            await ws.close()
            return
        except Exception as exc:
            logger.exception("ws start failed")
            await ws.send_text(
                json.dumps({"type": "error", "code": "runner.start_failed", "message": type(exc).__name__})
            )
            await ws.close()
            return
        await ws.send_text(json.dumps({"type": "ready", "container": container_name(session.run_id)}))
        proc = session.proc
        over_quota = asyncio.Event()

        async def pump_out(stream: asyncio.StreamReader, kind: str) -> None:
            while True:
                try:
                    line = await stream.readline()
                except ValueError:
                    # Line longer than the limit: drop it rather than wedge.
                    continue
                if not line:
                    return
                await ws.send_text(
                    json.dumps({"type": kind, "line": line.decode("utf-8", errors="replace").rstrip("\n")})
                )

        async def pump_in() -> None:
            assert proc.stdin is not None
            while True:
                msg = json.loads(await ws.receive_text())
                t = msg.get("type")
                if t == "in":
                    proc.stdin.write((str(msg.get("line") or "") + "\n").encode("utf-8"))
                    await proc.stdin.drain()
                elif t == "close":
                    proc.stdin.close()
                    return

        async def quota_watch() -> None:
            while proc.returncode is None:
                await asyncio.sleep(20)
                mb = await asyncio.to_thread(runner.workspace_mb, wsdir)
                if mb > settings.workspace_max_mb:
                    logger.warning("ws quota run=%s mb=%s", session.run_id, mb)
                    over_quota.set()
                    return

        out_t = asyncio.create_task(pump_out(proc.stdout, "out"))  # type: ignore[arg-type]
        err_t = asyncio.create_task(pump_out(proc.stderr, "err"))  # type: ignore[arg-type]
        in_t = asyncio.create_task(pump_in())
        quota_t = asyncio.create_task(quota_watch())
        wait_t = asyncio.create_task(proc.wait())
        try:
            while True:
                done, _ = await asyncio.wait(
                    {out_t, wait_t, in_t, quota_t}, return_when=asyncio.FIRST_COMPLETED
                )
                if quota_t in done and over_quota.is_set():
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "code": "runner.workspace_quota",
                                "message": "工作区超过容量上限，已停止。",
                            }
                        )
                    )
                    break
                if in_t in done:
                    exc = in_t.exception()
                    if isinstance(exc, WebSocketDisconnect) or exc is not None:
                        break
                    # stdin closed on purpose; keep draining stdout.
                    in_t = asyncio.create_task(asyncio.sleep(3600))
                if out_t in done or wait_t in done:
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(out_t, timeout=5)
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(wait_t, timeout=5)
                    break
            with contextlib.suppress(Exception):
                await asyncio.wait_for(err_t, timeout=2)
            with contextlib.suppress(Exception):
                await ws.send_text(json.dumps({"type": "exit", "code": proc.returncode}))
        except WebSocketDisconnect:
            pass
        finally:
            for t in (out_t, err_t, in_t, quota_t, wait_t):
                t.cancel()
            await runner.stop(session)
            with contextlib.suppress(Exception):
                await ws.close()

    return app


_PROXY_HOP = {"host", "content-length", "connection", "transfer-encoding", "x-pico-runner-token"}
_PROXY_KEEP = {"authorization", "content-type", "accept", "user-agent", "openai-beta"}


def build_proxy_app(runner: Runner) -> FastAPI:
    settings = runner.settings
    app = FastAPI(title="pi-runner proxy", docs_url=None, redoc_url=None, openapi_url=None)
    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=None, write=60.0, pool=10.0))

    @app.api_route("/{lane}/{run_id}/{path:path}", methods=["GET", "POST"])
    async def forward(lane: str, run_id: str, path: str, request: Request) -> Response:
        if lane not in {"l", "t"}:
            return JSONResponse({"ok": False, "code": "proxy.denied"}, status_code=404)
        try:
            validate_run_id(run_id)
        except PolicyError:
            return JSONResponse({"ok": False, "code": "proxy.denied"}, status_code=404)
        if run_id not in runner.sessions:
            return JSONResponse({"ok": False, "code": "proxy.no_session"}, status_code=403)
        body = await request.body()
        if len(body) > MAX_UPLOAD:
            return JSONResponse({"ok": False, "code": "proxy.too_large"}, status_code=413)
        headers = {
            k: v for k, v in request.headers.items() if k.lower() in _PROXY_KEEP and k.lower() not in _PROXY_HOP
        }
        headers["x-pico-runner-token"] = settings.token
        target = f"{settings.upstream}/internal/ws-proxy/{lane}/{run_id}/{path}"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        upstream = client.build_request(request.method, target, headers=headers, content=body)
        resp = await client.send(upstream, stream=True)

        async def body_iter():
            try:
                async for chunk in resp.aiter_raw():
                    yield chunk
            finally:
                await resp.aclose()

        out_headers = {
            k: v
            for k, v in resp.headers.items()
            if k.lower() in {"content-type", "cache-control"}
        }
        return StreamingResponse(body_iter(), status_code=resp.status_code, headers=out_headers)

    return app


async def _sweeper(runner: Runner) -> None:
    while True:
        with contextlib.suppress(Exception):
            removed = await asyncio.to_thread(runner.sweep_expired)
            if removed:
                logger.info("ws sweep removed=%s", removed)
        await asyncio.sleep(3600)


async def _reap_orphans(settings: RunnerSettings) -> None:
    """Kill workspace containers left over from a previous runner process."""
    with contextlib.suppress(Exception):
        ps = await asyncio.create_subprocess_exec(
            "docker",
            "ps",
            "-q",
            "--filter",
            "label=pico.ws=1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await ps.communicate()
        ids = [x for x in out.decode().split() if x]
        if ids:
            kill = await asyncio.create_subprocess_exec(
                "docker", "kill", *ids, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            await kill.wait()
            logger.info("ws reaped orphans=%s", len(ids))


async def serve() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = RunnerSettings.from_env()
    runner = Runner(settings)
    await _reap_orphans(settings)
    control = uvicorn.Server(
        uvicorn.Config(
            build_control_app(runner),
            host=settings.control_host,
            port=settings.control_port,
            log_level="info",
            ws_max_size=MAX_LINE,
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
    import signal

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, lambda: [setattr(s, "should_exit", True) for s in (control, proxy)])
    sweeper = asyncio.create_task(_sweeper(runner))
    try:
        await asyncio.gather(control.serve(), proxy.serve())
    finally:
        sweeper.cancel()
        for session in list(runner.sessions.values()):
            await runner.stop(session)


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
