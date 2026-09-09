"""One tool contract, three surfaces (#919 root cause · #966).

The Pi-visible tool set lives in ``pico-gateway-tools.ts`` (what Pi registers),
``true_pi/config.py`` (what the gateway executes), and ``capability_loading.py``
(CORE / EXTENDED). ``system.md`` and skill docs talk about them. Drift between
any two is a real product bug (Pi calls a name Python refuses, or Python has a
verb Pi can never reach). Pin the relationships; do not generate one from the
other (that would be a second schema kernel).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.capability_loading import CORE_VISIBLE_TOOLS, EXTENDED_TOOLS
from pico_orchestrator.tools_builtin import build_default_gateway
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS, UNREGISTERED_OFFICE_TOOLS

TS_PATH = ROOT / "services" / "true_pi_bridge" / "pico-gateway-tools.ts"
TOOL_SERVER = ROOT / "services" / "orchestrator" / "pico_orchestrator" / "true_pi" / "tool_server.py"

# Served by the bridge tool server itself (HITL park), not a gateway ToolSpec.
BRIDGE_SERVED = frozenset({"ask_user"})
SYSTEM_MD = ROOT / "services" / "orchestrator" / "pico_orchestrator" / "agent_assets" / "system.md"
SKILL_DOCS = sorted(
    (ROOT / "services" / "orchestrator" / "pico_orchestrator" / "office" / "skills").glob("*.md")
)

# Generic exec verbs that must never be registered on any surface (no bash).
FORBIDDEN_VERBS = frozenset(
    {"bash", "shell", "exec", "run_python", "python", "sandbox_exec", "sandbox_workspace_exec"}
)

# Load-bearing phrases per tool: both the TS description (what Pi reads) and the
# Python description (what the gateway / hosted path reads) must carry them.
# These are product semantics, not prose style.
ANCHORS: dict[str, tuple[str, ...]] = {
    "sandbox_office_lib": ("pico-office", "OUTPUT_PATH", "stderr", "One call = one output file"),
    "read_office_skill": ("sandbox_office_lib", "python-docx / openpyxl / python-pptx"),
    "generate_html_document": ("pico-artifact:", "No CDN", "ok is not finished"),
    "verify_html_document": ("http(s)",),
    "generate_image": ("image_artifact_ids", "pico-artifact:<id>", "base64"),
    "generate_diagram": ("Sibling of generate_image", "veto", "image_artifact_ids"),
    "kb_search": ("honest_miss", "school materials", "Never invent"),
    "web_search": ("未检索",),
    "web_fetch": ("intranet",),
    "ask_user": ("2–5", "not inventing a goal"),
    "publish_html_page": ("Not a Pico capability", "fails closed", "Edu"),
    "unpublish_html_page": ("Pico does not publish",),
    "sandbox_document_open": ("OOXML", "PDF"),
    "sandbox_browser_open": ("PUBLIC", "passwords"),
    "workspace_read_file": ("re-upload", "png/jpg"),
}


def _ts_text() -> str:
    return TS_PATH.read_text(encoding="utf-8")


def _ts_allowed(ts: str) -> set[str]:
    block = re.search(r"const ALLOWED = \[(.*?)\] as const;", ts, re.DOTALL)
    assert block, "ALLOWED list missing in TS"
    return set(re.findall(r'"([a-z_]+)"', block.group(1)))


def _ts_registrations(ts: str) -> dict[str, tuple[str, set[str]]]:
    """name -> (description, schema property names)."""
    out: dict[str, tuple[str, set[str]]] = {}
    pattern = re.compile(
        r'registerTool\(\s*pi,\s*"([a-z_]+)",\s*"((?:[^"\\]|\\.)*)",\s*(.*?)\n  \);',
        re.DOTALL,
    )
    for name, desc, schema in pattern.findall(ts):
        if schema.strip().rstrip(",").strip() == "AnyArgs":
            props: set[str] = set()
        else:
            inner = re.search(r"Type\.Object\(\s*\{(.*?)\}\s*,", schema, re.DOTALL)
            assert inner, f"{name}: cannot parse Type.Object"
            props = set(re.findall(r"^\s*([a-z_]+):\s*Type\.", inner.group(1), re.MULTILINE))
        out[name] = (desc, props)
    return out


def _python_args(description: str) -> set[str] | None:
    m = re.search(r"Args:\s*(.+)$", description, re.DOTALL)
    if not m:
        return None
    # Only the Args sentence; prose after it ("Never invent citations.") is not a param.
    segment = re.split(r"\.(?:\s|$)", m.group(1), maxsplit=1)[0]
    tokens = re.split(r"[,|]", segment)
    names: set[str] = set()
    for tok in tokens:
        tok = tok.strip().rstrip(".")
        tok = re.sub(r"\s*\(.*?\)", "", tok)
        tok = tok.split("=")[0].strip().rstrip("?")
        if re.fullmatch(r"[a-z_]+", tok):
            names.add(tok)
    return names


def test_three_allowlists_are_one_set() -> None:
    ts_allowed = _ts_allowed(_ts_text())
    core, ext = set(CORE_VISIBLE_TOOLS), set(EXTENDED_TOOLS)
    assert not (core & ext), f"CORE ∩ EXTENDED must be empty: {core & ext}"
    assert core | ext == set(ALLOWED_GATEWAY_TOOLS), {
        "core∪ext − gateway": (core | ext) - set(ALLOWED_GATEWAY_TOOLS),
        "gateway − core∪ext": set(ALLOWED_GATEWAY_TOOLS) - (core | ext),
    }
    assert ts_allowed == set(ALLOWED_GATEWAY_TOOLS), {
        "ts − py": ts_allowed - set(ALLOWED_GATEWAY_TOOLS),
        "py − ts": set(ALLOWED_GATEWAY_TOOLS) - ts_allowed,
    }
    assert len(CORE_VISIBLE_TOOLS) == len(core), "duplicate in CORE"
    assert len(EXTENDED_TOOLS) == len(ext), "duplicate in EXTENDED"


def test_ts_registers_exactly_the_allowlist() -> None:
    ts = _ts_text()
    registered = set(_ts_registrations(ts))
    assert registered == _ts_allowed(ts), {
        "registered − allowed": registered - _ts_allowed(ts),
        "allowed − registered": _ts_allowed(ts) - registered,
    }


def test_python_gateway_executes_every_pi_tool_and_no_unregistered_alias() -> None:
    gw = build_default_gateway()
    names = set(gw.tools)
    server = TOOL_SERVER.read_text(encoding="utf-8")
    for name in BRIDGE_SERVED:
        assert f'if name == "{name}":' in server, f"{name} not served by tool_server"
        assert name not in names, f"{name} must not also be a gateway ToolSpec"
    missing = set(ALLOWED_GATEWAY_TOOLS) - names - BRIDGE_SERVED
    assert not missing, f"Pi can call these but gateway has no handler: {missing}"
    leaked = names & set(UNREGISTERED_OFFICE_TOOLS)
    assert not leaked, f"unregistered aliases back on the gateway: {leaked}"
    assert not (names & FORBIDDEN_VERBS), names & FORBIDDEN_VERBS
    assert not (set(ALLOWED_GATEWAY_TOOLS) & set(UNREGISTERED_OFFICE_TOOLS))


def test_ts_schema_props_are_known_to_python() -> None:
    gw = build_default_gateway()
    drift: dict[str, set[str]] = {}
    for name, (_desc, props) in _ts_registrations(_ts_text()).items():
        if name in BRIDGE_SERVED:
            continue
        py_args = _python_args(gw.tools[name].description)
        if py_args is None:
            continue
        extra = props - py_args
        if extra:
            drift[name] = extra
    assert not drift, f"TS exposes params Python description does not list: {drift}"


def test_load_bearing_phrases_on_both_surfaces() -> None:
    gw = build_default_gateway()
    ts_reg = _ts_registrations(_ts_text())
    missing: list[str] = []
    for name, phrases in ANCHORS.items():
        ts_desc = ts_reg[name][0]
        py_desc = None if name in BRIDGE_SERVED else gw.tools[name].description
        for phrase in phrases:
            if phrase not in ts_desc:
                missing.append(f"TS {name}: {phrase!r}")
            if py_desc is not None and phrase not in py_desc:
                missing.append(f"PY {name}: {phrase!r}")
    assert not missing, "\n".join(missing)


def test_unregistered_names_absent_from_model_facing_text() -> None:
    surfaces = {"system.md": SYSTEM_MD.read_text(encoding="utf-8"), "ts": _ts_text()}
    for doc in SKILL_DOCS:
        surfaces[doc.name] = doc.read_text(encoding="utf-8")
    hits: list[str] = []
    for label, text in surfaces.items():
        for name in sorted(UNREGISTERED_OFFICE_TOOLS):
            if re.search(rf"\b{re.escape(name)}\b", text):
                hits.append(f"{label}: {name}")
    assert not hits, "\n".join(hits)


def test_system_md_tool_names_are_pi_reachable() -> None:
    text = SYSTEM_MD.read_text(encoding="utf-8")
    gw = build_default_gateway()
    known = set(gw.tools) | set(UNREGISTERED_OFFICE_TOOLS) | FORBIDDEN_VERBS
    mentioned = {n for n in re.findall(r"`([a-z]+(?:_[a-z]+)+)`", text) if n in known}
    unreachable = mentioned - set(ALLOWED_GATEWAY_TOOLS)
    assert not unreachable, f"system.md tells Pi about tools it cannot call: {unreachable}"
