"""Pinned Kimi Agent SDK / runtime versions (D1 freeze)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

# Binding pins — must match requirements.txt / docs/D1-FREEZE.md
PINNED_KIMI_AGENT_SDK = "0.0.5"
PINNED_KIMI_CLI = "1.12.0"

AGENT_PINS = {
    "kimi-agent-sdk": PINNED_KIMI_AGENT_SDK,
    "kimi-cli": PINNED_KIMI_CLI,
}


def installed_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in AGENT_PINS:
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = None
    return out


def assert_pins() -> None:
    installed = installed_versions()
    mismatches: list[str] = []
    for name, expected in AGENT_PINS.items():
        got = installed.get(name)
        if got != expected:
            mismatches.append(f"{name}: expected {expected}, got {got!r}")
    if mismatches:
        raise RuntimeError("Agent pin mismatch: " + "; ".join(mismatches))
