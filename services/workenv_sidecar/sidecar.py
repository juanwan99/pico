#!/usr/bin/env python3
"""Workenv overlay sidecar: spawn Pi, pipe official JSONL over WS, kill.

Not an agent loop. Not compaction. Not a second kernel.
Bind intent: container :18768 published as host 127.0.0.1:18768.
"""

from __future__ import annotations

import base64
import errno
import hashlib
import json
import os
import shutil
import signal
import stat
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

# prctl(2) PR_SET_PDEATHSIG. Direct child only; fork descendants do not inherit.
# Not a cgroup. Load libc before fork so preexec_fn does not import.
_PR_SET_PDEATHSIG = 1
_LIBC = None
if sys.platform.startswith("linux"):
    import ctypes

    try:
        _LIBC = ctypes.CDLL(None, use_errno=True)
    except OSError:
        _LIBC = None


def _preexec_pdeathsig() -> None:
    """SIGKILL this process if the sidecar parent dies. Direct child only."""
    if _LIBC is None:
        raise OSError("prctl unavailable")
    rc = _LIBC.prctl(_PR_SET_PDEATHSIG, int(signal.SIGKILL), 0, 0, 0)
    if rc != 0:
        import ctypes

        err = ctypes.get_errno()
        raise OSError(err, "prctl PR_SET_PDEATHSIG")
    if os.getppid() == 1:
        os.kill(os.getpid(), signal.SIGKILL)

LISTEN_HOST = os.environ.get("PICO_WORKENV_BIND", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("PICO_WORKENV_PORT", "18768"))
TOKEN = (os.environ.get("PICO_SANDBOX_TOKEN") or "").strip()
WORK_ROOT = Path(os.environ.get("PICO_WORKENV_WORK", "/work"))
SESSION_ROOT = Path(os.environ.get("PICO_WORKENV_SESSION", "/session"))
AGENT_HOME = Path(os.environ.get("PI_CODING_AGENT_DIR", "/agent-home"))
MODEL = os.environ.get("PICO_MODEL", "gpt-5.6-sol")
PI_BIN = os.environ.get("PICO_TRUE_PI_BIN", "pi")
# 18769 is the model proxy, never a ToolServer. Pi-mode create must pass tool_url.
HOST_GW_TOOLS = (os.environ.get("PICO_TRUE_PI_TOOL_URL") or "").strip()
UPSTREAM_BASE = os.environ.get("PICO_UPSTREAM_BASE", "http://host-gateway:18769/v1")
GATEWAY_EXT = Path(
    os.environ.get("PICO_GATEWAY_EXT", "/bridge/pico-gateway-tools.ts")
)
GATEWAY_EXT_SRC = Path(
    os.environ.get(
        "PICO_GATEWAY_EXT_SRC",
        "/tmp/pico-t4/services/true_pi_bridge/pico-gateway-tools.ts",
    )
)

_lock = threading.Lock()
_state: dict[str, Any] = {
    "box_id": "box-1",
    "conversation_key": None,
    "session_conversation": None,
    "owner_key": None,
    "runs": {},  # workspace_id -> run record
    "destroyed": set(),
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


def _safe_workspace_id(workspace_id: str) -> str | None:
    """Single path name under WORK_ROOT. Reject .., slashes, and absolute."""
    wid = str(workspace_id or "").strip()
    if not wid or wid in {".", ".."}:
        return None
    if "/" in wid or "\\" in wid:
        return None
    raw = Path(wid)
    if raw.is_absolute() or len(raw.parts) != 1 or raw.parts[0] == "..":
        return None
    return wid


def _work_dir(workspace_id: str) -> Path:
    wid = _safe_workspace_id(workspace_id)
    if wid is None:
        raise ValueError("workspace_id.invalid")
    root = Path(WORK_ROOT)
    work = root / wid
    try:
        root_res = root.resolve()
        resolved = work.resolve()
    except OSError as exc:
        raise ValueError("workspace_id.invalid") from exc
    if root_res not in resolved.parents:
        raise ValueError("workspace_id.invalid")
    return work


def _open_under_root(root: Path, path: Path) -> int | None:
    """Open path under root without following any symlink component."""
    try:
        root_res = root.resolve()
        rel = path.relative_to(root)
    except (OSError, ValueError):
        return None
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_DIRECTORY"):
        dir_flags = flags | os.O_DIRECTORY
    else:
        dir_flags = flags
    try:
        dir_fd = os.open(root_res, dir_flags)
    except OSError:
        return None
    try:
        parts = rel.parts
        if not parts or parts == (".",):
            os.close(dir_fd)
            return None
        for i, part in enumerate(parts):
            if part in {"", ".", ".."}:
                os.close(dir_fd)
                return None
            last = i == len(parts) - 1
            open_flags = flags if last else dir_flags
            if last and hasattr(os, "O_NONBLOCK"):
                open_flags |= os.O_NONBLOCK
            try:
                next_fd = os.open(part, open_flags, dir_fd=dir_fd)
            except OSError:
                os.close(dir_fd)
                return None
            os.close(dir_fd)
            dir_fd = next_fd
        return dir_fd
    except Exception:
        os.close(dir_fd)
        return None


def _read_regular_nofollow(path: Path, *, root: Path | None = None, max_bytes: int = 8 * 1024 * 1024) -> bytes | None:
    """Read a regular file. Do not follow a symlink out of /work."""
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    fd: int | None
    if root is not None:
        fd = _open_under_root(root, path)
    else:
        try:
            fd = os.open(path, flags)
        except OSError:
            fd = None
    if fd is None:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return None
        if int(st.st_size) > max_bytes:
            return None
        chunks: list[bytes] = []
        remaining = int(st.st_size)
        while remaining > 0:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _session_file(_workspace_id: str) -> Path:
    """One conversation, one official --session file.

    Same conversation may retarget cwd. A cleared conversation binding
    must not inherit the previous jsonl.
    """
    return SESSION_ROOT / "pico.jsonl"


def _session_bind_path() -> Path:
    return SESSION_ROOT / "bind.json"


def _read_session_bind() -> dict[str, str]:
    path = _session_bind_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        "conversation": str(raw.get("conversation") or ""),
        "owner": str(raw.get("owner") or ""),
    }


def _write_session_bind(*, conversation: str, owner: str) -> None:
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    _session_bind_path().write_text(
        json.dumps({"conversation": conversation, "owner": owner}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )


def _reset_session_file() -> None:
    path = SESSION_ROOT / "pico.jsonl"
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    try:
        _session_bind_path().unlink()
    except FileNotFoundError:
        pass


def _tool_url_ok(url: str) -> bool:
    """Reject the model proxy. ToolServer is never :18769."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.hostname:
        return False
    try:
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return False
    if int(port) == 18769:
        return False
    return True


def _retarget_session_cwd(session: Path, work: Path) -> None:
    """Point official session cwd at this run's /work/{run}.

    Destroy-run removes the previous workdir. Pi 0.84.4 then exits with
    ``Stored session working directory does not exist`` before prompt.
    Conversation jsonl stays; only the session header cwd moves.
    """
    if not session.is_file() or session.stat().st_size == 0:
        return
    text = session.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        return
    try:
        first = json.loads(lines[0])
    except json.JSONDecodeError:
        return
    if not isinstance(first, dict) or first.get("type") != "session":
        return
    first["cwd"] = str(work)
    lines[0] = json.dumps(first, ensure_ascii=False)
    session.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _gateway_oserror(exc: OSError) -> RuntimeError:
    if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
        return RuntimeError("gateway.ext.missing")
    return RuntimeError("gateway.ext.tampered")


def _reject_symlink_prefixes(path: Path) -> None:
    """lstat each prefix so an ancestor symlink cannot hide behind a final leaf."""
    raw = os.path.normpath(str(path))
    parts = Path(raw).parts
    if not parts or parts[-1] in {"", ".", ".."}:
        raise RuntimeError("gateway.ext.tampered")
    acc = Path(parts[0])
    rest = parts[1:]
    prefixes = [acc] if acc != Path(".") else []
    for part in rest:
        if part in {"", ".", ".."}:
            raise RuntimeError("gateway.ext.tampered")
        acc = acc / part
        prefixes.append(acc)
    for prefix in prefixes:
        try:
            st = os.lstat(prefix)
        except OSError as exc:
            if prefix == Path(raw):
                raise _gateway_oserror(exc) from exc
            raise RuntimeError("gateway.ext.tampered") from exc
        if stat.S_ISLNK(st.st_mode):
            raise RuntimeError("gateway.ext.tampered")


def _open_nofollow_file(path: Path) -> tuple[int, os.stat_result]:
    """Open leaf via parent dir_fd. O_NOFOLLOW on both. Same FD for fstat/read."""
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("gateway.ext.tampered")
    _reject_symlink_prefixes(path)
    flags = os.O_RDONLY | os.O_NOFOLLOW
    dir_flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_DIRECTORY"):
        dir_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    try:
        dir_fd = os.open(str(path.parent), dir_flags)
    except OSError as exc:
        raise _gateway_oserror(exc) from exc
    try:
        parent_st = os.fstat(dir_fd)
        if not stat.S_ISDIR(parent_st.st_mode):
            raise RuntimeError("gateway.ext.tampered")
        fd = os.open(path.name, flags, dir_fd=dir_fd)
    except OSError as exc:
        raise _gateway_oserror(exc) from exc
    finally:
        os.close(dir_fd)
    return fd, parent_st


def _read_nofollow_regular(path: Path) -> tuple[bytes, os.stat_result, os.stat_result]:
    fd, parent_st = _open_nofollow_file(path)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise RuntimeError("gateway.ext.tampered")
        want = int(st.st_size)
        if want > 2 * 1024 * 1024 or want <= 0:
            raise RuntimeError("gateway.ext.tampered")
        chunks: list[bytes] = []
        n = 0
        while n < want:
            piece = os.read(fd, min(65536, want - n))
            if not piece:
                raise RuntimeError("gateway.ext.tampered")
            n += len(piece)
            chunks.append(piece)
        if n != want:
            raise RuntimeError("gateway.ext.tampered")
        if os.read(fd, 1):
            raise RuntimeError("gateway.ext.tampered")
        return b"".join(chunks), st, parent_st
    except OSError as exc:
        raise _gateway_oserror(exc) from exc
    finally:
        os.close(fd)


def _ensure_gateway_ext() -> Path:
    """Official Pico gateway extension. Same -e file as host spawn_command."""
    src, src_st, src_parent = _read_nofollow_regular(GATEWAY_EXT_SRC)
    if src_st.st_mode & 0o002 or src_parent.st_mode & 0o002:
        raise RuntimeError("gateway.ext.tampered")
    current, st, parent_st = _read_nofollow_regular(GATEWAY_EXT)
    if st.st_mode & 0o002 or parent_st.st_mode & 0o002:
        raise RuntimeError("gateway.ext.tampered")
    dest_resolved = Path(os.path.normpath(str(GATEWAY_EXT)))
    if str(dest_resolved) == "/bridge/pico-gateway-tools.ts":
        if st.st_uid != 0 or (st.st_mode & 0o022):
            raise RuntimeError("gateway.ext.tampered")
        if parent_st.st_uid != 0 or (parent_st.st_mode & 0o022) or not stat.S_ISDIR(parent_st.st_mode):
            raise RuntimeError("gateway.ext.tampered")
    if current != src:
        raise RuntimeError("gateway.ext.tampered")
    del src_parent
    return GATEWAY_EXT


def _spawn_argv(workspace_id: str) -> list[str]:
    session = _session_file(workspace_id)
    session.parent.mkdir(parents=True, exist_ok=True)
    if not session.exists():
        session.write_text("", encoding="utf-8")
    argv = [
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
    rec = _run_record(workspace_id)
    mode = str((rec or {}).get("mode") or "pi")
    # Overlay Pi keeps builtins (files/bash in-box). Host spawn uses
    # --no-builtin-tools. B1 still loads the official Pico gateway -e.
    if mode == "pi":
        argv.extend(["-e", str(_ensure_gateway_ext())])
    return argv


def _kill_pg(proc: subprocess.Popen[bytes] | None, *, grace: float = 5.0) -> int | None:
    """SIGTERM/SIGKILL the process group even if the parent already exited."""
    if proc is None:
        return None
    parent_rc = proc.poll()
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        if parent_rc is not None:
            return parent_rc
        try:
            proc.terminate()
        except ProcessLookupError:
            return proc.poll()
    deadline = time.time() + grace
    while time.time() < deadline:
        rc = proc.poll()
        group_alive = False
        try:
            os.killpg(proc.pid, 0)
            group_alive = True
        except (ProcessLookupError, PermissionError, OSError):
            group_alive = False
        if rc is not None and not group_alive:
            return rc
        time.sleep(0.05)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        if parent_rc is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
    kill_deadline = time.time() + 2
    while time.time() < kill_deadline:
        rc = proc.poll()
        try:
            os.killpg(proc.pid, 0)
            time.sleep(0.05)
            continue
        except (ProcessLookupError, PermissionError, OSError):
            return parent_rc if parent_rc is not None else rc
    if parent_rc is not None:
        return parent_rc
    try:
        return proc.wait(timeout=0.2)
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
    if _safe_workspace_id(workspace_id) is None:
        return {"ok": False, "error": "workspace_id.invalid", "status": 400}
    mode = str(body.get("mode") or "pi").strip()
    if mode not in {"pi", "workdir"}:
        return {"ok": False, "error": "mode.invalid", "status": 400}
    tool_url = str(body.get("tool_url") or HOST_GW_TOOLS).strip()
    tool_token = str(body.get("tool_token") or "").strip()
    visible_tools = str(body.get("visible_tools") or "").strip()
    if mode == "pi" and not _tool_url_ok(tool_url):
        return {"ok": False, "error": "tool_url.invalid", "status": 400}
    conv = str(body.get("conversation_id") or body.get("conversation_key") or "poc")
    owner = (
        str(body.get("school_id") or "").strip()
        + ":"
        + str(body.get("membership_id") or "").strip()
    )
    write_agent_home()
    with _lock:
        if workspace_id in _state["destroyed"]:
            return {"ok": False, "error": "run.destroyed", "status": 409}
        if _state["owner_key"] not in {None, owner}:
            return {"ok": False, "error": "box.owner_mismatch", "status": 409}
        bind = _read_session_bind()
        if bind.get("owner") and bind["owner"] != owner:
            return {"ok": False, "error": "box.owner_mismatch", "status": 409}
        if _state["conversation_key"] in {None, conv}:
            bound_conv = bind.get("conversation") or _state.get("session_conversation")
            if bound_conv and bound_conv != conv:
                _reset_session_file()
            elif not bind and (SESSION_ROOT / "pico.jsonl").is_file() and (SESSION_ROOT / "pico.jsonl").stat().st_size:
                _reset_session_file()
            _state["conversation_key"] = conv
            _state["session_conversation"] = conv
            _write_session_bind(conversation=conv, owner=owner)
        elif _state["conversation_key"] != conv:
            return {"ok": False, "error": "box.conversation_mismatch", "status": 409}
        _state["owner_key"] = owner
        for rec in _state["runs"].values():
            if rec.get("workspace_id") != workspace_id:
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
            "pgid": None,
            "pgids": [],
            "ws": None,
            "destroyed": False,
            "stdin_lock": threading.Lock(),
        }
        if rec.get("destroyed"):
            return {"ok": False, "error": "run.destroyed", "status": 409}
        rec["run_id"] = str(body.get("run_id") or workspace_id)
        rec["mode"] = mode
        rec["tool_url"] = tool_url
        rec["tool_token"] = tool_token
        rec["visible_tools"] = visible_tools
        rec.setdefault("pgids", [])
        rec["destroyed"] = False
        _state["runs"][workspace_id] = rec
        _state["destroyed"].discard(workspace_id)
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
    if rec.get("destroyed") or workspace_id in _state["destroyed"]:
        return {"ok": False, "error": "run.destroyed", "status": 409}
    try:
        work = _work_dir(workspace_id)
    except ValueError:
        return {"ok": False, "error": "workspace_id.invalid", "status": 400}
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
        if dest.is_symlink() or dest.exists():
            dest.unlink()
        dest.write_bytes(raw)
        copied.append({"name": name, "sha256": hashlib.sha256(raw).hexdigest(), "n": len(raw)})
    return {"ok": True, "copied": copied}


def collect_files(body: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(body.get("workspace_id") or "").strip()
    rec = _run_record(workspace_id)
    if rec is None:
        return {"ok": False, "error": "run.unknown", "status": 404}
    try:
        work = _work_dir(workspace_id)
    except ValueError:
        return {"ok": False, "error": "workspace_id.invalid", "status": 400}
    allowed_globs = {"*.xlsx", "*.docx", "*.pptx", "*.html", "*.png"}
    globs = body.get("glob") or list(allowed_globs)
    files = []
    for pattern in globs:
        if pattern not in allowed_globs:
            continue
        try:
            root_res = Path(WORK_ROOT).resolve()
        except OSError:
            return {"ok": False, "error": "workspace_id.invalid", "status": 400}
        for path in sorted(work.glob(pattern)):
            if path.is_symlink():
                continue
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if root_res not in resolved.parents:
                continue
            raw = _read_regular_nofollow(path, root=Path(WORK_ROOT))
            if raw is None:
                continue
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
    if _safe_workspace_id(workspace_id) is None:
        return {"ok": False, "error": "workspace_id.invalid", "status": 400}
    proc = rec.get("proc")
    ws: WebSocketConnection | None = rec.get("ws")
    line = json.dumps({"id": f"a-{int(time.time())}", "type": "abort"}, ensure_ascii=False) + "\n"
    wrote = False
    if rec.get("mode") != "workdir" and proc is not None and proc.stdin is not None and proc.poll() is None:
        with rec["stdin_lock"]:
            try:
                proc.stdin.write(line.encode("utf-8"))
                proc.stdin.flush()
                wrote = True
            except Exception:  # noqa: BLE001
                wrote = False
    if rec.get("mode") == "workdir" or not wrote:
        if proc is not None:
            _kill_pg(proc, grace=5.0)
        pgid = rec.get("pgid")
        if isinstance(pgid, int) and pgid > 0:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
    if ws is not None:
        try:
            send_text(ws, json.dumps({"type": "workenv.abort_ack", "wrote": wrote}))
        except Exception as exc:  # noqa: BLE001
            del exc
    return {"ok": True, "wrote": wrote}


def list_work_files(body: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(body.get("workspace_id") or "").strip()
    rec = _run_record(workspace_id)
    if rec is None:
        return {"ok": False, "error": "run.unknown", "status": 404}
    try:
        work = _work_dir(workspace_id)
    except ValueError:
        return {"ok": False, "error": "workspace_id.invalid", "status": 400}
    names: list[dict[str, Any]] = []
    if work.is_dir():
        for path in sorted(work.iterdir()):
            if path.name.startswith("."):
                continue
            if path.is_symlink():
                continue
            if path.is_file():
                names.append({"name": path.name, "n": path.stat().st_size})
    return {"ok": True, "files": names}


def read_work_file(body: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(body.get("workspace_id") or "").strip()
    rec = _run_record(workspace_id)
    if rec is None:
        return {"ok": False, "error": "run.unknown", "status": 404}
    name = Path(str(body.get("name") or "")).name
    if not name or name in {".", ".."}:
        return {"ok": False, "error": "file.name", "status": 400}
    try:
        work = _work_dir(workspace_id)
    except ValueError:
        return {"ok": False, "error": "workspace_id.invalid", "status": 400}
    path = work / name
    if path.is_symlink():
        return {"ok": False, "error": "file.symlink", "status": 400}
    raw = _read_regular_nofollow(path, root=Path(WORK_ROOT))
    if raw is None:
        return {"ok": False, "error": "file.missing", "status": 404}
    return {
        "ok": True,
        "name": name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes_b64": base64.b64encode(raw).decode("ascii"),
        "n": len(raw),
    }


def exec_work(body: dict[str, Any]) -> dict[str, Any]:
    """Run python in /work/{run}. Not a shell. Not a second agent loop."""
    workspace_id = str(body.get("workspace_id") or "").strip()
    rec = _run_record(workspace_id)
    if rec is None:
        return {"ok": False, "error": "run.unknown", "status": 404}
    try:
        work = _work_dir(workspace_id)
    except ValueError:
        return {"ok": False, "error": "workspace_id.invalid", "status": 400}
    timeout = min(max(int(body.get("timeout") or 30), 1), 60)
    source = body.get("source")
    argv_in = body.get("argv")
    argv: list[str]
    if isinstance(source, str) and source.strip():
        script = work / "_pico_exec.py"
        if script.is_symlink() or script.exists():
            script.unlink()
        script.write_text(source, encoding="utf-8")
        argv = ["python3", "-I", str(script)]
    elif isinstance(argv_in, list) and argv_in:
        argv = [str(x) for x in argv_in]
        if not argv or Path(argv[0]).name not in {"python3", "python"}:
            return {"ok": False, "error": "exec.argv", "status": 400}
        for item in argv[1:]:
            if item.startswith("-") and item not in {"-I", "-c", "-u"}:
                return {"ok": False, "error": "exec.flag", "status": 400}
    else:
        return {"ok": False, "error": "exec.source", "status": 400}
    env = {
        "HOME": "/tmp",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    with _lock:
        rec = _state["runs"].get(workspace_id)
        if rec is None:
            return {"ok": False, "error": "run.unknown", "status": 404}
        if rec.get("destroyed") or workspace_id in _state["destroyed"]:
            return {"ok": False, "error": "run.destroyed", "status": 409}
        try:
            proc = subprocess.Popen(
                argv,
                cwd=str(work),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                preexec_fn=_preexec_pdeathsig,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "error": "exec.spawn", "detail": str(exc)[:200]}
        rec["proc"] = proc
        try:
            rec["pgid"] = os.getpgid(proc.pid)
        except OSError:
            rec["pgid"] = proc.pid
        pgids = rec.setdefault("pgids", [])
        if isinstance(rec["pgid"], int) and rec["pgid"] > 0 and rec["pgid"] not in pgids:
            pgids.append(rec["pgid"])
    try:
        stdout_b, stderr_b = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_pg(proc, grace=2.0)
        rec["proc"] = None
        rec["pgid"] = None
        return {"ok": False, "error": "exec.timeout", "timeout": timeout, "executed": False}
    stdout = (stdout_b or b"")[:8000].decode("utf-8", errors="replace")
    stderr = (stderr_b or b"")[:4000].decode("utf-8", errors="replace")
    return {
        "ok": proc.returncode == 0,
        "executed": True,
        "returncode": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def destroy_run(body: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(body.get("workspace_id") or "").strip()
    with _lock:
        rec = _state["runs"].get(workspace_id)
        if rec is not None:
            rec["destroyed"] = True
        _state["destroyed"].add(workspace_id)
    rec = _run_record(workspace_id)
    rc = None
    seen: list[int] = []
    proc = rec.get("proc") if rec is not None else None
    if rec is not None:
        for pgid in [rec.get("pgid"), *(rec.get("pgids") or [])]:
            if isinstance(pgid, int) and pgid > 0 and pgid not in seen:
                seen.append(pgid)
        rc = _kill_pg(proc, grace=5.0)
        for pgid in seen:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except (PermissionError, OSError):
                pass
        rec["ws"] = None
        rec["destroyed"] = True
    alive = bool(proc is not None and proc.poll() is None)
    for pgid in seen:
        try:
            os.killpg(pgid, 0)
            alive = True
        except ProcessLookupError:
            pass
        except (PermissionError, OSError):
            # PermissionError is not proof the group is gone.
            alive = True
    try:
        work = _work_dir(workspace_id)
    except ValueError:
        return {"ok": False, "destroyed": False, "returncode": rc, "error": "workspace_id.invalid"}
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    gone = (not work.exists()) and not alive
    if gone:
        with _lock:
            rec = _state["runs"].get(workspace_id)
            if rec is not None:
                rec["proc"] = None
                rec["pgid"] = None
                rec["pgids"] = []
            _state["runs"].pop(workspace_id, None)
            _state["destroyed"].add(workspace_id)
            if not _state["runs"]:
                _state["conversation_key"] = None
                _state["owner_key"] = None
                # Keep official --session jsonl for T1 round 2. Wipe only
                # when create binds a different conversation.
    return {"ok": gone, "destroyed": gone, "returncode": rc}


def spawn_pi(workspace_id: str) -> subprocess.Popen[bytes]:
    rec = _run_record(workspace_id)
    if rec is None:
        raise RuntimeError("run.unknown")
    if rec.get("destroyed") or workspace_id in _state["destroyed"]:
        raise RuntimeError("run.destroyed")
    if rec.get("proc") is not None and rec["proc"].poll() is None:
        raise RuntimeError("run.conflict")
    work = _work_dir(workspace_id)
    work.mkdir(parents=True, exist_ok=True)
    _retarget_session_cwd(_session_file(workspace_id), work)
    write_agent_home()
    env = os.environ.copy()
    env["PI_CODING_AGENT_DIR"] = str(AGENT_HOME)
    env["HOME"] = "/tmp"
    env["PYTHONUNBUFFERED"] = "1"
    env["PICO_TRUE_PI_TOOL_URL"] = str(rec.get("tool_url") or HOST_GW_TOOLS)
    env["PICO_TRUE_PI_RUN_ID"] = rec["run_id"]
    tok_tool = str(rec.get("tool_token") or "").strip()
    if tok_tool:
        env["PICO_TRUE_PI_TOOL_TOKEN"] = tok_tool
    vis = str(rec.get("visible_tools") or "").strip()
    if vis:
        env["PICO_TRUE_PI_VISIBLE_TOOLS"] = vis
    tok = (os.environ.get("PICO_RUN_TOKEN") or os.environ.get("OPENAI_API_KEY") or "").strip()
    if tok:
        env["OPENAI_API_KEY"] = tok
        env["OPENAI_BASE_URL"] = UPSTREAM_BASE
    env.pop("DEEPSEEK_API_KEY", None)
    env.pop("PICO_SANDBOX_TOKEN", None)
    argv = _spawn_argv(workspace_id)
    with _lock:
        rec = _state["runs"].get(workspace_id)
        if rec is None or rec.get("destroyed") or workspace_id in _state["destroyed"]:
            raise RuntimeError("run.destroyed")
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(work),
            env=env,
            start_new_session=True,
            preexec_fn=_preexec_pdeathsig,
            bufsize=0,
        )
        rec["proc"] = proc
        try:
            rec["pgid"] = os.getpgid(proc.pid)
        except OSError:
            rec["pgid"] = proc.pid
        pgids = rec.setdefault("pgids", [])
        if isinstance(rec["pgid"], int) and rec["pgid"] > 0 and rec["pgid"] not in pgids:
            pgids.append(rec["pgid"])
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
    rec = _run_record(workspace_id)
    if rec is None or str(rec.get("mode") or "") != "pi":
        try:
            send_close(ws)
        except Exception as exc:  # noqa: BLE001
            del exc
        try:
            ws.close()
        except Exception as exc:  # noqa: BLE001
            del exc
        return
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
        if path in {"/healthz", "/health"}:
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
            "/v1/internal/workenv/ls": list_work_files,
            "/v1/internal/workenv/read": read_work_file,
            "/v1/internal/workenv/exec": exec_work,
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
