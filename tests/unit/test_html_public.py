"""T-HTML-PUBLIC: publish/collect plumbing, no scene prompts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.html_public import inject_collect_hook, normalize_collect_payload
from pico_orchestrator.true_pi.config import ALLOWED_GATEWAY_TOOLS
from pico_orchestrator.true_pi.runtime import pico_system_text


def test_collect_hook_is_plumbing_not_prompt():
    html = "<html><body><form><input name='n'></form></body></html>"
    out = inject_collect_hook(html)
    assert "__PICO_COLLECT__" in out
    assert "学生" not in out
    assert "教师" not in out
    assert "姓名" not in out
    again = inject_collect_hook(out)
    assert again.count("__PICO_COLLECT__") == 1


def test_collect_payload_caps():
    got = normalize_collect_payload({"n": "ok", "x": 1})
    assert got["n"] == "ok"
    assert got["x"] == 1
    with pytest.raises(ToolError):
        normalize_collect_payload({})
    with pytest.raises(ToolError):
        normalize_collect_payload({f"k{i}": i for i in range(40)})


def test_publish_tools_on_allowlist_and_system_stays_generic():
    assert "publish_html_page" in ALLOWED_GATEWAY_TOOLS
    assert "unpublish_html_page" in ALLOWED_GATEWAY_TOOLS
    assert "bash" not in ALLOWED_GATEWAY_TOOLS
    assert len(ALLOWED_GATEWAY_TOOLS) == 25
    body = pico_system_text()
    assert "publish_html_page" in body
    assert "这是什么" not in body
    assert "课件" not in body
    assert "学生端" not in body
    assert "教师看板" not in body
    assert "发布并收表" not in body
    assert "Do not publish unless the teacher asked" in body
