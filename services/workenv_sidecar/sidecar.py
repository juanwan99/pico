#!/usr/bin/env python3
"""Workenv overlay sidecar: spawn Pi, pipe official JSONL over WS, kill.

Not an agent loop. Not compaction. Not a second kernel.
Bind intent: container :18768 published as host 127.0.0.1:18768.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from pico_workenv_ws import WebSocketConnection, accept_websocket, send_close, send_text

LISTEN_HOST = os.environ.get("PICO_WORKENV_BIND", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("PICO_WORKENV_PORT", "18768"))
TOKEN = (os.environ.get("PICO_SANDBOX_TOKEN") or "").strip()
WORK_ROOT = Path(os.environ.get("PICO_WORKENV_WORK", "/work"))
SESSION_ROOT = Path(os.environ.get("PICO_WORKENV_SESSION", "/session"))
AGENT_HOME = Path(os.environ.get("PI_CODING_AGENT_DIR", "/agent-home"))
MODEL = os.environ.get("PICO_MODEL", "gpt-5.6-sol")
PI_BIN = os.environ.get("PICO_TRUE_PI_BIN", "pi")
HOST_GW_TOOLS = os.environ.get("PICO_TRUE_PI_TOOL_URL", "http://host-gateway:18769")
UPSTREAM_BASE = os.environ.get("PICO_UPSTREAM_BASE", "http://host-gateway:18769/v1")

_lock = threading.Lock()
_state: dict[str, Any] = {
    "box_id": "box-1",
    "conversation_key": None,
    "runs": {},  # workspace_id -> run record
}


def _json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    if not TOKEN:
        return False
    raw = handler.headers.get("Authorization") or ""
    if raw.lower().startswith("bearer "):
        got = raw.split(" ", 1)[1].strip()
        return got == TOKEN
    return False


def write_agent_home() -> None:
    AGENT_HOME.mkdir(parents=True, exist_ok=True)
    models = {
        "providers": {
            "openai": {
                "baseUrl": UPSTREAM_BASE,
                "api": "openai-responses",
                "modelOverrides": {MODEL: {"contextWindow": 256000, "maxTokens": 32000}},
                "models": [
                    {
                        "id": MODEL,
                        "reasoning": True,
                        "input": ["text"],
                        "contextWindow": 256000,
                        "maxTokens": 32000,
                        "api": "openai-responses",
                        "thinkingLevelMap": {
                            "off": "medium",
                            "minimal": "medium",
                            "low": "medium",
                            "medium": "medium",
                            "high": "medium",
                            "xhigh": "medium",
                        },
                    }
                ],
            }
        }
    }
    (AGENT_HOME / "models.json").write_text(
        json.dumps(models, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    settings = {
        "compaction": {
            "enabled": True,
            "reserveTokens": 16384,
            "keepRecentTokens": 32768,
        }
    }
    text = json.dumps(settings, ensure_ascii=False, indent=2) + "\n"
    (AGENT_HOME / "settings.json").write_text(text, encoding="utf-8")
    system = (
        "You work in an isolated workspace. Use built-in read, write, edit, ls, and bash.\n"
        "Create real files on disk. Do not invent tool names.\n"
        "The teacher message is the user text. Do not weld extra delivery quotas.\n"
    )
    (AGENT_HOME / "SYSTEM.md").write_text(system, encoding="utf-8")


def _work_dir(workspace_id: str) -> Path:
    return WORK_ROOT / workspace_id


def _session_file(workspace_id: str) -> Path:
    return SESSION_ROOT / f"pico-{workspace_id}.jsonl"


def _spawn_argv(workspace_id: str) -> list[str]:
    session = _session_file(workspace_id)
    session.parent.mkdir(parents=True, exist_ok=True)
    if not session.exists():
        session.write_text("", encoding="utf-8")
    return [
        PI_BIN,
        "--mode",
        "rpc",
        "--no-context-files",
        "--no-extensions",
        "--session",
        str(session),
        "--provider",
        "openai",
        "--model",
        MODEL,
        "--thinking",
        "medium",
    ]


def _kill_pg(proc: subprocess.Popen[bytes] | None, *, grace: float = 5.0) -> int | None:
    if proc is None or proc.poll() is not None:
        return None if proc is None else proc.returncode
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
        except ProcessLookupError:
            return proc.poll()
    deadline = time.time() + grace
    while time.time() < deadline:
        rc = proc.poll()
        if rc is not None:
            return rc
        time.sleep(0.05)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    try:
        return proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        return proc.poll()


def _run_record(workspace_id: str) -> dict[str, Any] | None:
    with _lock:
        rec = _state["runs"].get(workspace_id)
        return rec


def create_run(body: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(body.get("workspace_id") or body.get("run_id") or "").strip()
    if not workspace_id:
        return {"ok": False, "error": "workspace_id required"}
    mode = str(body.get("mode") or "pi").strip()
    conv = str(body.get("conversation_id") or body.get("conversation_key") or "poc")
    write_agent_home()
    with _lock:
        if _state["conversation_key"] in {None, conv}:
            _state["conversation_key"] = conv
        elif _state["conversation_key"] != conv:
            return {"ok": False, "error": "box.conversation_mismatch", "status": 409}
        for rec in _state["runs"].values():
            proc = rec.get("proc")
            if rec.get("workspace_id") != workspace_id and proc is not None and proc.poll() is None:
                return {"ok": False, "error": "run.conflict", "status": 409}
        work = _work_dir(workspace_id)
        reused = work.exists()
        work.mkdir(parents=True, exist_ok=True)
        (work / ".pi").mkdir(parents=True, exist_ok=True)
        settings = (AGENT_HOME / "settings.json").read_text(encoding="utf-8")
        (work / ".pi" / "settings.json").write_text(settings, encoding="utf-8")
        system = (AGENT_HOME / "SYSTEM.md").read_text(encoding="utf-8")
        (work / ".pi" / "SYSTEM.md").write_text(system, encoding="utf-8")
        rec = _state["runs"].get(workspace_id) or {
            "workspace_id": workspace_id,
            "run_id": str(body.get("run_id") or workspace_id),
            "mode": mode,
            "proc": None,
            "ws": None,
            "stdin_lock": threading.Lock(),
        }
        rec["run_id"] = str(body.get("run_id") or workspace_id)
        rec["mode"] = mode
        _state["runs"][workspace_id] = rec
    return {
        "ok": True,
        "box_id": _state["box_id"],
        "workspace_id": workspace_id,
        "reused": reused,
    }


def attach_files(body: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(body.get("workspace_id") or "").strip()
    rec = _run_record(workspace_id)
    if rec is None:
        return {"ok": False, "error": "run.unknown", "status": 404}
    work = _work_dir(workspace_id)
    copied = []
    for item in body.get("files") or []:
        if not isinstance(item, dict):
            continue
        name = Path(str(item.get("name") or "")).name
        if not name or name in {".", ".."}:
            continue
        raw_b64 = str(item.get("bytes_b64") or "")
        try:
            raw = base64.b64decode(raw_b64)
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": "file.b64", "status": 400}
        dest = work / name
        dest.write_bytes(raw)
        copied.append({"name": name, "sha256": hashlib.sha256(raw).hexdigest(), "n": len(raw)})
    return {"ok": True, "copied": copied}


def collect_files(body: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(body.get("workspace_id") or "").strip()
    rec = _run_record(workspace_id)
    if rec is None:
        return {"ok": False, "error": "run.unknown", "status": 404}
    work = _work_dir(workspace_id)
    globs = body.get("glob") or ["*.xlsx", "*.docx", "*.pptx", "*.html", "*.png"]
    files = []
    for pattern in globs:
        for path in sorted(work.glob(pattern)):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            files.append(
                {
                    "name": path.name,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes_b64": base64.b64encode(raw).decode("ascii"),
                    "n": len(raw),
                }
            )
    return {"ok": True, "files": files}


def abort_run(body: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(body.get("workspace_id") or "").strip()
    rec = _run_record(workspace_id)
    if rec is None:
        return {"ok": False, "error": "run.unknown", "status": 404}
    proc = rec.get("proc")
    ws: WebSocketConnection | None = rec.get("ws")
    line = json.dumps({"id": f"a-{int(time.time())}", "type": "abort"}, ensure_ascii=False) + "\n"
    wrote = False
    if proc is not None and proc.stdin is not None and proc.poll() is None:
        with rec["stdin_lock"]:
            try:
                proc.stdin.write(line.encode("utf-8"))
                proc.stdin.flush()
                wrote = True
            except Exception:  # noqa: BLE001
                wrote = False
    if not wrote and proc is not None:
        _kill_pg(proc, grace=5.0)
    if ws is not None:
        try:
            send_text(ws, json.dumps({"type": "workenv.abort_ack", "wrote": wrote}))
        except Exception as exc:  # noqa: BLE001
            del exc
    return {"ok": True, "wrote": wrote}


def destroy_run(body: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(body.get("workspace_id") or "").strip()
    rec = _run_record(workspace_id)
    rc = None
    if rec is not None:
        rc = _kill_pg(rec.get("proc"), grace=5.0)
        rec["proc"] = None
        rec["ws"] = None
    work = _work_dir(workspace_id)
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    gone = not work.exists()
    return {"ok": True, "destroyed": gone, "returncode": rc}


def spawn_pi(workspace_id: str) -> subprocess.Popen[bytes]:
    rec = _run_record(workspace_id)
    if rec is None:
        raise RuntimeError("run.unknown")
    if rec.get("proc") is not None and rec["proc"].poll() is None:
        raise RuntimeError("run.conflict")
    work = _work_dir(workspace_id)
    work.mkdir(parents=True, exist_ok=True)
    write_agent_home()
    env = os.environ.copy()
    env["PI_CODING_AGENT_DIR"] = str(AGENT_HOME)
    env["HOME"] = "/tmp"
    env["PYTHONUNBUFFERED"] = "1"
    env["PICO_TRUE_PI_TOOL_URL"] = HOST_GW_TOOLS
    env["PICO_TRUE_PI_RUN_ID"] = rec["run_id"]
    tok = (os.environ.get("PICO_RUN_TOKEN") or os.environ.get("OPENAI_API_KEY") or "").strip()
    if tok:
        env["OPENAI_API_KEY"] = tok
        env["OPENAI_BASE_URL"] = UPSTREAM_BASE
    env.pop("DEEPSEEK_API_KEY", None)
    env.pop("PICO_SANDBOX_TOKEN", None)
    argv = _spawn_argv(workspace_id)
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(work),
        env=env,
        start_new_session=True,
        bufsize=0,
    )
    rec["proc"] = proc
    return proc


def _pipe_stdout(proc: subprocess.Popen[bytes], ws: WebSocketConnection) -> None:
    assert proc.stdout is not None
    buf = b""
    try:
        while True:
            chunk = proc.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.rstrip(b"\r")
                if not line:
                    continue
                try:
                    send_text(ws, line.decode("utf-8"))
                except Exception:  # noqa: BLE001
                    return
    finally:
        try:
            send_close(ws)
        except Exception as exc:  # noqa: BLE001
            del exc


def _pipe_stderr(proc: subprocess.Popen[bytes]) -> None:
    assert proc.stderr is not None
    while True:
        line = proc.stderr.readline()
        if not line:
            return


def attach_rpc(ws: WebSocketConnection, workspace_id: str) -> None:
    proc = spawn_pi(workspace_id)
    rec = _run_record(workspace_id)
    assert rec is not None
    rec["ws"] = ws
    t_out = threading.Thread(target=_pipe_stdout, args=(proc, ws), daemon=True)
    t_err = threading.Thread(target=_pipe_stderr, args=(proc,), daemon=True)
    t_out.start()
    t_err.start()
    try:
        while True:
            msg = ws.recv_text()
            if msg is None:
                break
            payload = msg if msg.endswith("\n") else msg + "\n"
            if proc.poll() is not None:
                break
            with rec["stdin_lock"]:
                if proc.stdin is None:
                    break
                proc.stdin.write(payload.encode("utf-8"))
                proc.stdin.flush()
    except Exception as exc:  # noqa: BLE001
        del exc
    finally:
        _kill_pg(proc, grace=5.0)
        rec["proc"] = None
        rec["ws"] = None
        try:
            ws.close()
        except Exception as exc:  # noqa: BLE001
            del exc


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys_stderr = __import__("sys").stderr
        sys_stderr.write("[workenv] " + (fmt % args) + "\n")

    def _read_json(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(n) if n else b"{}"
        try:
            obj = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
        return obj if isinstance(obj, dict) else {}

    def _send_json(self, code: int, obj: dict[str, Any]) -> None:
        body = _json_bytes(obj)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not _auth_ok(self):
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return
        path = urlparse(self.path).path
        if (self.headers.get("Upgrade") or "").lower() == "websocket":
            if path != "/v1/internal/workenv/attach-rpc":
                self._send_json(404, {"ok": False, "error": "not_found"})
                return
            workspace_id = (self.headers.get("X-Pico-Run-Id") or "").strip()
            if not workspace_id or _run_record(workspace_id) is None:
                self._send_json(404, {"ok": False, "error": "run.unknown"})
                return
            self.close_connection = True
            ws = accept_websocket(self)
            attach_rpc(ws, workspace_id)
            return
        if path == "/healthz":
            self._send_json(200, {"ok": True, "service": "workenv-sidecar"})
            return
        self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        if not _auth_ok(self):
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return
        path = urlparse(self.path).path
        body = self._read_json()
        routes = {
            "/v1/internal/workenv/create": create_run,
            "/v1/internal/workenv/attach": attach_files,
            "/v1/internal/workenv/collect": collect_files,
            "/v1/internal/workenv/abort": abort_run,
            "/v1/internal/workenv/destroy-run": destroy_run,
        }
        fn = routes.get(path)
        if fn is None:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        result = fn(body)
        code = int(result.pop("status", 200) or 200)
        if not result.get("ok", True) and code == 200:
            code = 400
        self._send_json(code, result)


def main() -> int:
    if not TOKEN:
        raise SystemExit("PICO_SANDBOX_TOKEN required")
    write_agent_home()
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(f"workenv-sidecar listen {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
