"""#1167: 「工程已重新打包交付」 with no new file this turn fails, even after earlier files."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.delivery_policy import looks_like_redelivery_claim

# LX2 R13 (run 3e3e70d4): only ls / read / old tests ran, nothing was packed.
R13 = (
    "**第 13 轮已完成**，所有单元测试通过，工程已重新打包交付。 ### 1. 下学期收费方案 …… "
    "### 3. 交付文件 - **`classfund.zip`**：包含完整更新后的工程（顶层保持 `classfund/` 目录结构）。 "
    "### 4. 获取与使用方式 您可在右侧交付面板中直接点击 **下载** `classfund.zip`。"
)


def test_redelivery_claim_wording() -> None:
    assert looks_like_redelivery_claim(R13)
    assert looks_like_redelivery_claim("已经重新生成了课件，请在结果区下载。")
    assert looks_like_redelivery_claim("我把工程重新打包好了。")
    # #850 restating earlier files, or only offering to redo, is not a claim.
    assert not looks_like_redelivery_claim(
        "做完了，两份文件均已生成：春天来了.html 请在结果区下载。"
    )
    assert not looks_like_redelivery_claim("文件是好的；如果还是打不开，我可以重新生成一份。")
    assert not looks_like_redelivery_claim("已重新检查了一遍代码，没有发现问题。")


async def _gate(tmp_path, monkeypatch, *, prior: bool, this_turn: bool, text: str):
    from app import db as db_mod
    from app.db import ArtifactRow, RunRow, TaskRow, new_id
    from app.delivery_gate import apply_delivery_gate
    from app.settings import get_settings

    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'gate.db'}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    factory = db_mod.session_factory()
    cid = "convo-1167"
    run_id = new_id()
    async with factory() as session:
        turns = [("R12", new_id(), new_id(), prior), ("R13", new_id(), run_id, this_turn)]
        for title, task_id, rid, with_file in turns:
            session.add(
                TaskRow(
                    id=task_id,
                    school_id="school-a",
                    membership_id="member-1167",
                    title=title,
                    conversation_id=cid,
                )
            )
            session.add(
                RunRow(id=rid, task_id=task_id, status="succeeded", prompt=title, model="pico-fast")
            )
            if with_file:
                session.add(
                    ArtifactRow(
                        id=new_id(),
                        task_id=task_id,
                        run_id=rid,
                        kind="zip",
                        title="classfund.zip",
                        inline=None,
                        content_encoding="base64",
                        byte_size=5896,
                    )
                )
        await session.commit()
    async with factory() as session:
        run = await session.get(RunRow, run_id)
        await apply_delivery_gate(session, run, final_text=text, user_prompt="R13")
        await session.commit()
    async with factory() as session:
        return await session.get(RunRow, run_id)


@pytest.mark.asyncio
async def test_redelivery_claim_with_no_new_file_fails(tmp_path, monkeypatch) -> None:
    run = await _gate(tmp_path, monkeypatch, prior=True, this_turn=False, text=R13)
    assert run.status == "failed"
    assert run.error and "结果区里还是上一版" in run.error


@pytest.mark.asyncio
async def test_redelivery_claim_with_new_file_passes(tmp_path, monkeypatch) -> None:
    run = await _gate(tmp_path, monkeypatch, prior=True, this_turn=True, text=R13)
    assert run.status == "succeeded" and run.error is None


@pytest.mark.asyncio
async def test_restating_earlier_files_still_passes(tmp_path, monkeypatch) -> None:
    text = "做完了，classfund.zip 已生成，请在结果区下载。"
    run = await _gate(tmp_path, monkeypatch, prior=True, this_turn=False, text=text)
    assert run.status == "succeeded" and run.error is None
