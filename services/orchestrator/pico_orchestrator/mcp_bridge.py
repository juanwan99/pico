"""P2 MCP allowlist bridge — safe tools only, no host shell / open web.

Controlled via ``PICO_MCP_ALLOWLIST`` (comma-separated tool names).
Empty allowlist → no MCP tools registered (fail closed for MCP surface).
Product default pilot: ``mcp_time,mcp_workspace_stat``.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from pico_orchestrator.gateway import ArtifactStore, Principal, ToolError, ToolSpec

# Safe pilot tools only — never shell/file/web/MCP-market open.
KNOWN_MCP_TOOLS = frozenset({"mcp_time", "mcp_workspace_stat"})
DEFAULT_MCP_ALLOWLIST = "mcp_time,mcp_workspace_stat"


def parse_mcp_allowlist(raw: str | None = None) -> list[str]:
    """Return ordered unique allowlisted MCP tool names (known subset only)."""
    if raw is None:
        raw = os.environ.get("PICO_MCP_ALLOWLIST", DEFAULT_MCP_ALLOWLIST)
    seen: set[str] = set()
    out: list[str] = []
    for part in (raw or "").split(","):
        name = part.strip()
        if not name or name in seen:
            continue
        if name not in KNOWN_MCP_TOOLS:
            continue
        seen.add(name)
        out.append(name)
    return out


def mcp_health_fields(raw: str | None = None) -> dict[str, Any]:
    names = parse_mcp_allowlist(raw)
    return {
        "mcp_allowlist_enabled": len(names) > 0,
        "mcp_allowlist_count": len(names),
        "mcp_tools": names,
    }


async def _mcp_time(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
    del principal, args
    now = datetime.now(UTC).replace(microsecond=0)
    return {
        "mcp": "mcp_time",
        "server": "pico-mcp-bridge",
        "utc": now.isoformat().replace("+00:00", "Z"),
        "note": "allowlisted MCP bridge · clock only",
    }


def _workspace_stat_handler(store: ArtifactStore):
    async def _mcp_workspace_stat(
        principal: Principal, args: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            limit = int(args.get("limit") or 50)
        except (TypeError, ValueError) as exc:
            raise ToolError("tool.invalid_arguments", "limit must be an integer") from exc
        if not 1 <= limit <= 100:
            raise ToolError("tool.invalid_arguments", "limit must be between 1 and 100")
        artifacts = await store.list(principal, limit=limit)
        by_kind: dict[str, int] = {}
        for art in artifacts:
            kind = str(art.get("kind") or "unknown")
            by_kind[kind] = by_kind.get(kind, 0) + 1
        return {
            "mcp": "mcp_workspace_stat",
            "server": "pico-mcp-bridge",
            "count": len(artifacts),
            "by_kind": by_kind,
            "titles": [str(a.get("title") or "")[:80] for a in artifacts[:10]],
            "note": "allowlisted MCP bridge · membership Artifact stats only",
        }

    return _mcp_workspace_stat


def mcp_tool_specs(store: ArtifactStore, allowlist: list[str] | None = None) -> list[ToolSpec]:
    """Build ToolSpec list for allowlisted MCP bridge tools."""
    names = allowlist if allowlist is not None else parse_mcp_allowlist()
    specs: list[ToolSpec] = []
    for name in names:
        if name == "mcp_time":
            specs.append(
                ToolSpec(
                    name="mcp_time",
                    description=(
                        "MCP allowlist bridge: return current UTC time. "
                        "No host access. Server=pico-mcp-bridge."
                    ),
                    handler=_mcp_time,
                    school_scoped=False,
                )
            )
        elif name == "mcp_workspace_stat":
            specs.append(
                ToolSpec(
                    name="mcp_workspace_stat",
                    description=(
                        "MCP allowlist bridge: summarize current membership Artifact "
                        "ledger (counts/kinds). No host filesystem."
                    ),
                    handler=_workspace_stat_handler(store),
                    school_scoped=False,
                )
            )
    return specs


def mcp_openai_parameters() -> dict[str, dict[str, Any]]:
    return {
        "mcp_time": {
            "type": "object",
            "properties": {},
        },
        "mcp_workspace_stat": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
        },
    }
