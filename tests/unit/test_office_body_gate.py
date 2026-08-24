"""T-COMPACT-OFFICE-HARD: thin OOXML shells fail closed; python-docx bodies pass."""

from __future__ import annotations

import base64
import io
import json
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))


def _thin_docx_zip(title: str, marker: str, body: str) -> bytes:
    heading = escape(title)
    paragraph = escape(body)
    marker_xml = escape(marker)
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{heading}</w:t></w:r></w:p>
    <w:p><w:r><w:t>标记：{marker_xml}</w:t></w:r></w:p>
    <w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
        )
        zf.writestr("word/document.xml", document)
    return buf.getvalue()


async def _boot_db(tmp_path, monkeypatch, name: str):
    from app import db as db_mod
    from app.settings import get_settings

    db_path = tmp_path / name
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._Session = None
    await db_mod.init_db()
    return db_mod.session_factory()


@pytest.mark.asyncio
async def test_delivery_gate_rejects_thin_docx_shell(tmp_path, monkeypatch) -> None:
    from app.db import ArtifactRow, EventRow, RunRow, TaskRow, new_id
    from app.delivery_gate import apply_delivery_gate

    factory = await _boot_db(tmp_path, monkeypatch, "thin-docx.db")
    thin = _thin_docx_zip("家长会通知", "M", "一行")
    task_id = new_id()
    run_id = new_id()
    prompt = "请把下面这段家长通知改成 Word 文档并下载。"
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-thin-docx",
                title="office",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="succeeded",
                prompt=prompt,
                model="pico-deep",
                token_usage_json=json.dumps(
                    {"skill_snapshot": {"name": "skill.deliverable", "tools": ["generate_docx_document"]}}
                ),
            )
        )
        session.add(
            ArtifactRow(
                id=new_id(),
                task_id=task_id,
                run_id=run_id,
                kind="docx",
                title="家长会通知.docx",
                inline=base64.b64encode(thin).decode("ascii"),
                content_encoding="base64",
                byte_size=len(thin),
            )
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        await apply_delivery_gate(
            session,
            run,
            final_text="已交付家长会通知.docx",
            user_prompt=prompt,
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.error and "空壳" in run.error
        failed = [
            e
            for e in (
                await session.execute(
                    select(EventRow).where(
                        EventRow.run_id == run_id,
                        EventRow.type == "run.status",
                    )
                )
            ).scalars()
            if e.payload and e.payload.get("status") == "failed"
        ]
        assert failed
        assert failed[-1].payload.get("reason") == "office_body_too_thin"


@pytest.mark.asyncio
async def test_delivery_gate_accepts_python_docx_body(tmp_path, monkeypatch) -> None:
    from app.db import ArtifactRow, RunRow, TaskRow, new_id
    from app.delivery_gate import apply_delivery_gate
    from pico_orchestrator.document_generators import build_docx_document

    factory = await _boot_db(tmp_path, monkeypatch, "real-docx.db")
    raw = build_docx_document(
        title="家长会通知.docx",
        marker="MEET1",
        body=(
            "各位家长：本周五（3月14日）下午两点在教学楼三层三年级二班教室召开本学期家长会，"
            "请准时到场，并带好孩子的期末成绩单、家校联系册和课外阅读记录。签到从一点五十分开始。\n\n"
            "会议内容按顺序进行：先通报本班期中以来的学习与纪律情况，再讲作业习惯与家庭辅导建议，"
            "然后说明下学期课程、值日、校服与收费事项，最后留二十分钟个别交流。"
            "请提前十分钟入场，手机调至静音，中途如需接听请到走廊。\n\n"
            "如有事不能参加，请当天中午十二点前在班级群私信班主任请假并注明由哪位家长代到。"
            "三年级二班班主任。教室路线、签到表与座位图见班级群置顶。"
            "会后请在本周日晚八点前把家庭作业时间安排发给老师，便于下周跟进错题订正。"
            "雨天请走东门电梯，自行车请停在教学楼北侧车棚。"
        ),
    )
    task_id = new_id()
    run_id = new_id()
    prompt = "请把下面这段家长通知改成 Word 文档并下载。"
    async with factory() as session:
        session.add(
            TaskRow(
                id=task_id,
                school_id="school-a",
                membership_id="member-real-docx",
                title="office",
            )
        )
        session.add(
            RunRow(
                id=run_id,
                task_id=task_id,
                status="succeeded",
                prompt=prompt,
                model="pico-deep",
                token_usage_json=json.dumps(
                    {"skill_snapshot": {"name": "skill.deliverable", "tools": ["generate_docx_document"]}}
                ),
            )
        )
        session.add(
            ArtifactRow(
                id=new_id(),
                task_id=task_id,
                run_id=run_id,
                kind="docx",
                title="家长会通知.docx",
                inline=base64.b64encode(raw).decode("ascii"),
                content_encoding="base64",
                byte_size=len(raw),
            )
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        await apply_delivery_gate(
            session,
            run,
            final_text="已交付家长会通知.docx",
            user_prompt=prompt,
        )
        await session.commit()

    async with factory() as session:
        run = await session.get(RunRow, run_id)
        assert run is not None
        assert run.status == "succeeded"
