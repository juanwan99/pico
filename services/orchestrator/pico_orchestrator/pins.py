"""Runtime identity + optional legacy Kimi package pins.

Product default multi-step kernel = Pi (pico_orchestrator.pi_runtime).
kimi-agent-sdk / kimi-cli pins only matter when legacy Kimi path is enabled.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

PINNED_KIMI_AGENT_SDK = "0.0.5"
PINNED_KIMI_CLI = "1.12.0"

AGENT_PINS = {
    "default_runtime": "pi-agent",
    "kimi-agent-sdk": PINNED_KIMI_AGENT_SDK,  # legacy optional
    "kimi-cli": PINNED_KIMI_CLI,  # legacy optional + safety yaml loader
}


def installed_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {"default_runtime": "pi-agent"}
    for name in ("kimi-agent-sdk", "kimi-cli"):
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = None
    return out


def assert_pins() -> None:
    """Legacy pin check — only hard-fails when packages are installed at wrong version.

    Pi path does not require kimi packages. Mismatch on installed legacy packages still fails.
    """
    installed = installed_versions()
    mismatches: list[str] = []
    for name, expected in (
        ("kimi-agent-sdk", PINNED_KIMI_AGENT_SDK),
        ("kimi-cli", PINNED_KIMI_CLI),
    ):
        got = installed.get(name)
        if got is None:
            continue  # optional for Pi-only deploys
        if got != expected:
            mismatches.append(f"{name}: expected {expected}, got {got!r}")
    if mismatches:
        raise RuntimeError("Agent pin mismatch: " + "; ".join(mismatches))
