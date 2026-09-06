"""Publish confirm is a real gate, not a prompt."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.gateway import ToolError
from pico_orchestrator.publish_confirm import (
    confirm_options,
    consume_confirm_token,
    is_confirm_answer,
    issue_confirm_token,
    require_teacher_confirm,
    reset_confirm_tokens,
)


@dataclass
class P:
    school_id: str
    membership_id: str
    scopes: list[str]


@pytest.fixture(autouse=True)
def _clean_tokens() -> None:
    reset_confirm_tokens()
    yield
    reset_confirm_tokens()


def test_missing_token_does_not_confirm() -> None:
    owner = P("school-a", "member-a", ["ai:run"])
    with pytest.raises(ToolError) as denied:
        consume_confirm_token(owner, artifact_id="art-1", token="")
    assert denied.value.code == "publish.unconfirmed"


def test_token_binds_identity_and_page() -> None:
    owner = P("school-a", "member-a", ["ai:run"])
    other = P("school-a", "member-b", ["ai:run"])
    token = issue_confirm_token(owner, artifact_id="art-1")
    with pytest.raises(ToolError) as mismatch:
        consume_confirm_token(owner, artifact_id="art-2", token=token)
    assert mismatch.value.code == "publish.confirm_mismatch"
    with pytest.raises(ToolError) as tenant:
        consume_confirm_token(other, artifact_id="art-1", token=token)
    assert tenant.value.code == "publish.confirm_mismatch"
    consume_confirm_token(owner, artifact_id="art-1", token=token)
    with pytest.raises(ToolError) as replay:
        consume_confirm_token(owner, artifact_id="art-1", token=token)
    assert replay.value.code == "publish.confirm_replay"


def test_confirm_answer_requires_this_page_option() -> None:
    page_a = "cafebabe-1111-2222-3333-444444444444"
    page_b = "deadbeef-1111-2222-3333-444444444444"
    yes_a, no = confirm_options(page_a)
    yes_b, _ = confirm_options(page_b)
    assert is_confirm_answer(yes_a, page_a) is True
    assert is_confirm_answer(yes_b, page_a) is False
    assert is_confirm_answer("确认发布", page_a) is False
    assert is_confirm_answer("确认发布取消", page_a) is False
    assert is_confirm_answer(f"确认发布 {page_a}", page_a) is False
    assert is_confirm_answer(no, page_a) is False


@pytest.mark.asyncio
async def test_wrong_page_option_does_not_authorize(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = P("school-a", "member-a", ["ai:run"])
    page_a = "cafebabe-1111-2222-3333-444444444444"
    yes_other, _ = confirm_options("deadbeef-1111-2222-3333-444444444444")
    monkeypatch.setattr(
        "pico_orchestrator.ask_user.park",
        AsyncMock(return_value={"ok": True, "answer": yes_other, "question": "确认吗"}),
    )
    with pytest.raises(ToolError) as cancelled:
        await require_teacher_confirm(
            owner,
            artifact_id=page_a,
            title="demo.html",
            confirm_token="",
            run_id="run-1",
            emit=None,
        )
    assert cancelled.value.code == "publish.cancelled"


@pytest.mark.asyncio
async def test_run_park_cancel_does_not_issue_token(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = P("school-a", "member-a", ["ai:run"])
    parked = {"ok": True, "answer": "取消", "question": "确认吗"}
    monkeypatch.setattr(
        "pico_orchestrator.ask_user.park", AsyncMock(return_value=parked)
    )
    with pytest.raises(ToolError) as cancelled:
        await require_teacher_confirm(
            owner,
            artifact_id="art-1",
            title="demo.html",
            confirm_token="",
            run_id="run-1",
            emit=None,
        )
    assert cancelled.value.code == "publish.cancelled"


@pytest.mark.asyncio
async def test_second_confirm_after_cancel_needs_new_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = P("school-a", "member-a", ["ai:run"])
    answers = iter(["取消", confirm_options("art-2")[0]])

    async def park(_run_id, _question, _options, _emit):
        return {"ok": True, "answer": next(answers), "question": "确认吗"}

    monkeypatch.setattr("pico_orchestrator.ask_user.park", park)
    with pytest.raises(ToolError) as cancelled:
        await require_teacher_confirm(
            owner,
            artifact_id="art-1",
            title="demo.html",
            confirm_token="",
            run_id="run-1",
            emit=None,
        )
    assert cancelled.value.code == "publish.cancelled"
    token = await require_teacher_confirm(
        owner,
        artifact_id="art-2",
        title="demo.html",
        confirm_token="",
        run_id="run-2",
        emit=None,
    )
    assert token
    with pytest.raises(ToolError) as replay:
        consume_confirm_token(owner, artifact_id="art-2", token=token)
    assert replay.value.code == "publish.confirm_replay"


@pytest.mark.asyncio
async def test_run_park_yes_consumes_one_shot(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = P("school-a", "member-a", ["ai:run"])
    parked = {"ok": True, "answer": confirm_options("art-1")[0], "question": "确认吗"}
    monkeypatch.setattr(
        "pico_orchestrator.ask_user.park", AsyncMock(return_value=parked)
    )
    token = await require_teacher_confirm(
        owner,
        artifact_id="art-1",
        title="demo.html",
        confirm_token="",
        run_id="run-1",
        emit=None,
    )
    assert token
    with pytest.raises(ToolError):
        consume_confirm_token(owner, artifact_id="art-1", token=token)
