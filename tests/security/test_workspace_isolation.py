"""Card #1093: Pi builtins only inside an isolated workspace box.

Host-spawned Pi (legacy / rollback) keeps --no-builtin-tools. The runner
box gets builtins but the docker argv must carry every isolation flag and
never the docker socket, host network or a long-lived secret.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))

from pi_runner.policy import (
    ALLOWED_ENV_KEYS,
    PolicyError,
    RunnerSettings,
    WorkspaceKey,
    docker_run_argv,
    filter_env,
    safe_relpath,
    validate_pi_args,
)
from pico_orchestrator.true_pi.client import SubprocessTransport

KEY = WorkspaceKey.parse("a" * 32, "b" * 32, "c" * 32)
SETTINGS = RunnerSettings(token="t" * 32, workspace_root=Path("/var/lib/pico/workspaces"))


def _argv(**kw) -> list[str]:
    return docker_run_argv(
        SETTINGS,
        run_id="run-1",
        key=KEY,
        pi_args=["--mode", "rpc"],
        env_file=Path("/tmp/env"),
        with_memory=kw.get("with_memory", False),
    )


def _flag(argv: list[str], name: str) -> list[str]:
    return [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == name]


def test_host_spawn_keeps_builtins_off(tmp_path: Path) -> None:
    t = SubprocessTransport(session_dir=tmp_path, tool_url="", tool_token="x", run_id="r")
    assert "--no-builtin-tools" in t.spawn_command()


def test_box_argv_isolation_flags() -> None:
    argv = _argv()
    assert _flag(argv, "--runtime") == ["runsc"]
    assert _flag(argv, "--network") == ["pico-ws"]
    assert _flag(argv, "--user") == ["65532:65532"]
    assert _flag(argv, "--cap-drop") == ["ALL"]
    assert "no-new-privileges:true" in _flag(argv, "--security-opt")
    assert "--read-only" in argv
    assert _flag(argv, "--memory") and _flag(argv, "--pids-limit") and _flag(argv, "--cpus")
    assert _flag(argv, "--env-file") == ["/tmp/env"]


def test_box_argv_never_mounts_socket_or_host() -> None:
    argv = _argv(with_memory=True)
    joined = " ".join(argv)
    assert "docker.sock" not in joined
    assert "--privileged" not in argv
    assert "host" not in _flag(argv, "--network")
    assert "--pid" not in argv and "--ipc" not in argv
    mounts = _flag(argv, "-v")
    assert mounts == [
        f"/var/lib/pico/workspaces/{'a' * 32}/{'b' * 32}/{'c' * 32}:/workspace:rw",
        f"/var/lib/pico/workspaces/{'a' * 32}/{'b' * 32}/_memory:/memory:rw",
    ]


def test_box_argv_env_values_not_on_command_line() -> None:
    argv = _argv()
    env_pairs = _flag(argv, "-e")
    assert all(not p.startswith(("OPENAI_API_KEY", "PICO_TRUE_PI_TOOL_TOKEN")) for p in env_pairs)


def test_env_filter_drops_secrets() -> None:
    env = filter_env(
        {
            "OPENAI_API_KEY": "per-run",
            "DEEPSEEK_API_KEY": "real",
            "MEILI_MASTER_KEY": "real",
            "SUB2API_ADMIN_API_KEY": "real",
            "PICO_OPENAI_PROXY_KEY": "real",
        }
    )
    assert env == {"OPENAI_API_KEY": "per-run"}
    assert not any("MASTER" in k or "ADMIN" in k or "PROXY_KEY" in k for k in ALLOWED_ENV_KEYS)


@pytest.mark.parametrize(
    "rel",
    ["../x", "/etc/passwd", "attachments/../../x", "outputs/a", ".pico/../attachments/x", ""],
)
def test_upload_path_rejects_escape(rel: str) -> None:
    with pytest.raises(PolicyError):
        safe_relpath(rel, prefixes=("attachments/",))


def test_workspace_key_must_be_hex() -> None:
    with pytest.raises(PolicyError):
        WorkspaceKey.parse("../etc", "b" * 32, "c" * 32)


def test_pi_args_must_be_rpc() -> None:
    with pytest.raises(PolicyError):
        validate_pi_args(["-p", "hi"])
