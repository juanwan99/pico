"""Supreme law + work method must stay at the front of AGENTS.md and LAW."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_agents_md_opens_with_supreme_ban() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "禁止自搞一套体系" in text
    assert "禁止做重体系" in text
    head = text[:1600]
    assert "禁止自搞一套体系" in head
    assert "本窗合一" in head
    assert "GitHub Issue/PR/SHA/CI" in head
    assert "写码 /home/ops/pico" in head
    assert "生产 /opt/pico" in head
    assert "主管/执行者两套编制" in head
    assert "只有 origin/main 是生产线" in head
    assert "旁支不准部" in head
    assert "必须 prod-update" in head
    assert "docs-only 不部" in head
    assert "只开 squash" in head
    assert "关卡关键字" in head
    assert "删本任务本地枝" in head
    assert "旧窗摘要" in head
    assert "已合头枝不是在飞" in head


def test_law_supreme_section_exists() -> None:
    text = (ROOT / "docs" / "LAW-NO-SELF-BUILD-THIN-ADAPTER.md").read_text(encoding="utf-8")
    assert "## 0-supreme. 最高要求" in text
    assert "绝对禁止自己搞一套体系" in text
    assert "绝对禁止做重体系" in text
    assert "只允许对成熟上游做薄适配" in text
    assert "最高句（禁止自搞一套 / 禁止重体系）" in text
    assert "工作法不另起文件" in text


def test_truth_freeze_has_s0_and_w0() -> None:
    text = (ROOT / "docs" / "TRUTH-FREEZE.md").read_text(encoding="utf-8")
    assert "BINDING FREEZE v1.6" in text
    assert "| S0 |" in text
    assert "| W0 |" in text
    assert "绝对禁止自己搞一套体系" in text
    assert "本窗合一" in text
    assert "唯一真源" in text


def test_workenv_stage_plan_exists() -> None:
    text = (ROOT / "docs" / "PLAN-WORKENV-UPSTREAM.md").read_text(encoding="utf-8")
    assert "成熟上游" in text
    assert "B1" in text
    assert "PICO_WORKENV" in text


def test_state_now_is_index_not_second_ledger() -> None:
    text = (ROOT / "docs" / "STATE-NOW.md").read_text(encoding="utf-8")
    assert "在飞: 无" in text
    assert "GitHub Issue/PR/SHA/CI + 公网 tip" in text
    assert "本页三行是索引" in text
    assert "写码 `/home/ops/pico`" in text
    assert "生产 `/opt/pico`" in text
