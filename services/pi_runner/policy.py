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
    workspace_max_files: int = 20000
    member_max_mb: int = 5120
    max_session_s: int = 8 * 3600
    # Idle boxes cost ~60-90MB (gVisor + Pi); 1.5G/1.5 CPU are per-box caps,
    # not reservations. 12 x 1.5G fits the shared host even with no slice
    # limits; raise (e.g. 32 / 24) once host-setup --slices put the shared
    # memory ceiling in place (card #1135).
    max_sessions: int = 12
    max_per_school: int = 9
    min_free_mb: int = 3072
    # Host MemAvailable floor: below it no new box starts (requests queue).
    min_avail_mb: int = 3072
    # Full runner = wait in line, not fail (card #1135).
    queue_wait_s: int = 1200
    queue_max: int = 200
    # Every box under one systemd slice; its limits (host-setup step 5) are the
    # pooled CPU/memory budget that keeps the shared host's production safe.
    cgroup_parent: str = "pico-ws.slice"
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
        runtime = os.environ.get("PICO_RUNNER_RUNTIME", "runsc")
        if runtime != "runsc" and os.environ.get("PICO_RUNNER_ALLOW_UNSAFE_RUNTIME") != "1":
            # Boxes run untrusted model commands; plain runc shares the host kernel.
            raise PolicyError("runner.runtime", f"refusing runtime {runtime!r}; boxes need runsc")
        return cls(
            token=token,
            upstream=os.environ.get("PICO_RUNNER_UPSTREAM", "http://127.0.0.1:18765").rstrip("/"),
            workspace_root=Path(
                os.environ.get("PICO_RUNNER_WS_ROOT", "/var/lib/pico/workspaces")
            ),
            image=os.environ.get("PICO_RUNNER_IMAGE", "pico-workspace:v1"),
            network=os.environ.get("PICO_RUNNER_NETWORK", "pico-ws"),
            runtime=runtime,
            memory=os.environ.get("PICO_RUNNER_MEM", "1536m"),
            cpus=os.environ.get("PICO_RUNNER_CPUS", "1.5"),
            pids=_env_int("PICO_RUNNER_PIDS", 256),
            workspace_max_mb=_env_int("PICO_RUNNER_WS_MAX_MB", 2048),
            workspace_max_files=_env_int("PICO_RUNNER_WS_MAX_FILES", 20000),
            member_max_mb=_env_int("PICO_RUNNER_MEMBER_MAX_MB", 5120),
            max_session_s=_env_int("PICO_RUNNER_MAX_SESSION_S", 8 * 3600),
            max_sessions=_env_int("PICO_RUNNER_MAX_SESSIONS", 12),
            max_per_school=_env_int("PICO_RUNNER_MAX_PER_SCHOOL", 9),
            min_free_mb=_env_int("PICO_RUNNER_MIN_FREE_MB", 3072),
            min_avail_mb=_env_int("PICO_RUNNER_MIN_AVAIL_MB", 3072),
            queue_wait_s=_env_int("PICO_RUNNER_QUEUE_WAIT_S", 1200),
            queue_max=_env_int("PICO_RUNNER_QUEUE_MAX", 200),
            cgroup_parent=os.environ.get("PICO_RUNNER_CGROUP_PARENT", "pico-ws.slice").strip(),
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


# Every this-many seconds in line counts as one box fewer for the school, so
# a busy school's request is not passed over until the line gives up.
QUEUE_AGE_STEP_S = 120.0


def queue_order(waiting: list[tuple[str, float]], active: dict[str, int], now: float) -> list[int]:
    """Indices of ``waiting`` ((school, since) pairs) in admission order.

    The school running fewest boxes goes first (time in line lowers that
    count), then first come first served: a busy school fills idle capacity
    but cannot starve another school, and is not starved itself.
    """

    def rank(i: int) -> tuple[int, float, int]:
        school, since = waiting[i]
        aged = int(max(0.0, now - since) // QUEUE_AGE_STEP_S)
        return (active.get(school, 0) - aged, since, i)

    return sorted(range(len(waiting)), key=rank)


def mem_available_mb(meminfo: str) -> int | None:
    """``MemAvailable`` from /proc/meminfo text (a container sees the host's)."""
    for line in meminfo.splitlines():
        if line.startswith("MemAvailable:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) // 1024
    return None


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


RESOLV_NAME = ".pico-resolv.conf"


def resolv_conf_path(settings: RunnerSettings) -> Path:
    return settings.workspace_root / RESOLV_NAME


def resolv_conf_text(settings: RunnerSettings) -> str:
    return "".join(f"nameserver {d}\n" for d in settings.dns) + "options timeout:2 attempts:2\n"


def write_resolv_conf(settings: RunnerSettings) -> Path:
    """Public resolvers for boxes.

    gVisor's netstack skips the in-namespace NAT that routes Docker's embedded
    DNS (127.0.0.11) on user-defined networks, so boxes get their own
    resolv.conf instead of relying on --dns.
    """
    path = resolv_conf_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(resolv_conf_text(settings), encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    return path


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
    ]
    if settings.cgroup_parent:
        argv.extend(["--cgroup-parent", settings.cgroup_parent])
    argv += [
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
        # stdout/stderr go to the runner pipe only; no json-file log on the host disk.
        "--log-driver",
        "none",
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
    argv.extend(["-v", f"{resolv_conf_path(settings)}:/etc/resolv.conf:ro"])
    if with_memory:
        argv.extend(["-v", f"{key.memory_dir(settings.workspace_root)}:{MEMORY_MOUNT}:rw"])
    argv.append(settings.image)
    argv.append("pi")
    argv.extend(pi_args)
    return argv
