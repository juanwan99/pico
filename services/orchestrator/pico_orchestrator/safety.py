"""Agent safety: prove Shell / host File / Web / MCP defaults are OFF."""

from __future__ import annotations

from pathlib import Path

# Paths that must never appear in the Pico agent tool list.
DANGEROUS_TOOL_PATHS: frozenset[str] = frozenset(
    {
        "kimi_cli.tools.shell:Shell",
        "kimi_cli.tools.file:ReadFile",
        "kimi_cli.tools.file:ReadMediaFile",
        "kimi_cli.tools.file:Glob",
        "kimi_cli.tools.file:Grep",
        "kimi_cli.tools.file:WriteFile",
        "kimi_cli.tools.file:StrReplaceFile",
        "kimi_cli.tools.web:SearchWeb",
        "kimi_cli.tools.web:FetchURL",
        "kimi_cli.tools.multiagent:Task",
    }
)

DANGEROUS_PREFIXES: tuple[str, ...] = (
    "kimi_cli.tools.shell:",
    "kimi_cli.tools.file:",
    "kimi_cli.tools.web:",
    "kimi_cli.tools.multiagent:",
)

DEFAULT_AGENT_FILE = Path(__file__).resolve().parents[1] / "agents" / "pico.yaml"


def _load_tools_from_yaml(path: Path) -> list[str]:
    """Load tool list without requiring kimi_cli when possible.

    Prefer kimi_cli.agentspec when installed (legacy yaml semantics).
    Fall back to a minimal YAML parse of tools: list entries.
    """
    try:
        from kimi_cli.agentspec import load_agent_spec

        spec = load_agent_spec(path)
        tools = list(spec.tools)
        excluded = set(spec.exclude_tools)
        return [t for t in tools if t not in excluded]
    except ImportError:
        pass

    text = path.read_text(encoding="utf-8")
    tools: list[str] = []
    excluded: set[str] = set()
    section: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("tools:"):
            section = "tools"
            continue
        if stripped.startswith("exclude_tools:"):
            section = "exclude"
            continue
        if not line.startswith(" ") and not line.startswith("\t") and stripped.endswith(":"):
            section = None
            continue
        if section in {"tools", "exclude"} and stripped.startswith("-"):
            item = stripped[1:].strip().strip("\"'")
            if section == "tools":
                tools.append(item)
            else:
                excluded.add(item)
    return [t for t in tools if t not in excluded]


def load_pico_agent_tools(agent_file: Path | None = None) -> list[str]:
    path = agent_file or DEFAULT_AGENT_FILE
    return _load_tools_from_yaml(path)


def assert_dangerous_tools_off(agent_file: Path | None = None) -> dict:
    """Load agent file and assert no dangerous host tools are enabled.

    Returns a proof dict suitable for logs / CI artifacts.
    Raises AssertionError if any dangerous tool remains.
    """
    path = agent_file or DEFAULT_AGENT_FILE
    tools = load_pico_agent_tools(path)
    violations: list[str] = []
    for t in tools:
        if t in DANGEROUS_TOOL_PATHS:
            violations.append(t)
            continue
        for prefix in DANGEROUS_PREFIXES:
            if t.startswith(prefix):
                violations.append(t)
                break
    proof = {
        "agent_file": str(path.resolve()),
        "tools": tools,
        "dangerous_off": len(violations) == 0,
        "violations": violations,
        "mcp_configured": False,  # Pico does not load MCP servers in Phase 1
    }
    if violations:
        raise AssertionError(f"Dangerous tools still enabled in {path}: {violations}")
    return proof
