"""Pure policy for pi-runner: settings, workspace paths, docker argv.

No I/O here so every isolation rule is unit-testable without Docker.
The runner is Pico-trusted code that manages containers; the workspace
container is where the model runs and gets nothing but its own directory,
two per-run tokens and the public internet.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# Env keys a workspace container may receive. Everything else is dropped:
# the model can `env` inside the box, so no long-lived secret may pass.
ALLOWED_ENV_KEYS = frozenset(
    {
        "PICO_TRUE_PI_TOOL_URL",
        "PICO_TRUE_PI_TOOL_TOKEN",
        "PICO_TRUE_PI_RUN_ID",
        "PICO_TRUE_PI_VISIBLE_TOOLS",
        "OPENAI_API_KEY",
        "PI_CODING_AGENT_DIR",
        "PI_MEMORY_DIR",
        "PI_AUTOCOMMIT",
    }
)

# Workspace files pico-api may seed before start (Pi settings only).
SEED_PREFIXES = (".pico/agent/", ".pi/")
# Files pico-api may upload / download over the control API.
UPLOAD_PREFIXES = ("attachments/",)
DOWNLOAD_PREFIXES = ("outputs/", "attachments/")

WORKSPACE_MOUNT = "/workspace"
MEMORY_MOUNT = "/memory"
CONTAINER_UID = "65532:65532"

_KEY_PART = re.compile(r"^[a-f0-9]{8,64}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


class PolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class RunnerSettings:
    token: str
    upstream: str = "http://127.0.0.1:18765"
    workspace_root: Path = Path("/var/lib/pico/workspaces")
    image: str = "pico-workspace:v1"
    network: str = "pico-ws"
    runtime: str = "runsc"
    memory: str = "1536m"
    cpus: str = "1.5"
    pids: int = 256
    tmp_size: str = "512m"
    home_size: str = "512m"
    workspace_max_mb: int = 2048
    max_sessions: int = 6
    max_per_school: int = 3
    min_free_mb: int = 3072
    ttl_days: int = 7
    dns: tuple[str, ...] = ("223.5.5.5", "119.29.29.29")
    control_host: str = "127.0.0.1"
    control_port: int = 18790
    proxy_host: str = "172.30.250.1"
    proxy_port: int = 18791
    extra_labels: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> RunnerSettings:
        token = os.environ.get("PICO_RUNNER_TOKEN", "").strip()
        if len(token) < 24:
            raise PolicyError("runner.token", "PICO_RUNNER_TOKEN must be set (>=24 chars)")
        dns = tuple(
            d.strip()
            for d in os.environ.get("PICO_RUNNER_DNS", "223.5.5.5,119.29.29.29").split(",")
            if d.strip()
        )
        return cls(
            token=token,
            upstream=os.environ.get("PICO_RUNNER_UPSTREAM", "http://127.0.0.1:18765").rstrip("/"),
            workspace_root=Path(
                os.environ.get("PICO_RUNNER_WS_ROOT", "/var/lib/pico/workspaces")
            ),
            image=os.environ.get("PICO_RUNNER_IMAGE", "pico-workspace:v1"),
            network=os.environ.get("PICO_RUNNER_NETWORK", "pico-ws"),
            runtime=os.environ.get("PICO_RUNNER_RUNTIME", "runsc"),
            memory=os.environ.get("PICO_RUNNER_MEM", "1536m"),
            cpus=os.environ.get("PICO_RUNNER_CPUS", "1.5"),
            pids=_env_int("PICO_RUNNER_PIDS", 256),
            workspace_max_mb=_env_int("PICO_RUNNER_WS_MAX_MB", 2048),
            max_sessions=_env_int("PICO_RUNNER_MAX_SESSIONS", 6),
            max_per_school=_env_int("PICO_RUNNER_MAX_PER_SCHOOL", 3),
            min_free_mb=_env_int("PICO_RUNNER_MIN_FREE_MB", 3072),
            ttl_days=_env_int("PICO_RUNNER_TTL_DAYS", 7),
            dns=dns or ("223.5.5.5",),
            control_host=os.environ.get("PICO_RUNNER_CONTROL_HOST", "127.0.0.1"),
            control_port=_env_int("PICO_RUNNER_CONTROL_PORT", 18790),
            proxy_host=os.environ.get("PICO_RUNNER_PROXY_HOST", "172.30.250.1"),
            proxy_port=_env_int("PICO_RUNNER_PROXY_PORT", 18791),
        )


@dataclass(frozen=True)
class WorkspaceKey:
    """Hashed tenant path. pico-api hashes; the runner only validates shape."""

    school: str
    member: str
    conv: str

    @classmethod
    def parse(cls, school: str, member: str, conv: str) -> WorkspaceKey:
        for part in (school, member, conv):
            if not _KEY_PART.match(str(part or "")):
                raise PolicyError("runner.bad_key", "workspace key must be lowercase hex")
        return cls(school=school, member=member, conv=conv)

    def workspace_dir(self, root: Path) -> Path:
        return root / self.school / self.member / self.conv

    def memory_dir(self, root: Path) -> Path:
        return root / self.school / self.member / "_memory"


def validate_run_id(run_id: str) -> str:
    rid = str(run_id or "")
    if not _RUN_ID.match(rid):
        raise PolicyError("runner.bad_run_id", "run_id must be [A-Za-z0-9_-]{1,80}")
    return rid


def safe_relpath(rel: str, *, prefixes: tuple[str, ...]) -> PurePosixPath:
    """Relative path inside the workspace under one of ``prefixes``."""
    text = str(rel or "").replace("\\", "/").strip()
    if not text or text.startswith("/") or "\x00" in text:
        raise PolicyError("runner.bad_path", "path must be relative")
    path = PurePosixPath(text)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise PolicyError("runner.bad_path", "path must not contain . or ..")
    if not any(text.startswith(p) for p in prefixes):
        raise PolicyError("runner.bad_path", f"path must start with one of {prefixes}")
    if len(text) > 400:
        raise PolicyError("runner.bad_path", "path too long")
    return path


def filter_env(env: dict[str, str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (env or {}).items():
        if key not in ALLOWED_ENV_KEYS:
            continue
        text = str(value)
        if "\n" in text or "\x00" in text or len(text) > 8192:
            raise PolicyError("runner.bad_env", f"bad env value for {key}")
        out[key] = text
    return out


def validate_pi_args(args: list[str] | None) -> list[str]:
    if not isinstance(args, list) or not args or len(args) > 64:
        raise PolicyError("runner.bad_args", "pi args must be a non-empty list")
    out: list[str] = []
    for item in args:
        text = str(item)
        if "\x00" in text or len(text) > 4096:
            raise PolicyError("runner.bad_args", "bad pi arg")
        out.append(text)
    if "--mode" not in out or "rpc" not in out:
        raise PolicyError("runner.bad_args", "pi must run in --mode rpc")
    return out


def container_name(run_id: str) -> str:
    return f"pico-ws-{validate_run_id(run_id)}".lower()


def docker_run_argv(
    settings: RunnerSettings,
    *,
    run_id: str,
    key: WorkspaceKey,
    pi_args: list[str],
    env_file: Path,
    with_memory: bool,
) -> list[str]:
    """``docker run`` argv for one workspace container.

    Isolation contract (card #1093): gVisor runtime, non-root, no
    capabilities, no privilege escalation, read-only root, bounded
    CPU/memory/pids, only the workspace (and member memory) mounted, own
    network, public DNS. Never docker.sock, never host network.
    """
    ws = key.workspace_dir(settings.workspace_root)
    argv = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--name",
        container_name(run_id),
        "--label",
        "pico.ws=1",
        "--label",
        f"pico.ws.school={key.school}",
        "--label",
        f"pico.ws.run={validate_run_id(run_id)}",
        "--runtime",
        settings.runtime,
        "--network",
        settings.network,
        "--user",
        CONTAINER_UID,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--read-only",
        "--tmpfs",
        f"/tmp:rw,nosuid,nodev,size={settings.tmp_size}",
        "--tmpfs",
        f"/home/pi:rw,nosuid,nodev,size={settings.home_size},uid=65532,gid=65532",
        "--memory",
        settings.memory,
        "--memory-swap",
        settings.memory,
        "--cpus",
        settings.cpus,
        "--pids-limit",
        str(settings.pids),
        "--ulimit",
        "nofile=4096:4096",
        "--env-file",
        str(env_file),
        "-e",
        "HOME=/home/pi",
        "-e",
        "PIP_USER=1",
        "-v",
        f"{ws}:{WORKSPACE_MOUNT}:rw",
        "-w",
        WORKSPACE_MOUNT,
    ]
    for server in settings.dns:
        argv.extend(["--dns", server])
    if with_memory:
        argv.extend(["-v", f"{key.memory_dir(settings.workspace_root)}:{MEMORY_MOUNT}:rw"])
    argv.append(settings.image)
    argv.append("pi")
    argv.extend(pi_args)
    return argv
