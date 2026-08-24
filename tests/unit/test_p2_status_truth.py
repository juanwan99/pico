"""T-PACK-P2-STATUS-TRUTH: UI/banner/timeline/ledger share one truth.

Locks P2 root causes:
- RC-D: single-HTML multi-section prompts must not inflate min_artifacts.
- RC-A: when other-format files exist, the office banner must not claim
  "no downloadable file".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


def test_single_html_multi_section_routing_does_not_guess() -> None:
    """Routing never sets min from HTML section packing or explicit multi phrasing."""
    from app.openai_compat import _this_round_delivery_plan

    single_unit_prompts = [
        (
            "请做可下载 HTML 互动页「动物细胞结构标认」：标题、五个结构名称列表、"
            "两个按钮「随机高亮」「重置」。"
        ),
        "请做可下载 HTML 页面：大标题、三个区块、两个按钮。",
        "请生成可下载 HTML 课件：标题、五个结构名称列表、两个按钮。",
        (
            "请做一份可下载的 HTML 单页课件「太阳系行星介绍」：大标题、"
            "八颗行星各一节、两个交互按钮。"
        ),
        (
            "请制作可下载的 HTML 互动页「珠峰登山准备清单」：大标题、"
            "八项准备勾选、两个按钮「随机提示」「重置」。"
        ),
        "请生成可下载的 HTML 课件「质数入门」：大标题、三个小节、两个按钮。",
        "请制作可下载的 HTML 页面「值班板」：大标题、三列表格、两个按钮。",
        "请分别交付 3 个独立 HTML 文件：A.html B.html C.html。",
        "请交付 4 个独立可下载文件：甲.md 乙.md 丙.md 丁.md。",
    ]
    for prompt in single_unit_prompts:
        plan = _this_round_delivery_plan(prompt)
        assert plan.min_artifacts == 0, prompt
        assert plan.force_agent is False, prompt
        assert plan.multi_deliverable is False, prompt


@pytest.mark.asyncio
async def test_gate_message_truthful_when_other_format_files_exist(
    tmp_path, monkeypatch
) -> None:
    """A landed file is a landed file. Do not fail-closed from a user-prompt Office list."""
    from app import db as db_mod
    from app.db import ArtifactRow, RunRow, TaskRow, new_id
    from app.delivery_gate import apply_delivery_gate
    from app.settings import get_settings

    db_path = tmp_path / "gate-truth.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    factory = db_mod.session_factory()

    prompt = "请生成一份可下载 Word 文档《团队周报》，内容为三个进展。"
    task_id = new_id()
    run_id = new_id()
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-truth",
                title="word-request",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="succeeded",
                prompt=prompt,
                model="pico-agent",
                token_usage_json=json.dumps(
                    {
                        "skill_snapshot": {
                            "name": "skill.engineering_delivery",
                            "tools": ["workspace_write_file"],
                        }
                    }
                ),
            )
        )
        # A real but wrong-format file exists (Markdown, not Word).
        session.add(
            ArtifactRow(
                id=new_id(),
                task_id=task_id,
                run_id=run_id,
                kind="text",
                title="团队周报.md",
                inline="# 团队周报\n进展",
                content_encoding="utf8",
                content_sha256="c" * 64,
                byte_size=120,
            )
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        await apply_delivery_gate(
            session,
            run,
            final_text="完成，文件：团队周报.md 已可下载。",
            user_prompt=prompt,
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "succeeded"
        assert not run.error
