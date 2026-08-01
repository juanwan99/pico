"""S2/D1 safety: Shell/File/Web/MCP off in pinned agent config."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "services/orchestrator/agents/pico.yaml"
KIMI_RUNTIME_AGENT = ROOT / "services/orchestrator/agents/pico-kimi-runtime.yaml"


def test_agent_file_exists() -> None:
    assert AGENT.is_file(), f"missing {AGENT}"


def test_dangerous_tools_off() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
    from pico_orchestrator.safety import (
        DANGEROUS_TOOL_PATHS,
        assert_dangerous_tools_off,
        load_pico_agent_tools,
    )

    tools = load_pico_agent_tools(AGENT)
    for d in DANGEROUS_TOOL_PATHS:
        assert d not in tools
    proof = assert_dangerous_tools_off(AGENT)
    assert proof["dangerous_off"] is True
    assert proof["mcp_configured"] is False
    assert proof["violations"] == []


def test_agent_yaml_has_no_shell_file_web_literals() -> None:
    text = AGENT.read_text(encoding="utf-8")
    # tools: [] section must not list host capabilities as enabled entries
    # (exclude_tools listing them is OK and expected)
    import yaml

    data = yaml.safe_load(text)
    tools = data["agent"].get("tools") or []
    joined = "\n".join(tools)
    assert "shell:Shell" not in joined
    assert "tools.file:" not in joined
    assert "tools.web:" not in joined


def test_flagged_kimi_agent_exposes_only_gateway_wrappers() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
    from kimi_cli.agentspec import load_agent_spec
    from pico_orchestrator.safety import DANGEROUS_TOOL_PATHS, assert_dangerous_tools_off

    spec = load_agent_spec(KIMI_RUNTIME_AGENT)
    assert spec.tools
    assert all(path.startswith("pico_orchestrator.kimi_tools:") for path in spec.tools)
    assert DANGEROUS_TOOL_PATHS.issubset(set(spec.exclude_tools))
    assert spec.subagents == {}
    system_template = spec.system_prompt_path.read_text(encoding="utf-8")
    assert "${ROLE_ADDITIONAL}" in system_template
    assert "{{ROLE_ADDITIONAL}}" not in system_template
    proof = assert_dangerous_tools_off(KIMI_RUNTIME_AGENT)
    assert proof["dangerous_off"] is True
    assert proof["mcp_configured"] is False
