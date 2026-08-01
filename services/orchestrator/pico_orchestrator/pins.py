"""Pinned versions of kimi-agent-sdk / kimi-cli (install freeze).

These pins do NOT prove the open-source Kimi Agent runtime is the execution path.
Today they support version lock + safety yaml loading (see safety.py).
Execution path: transitional runner.py until Kimi Agent is truly wired
(docs/TRUTH-FREEZE.md O1–O3, debt D8).
"""

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
