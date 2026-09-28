"""Red-team probe for workspace boxes (card #1093 acceptance).

Run on the production host inside the runner container (it has the docker
CLI and the exact isolation argv):

    docker compose -f docker-compose.host.yml exec pi-runner python -m pi_runner.attack_test

Starts one box with ``docker_run_argv`` (same flags as a real session) but
runs a probe script instead of Pi. Every escape attempt must fail and the
public internet must work. Exit 0 only if all checks pass.
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from pi_runner.policy import RunnerSettings, WorkspaceKey, docker_run_argv, write_resolv_conf

PROBE = r'''
import json, os, platform, socket, ssl, subprocess, sys, urllib.request
targets = json.loads(sys.argv[1])
out = {}
def tcp(host, port, t=3.0):
    try:
        s = socket.create_connection((host, port), timeout=t); s.close(); return True
    except Exception:
        return False
out["uid"] = os.getuid()
out["kernel"] = platform.release()
secret_words = ("SECRET", "PASSWORD", "MASTER", "ADMIN", "DEEPSEEK", "MEILI", "SUB2API", "PROXY_KEY")
out["secret_env"] = sorted(k for k in os.environ if any(w in k.upper() for w in secret_words))
out["docker_sock"] = os.path.exists("/var/run/docker.sock") or os.path.exists("/run/docker.sock")
host_markers = [p for p in ("/var/lib/pico/workspaces", "/home/ops", "/etc/docker", "/opt/pico/.git",
                            "/opt/pico/.env", "/opt/pico/docker-compose.host.yml", "/root/.ssh")
                if os.path.exists(p)]
allowed_mounts = {"/workspace", "/memory", "/etc/resolv.conf", "/etc/hosts", "/etc/hostname",
                  "/", "/proc", "/sys", "/dev", "/dev/pts", "/dev/shm", "/dev/mqueue", "/tmp", "/home/pi",
                  "/sys/fs/cgroup"}
mounts = []
with open("/proc/mounts") as fh:
    for ln in fh:
        parts = ln.split()
        if len(parts) > 1:
            mounts.append(parts[1])
out["host_paths_visible"] = host_markers + sorted(m for m in mounts if m not in allowed_mounts
                                                  and not m.startswith(("/proc/", "/sys/", "/dev/")))
def can_write(path):
    try:
        with open(path, "w") as fh: fh.write("x")
        return True
    except Exception:
        return False
out["write_root"] = can_write("/etc/pico-probe")
out["write_workspace"] = can_write("/workspace/probe.txt")
out["blocked"] = {f"{h}:{p}": tcp(h, p) for h, p in targets["must_fail"]}
out["proxy"] = tcp(targets["proxy"][0], targets["proxy"][1])
out["control"] = tcp(targets["control"][0], targets["control"][1])
try:
    out["dns"] = bool(socket.gethostbyname("mirrors.aliyun.com"))
except Exception:
    out["dns"] = False
try:
    with urllib.request.urlopen("https://mirrors.aliyun.com/pypi/simple/pip/", timeout=15) as r:
        out["internet"] = r.status == 200
except Exception as exc:
    out["internet"] = False
out["smtp"] = tcp("smtp.qq.com", 25, 5)
# Fork pressure: must hit the pids limit, box must survive.
procs, n = [], 0
try:
    for n in range(2000):
        procs.append(subprocess.Popen(["sleep", "30"]))
except Exception:
    pass
out["forks_before_limit"] = len(procs)
for p in procs:
    p.kill()
# tmpfs bound: writing 700MB into /tmp must fail.
try:
    with open("/tmp/fill", "wb") as fh:
        for _ in range(700):
            fh.write(b"\0" * (1 << 20))
    out["tmp_unbounded"] = True
except Exception:
    out["tmp_unbounded"] = False
print("PROBE" + json.dumps(out))
'''


def _iface_ips() -> list[str]:
    ips: list[str] = []
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for name in os.listdir("/sys/class/net"):
        try:
            packed = fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", name[:15].encode()))
            ips.append(socket.inet_ntoa(packed[20:24]))
        except OSError:
            continue
    return sorted({ip for ip in ips if not ip.startswith("127.")})


def main() -> int:
    settings = RunnerSettings.from_env()
    write_resolv_conf(settings)
    host_ips = _iface_ips()
    must_fail: list[tuple[str, int]] = [
        ("100.100.100.200", 80),  # Aliyun metadata
        ("169.254.169.254", 80),
        ("100.100.2.136", 53),  # Aliyun internal DNS
    ]
    for ip in host_ips:
        if ip == settings.proxy_host:
            continue
        for port in (22, 80, 443, 3000, 5432, 6379, 7700, 18088, 18765, 18790, 27017):
            must_fail.append((ip, port))
    must_fail.append((settings.proxy_host, 22))
    must_fail.append((settings.proxy_host, 3000))
    targets = {
        "must_fail": must_fail,
        "proxy": [settings.proxy_host, settings.proxy_port],
        "control": [settings.proxy_host, settings.control_port],
    }
    key = WorkspaceKey.parse("0" * 32, "0" * 32, "a77ac4" + "0" * 26)
    ws = key.workspace_dir(settings.workspace_root)
    ws.mkdir(parents=True, exist_ok=True)
    os.lchown(ws, 65532, 65532)
    with tempfile.NamedTemporaryFile("w", delete=False, prefix="pico-ws-env-") as fh:
        fh.write("OPENAI_API_KEY=per-run-dummy\nPICO_TRUE_PI_TOOL_TOKEN=per-run-dummy\n")
        env_path = fh.name
    argv = docker_run_argv(
        settings,
        run_id="attack-test",
        key=key,
        pi_args=["--mode", "rpc"],
        env_file=Path(env_path),
        with_memory=False,
    )
    # Same isolation flags, probe instead of Pi. Relabel so the runner's
    # orphan reaper (label pico.ws=1, no live session) leaves the probe alone.
    cut = argv.index(settings.image) + 1
    argv = [
        "pico.ws.attack=1" if a == "pico.ws=1" else a for a in argv[:cut] if a != "-i"
    ] + ["python3", "-c", PROBE, json.dumps(targets)]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=600, check=False)
    finally:
        os.unlink(env_path)
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE")), "")
    if not line:
        print(json.dumps({"ok": False, "error": "probe produced no result", "rc": proc.returncode,
                          "stdout": proc.stdout[-1000:], "stderr": proc.stderr[-2000:]}))
        return 1
    got = json.loads(line[5:])
    checks = {
        "non_root": got["uid"] != 0,
        "gvisor_kernel": "gvisor" in got["kernel"] or got["kernel"].startswith("4.4.0"),
        "no_secret_env": not got["secret_env"],
        "no_docker_sock": not got["docker_sock"],
        "no_host_paths": not got["host_paths_visible"],
        "root_fs_read_only": not got["write_root"],
        "workspace_writable": got["write_workspace"],
        "internal_blocked": not any(got["blocked"].values()),
        "proxy_reachable": got["proxy"],
        "runner_control_blocked": not got["control"],
        "dns_ok": got["dns"],
        "internet_ok": got["internet"],
        "smtp_blocked": not got["smtp"],
        "pids_bounded": got["forks_before_limit"] < settings.pids,
        "tmp_bounded": not got["tmp_unbounded"],
    }
    leaks = sorted(k for k, v in got["blocked"].items() if v)
    report = {"ok": all(checks.values()), "checks": checks, "leaks": leaks, "host_ips": host_ips,
              "kernel": got["kernel"], "forks": got["forks_before_limit"],
              "host_paths": got["host_paths_visible"]}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
