"""#867: supreme law must stay at the front of AGENTS.md and LAW."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_agents_md_opens_with_supreme_ban() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "禁止自搞一套体系" in text
    assert "禁止做重体系" in text
    head = text[:1200]
    assert "禁止自搞一套体系" in head


def test_law_supreme_section_exists() -> None:
    text = (ROOT / "docs" / "LAW-NO-SELF-BUILD-THIN-ADAPTER.md").read_text(encoding="utf-8")
    assert "## 0-supreme. 最高要求" in text
    assert "绝对禁止自己搞一套体系" in text
    assert "绝对禁止做重体系" in text
    assert "只允许对成熟上游做薄适配" in text
    assert "最高句（禁止自搞一套 / 禁止重体系）" in text


def test_truth_freeze_v14_has_s0() -> None:
    text = (ROOT / "docs" / "TRUTH-FREEZE.md").read_text(encoding="utf-8")
    assert "BINDING FREEZE v1.4" in text
    assert "| S0 |" in text
    assert "绝对禁止自己搞一套体系" in text
