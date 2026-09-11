"""exam-answer-extract: prompt source, JSON repair, page merge, HTTP adapter (edu-core#1496)."""

from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "packages" / "exam-answer-extract"))

import extract as ex
from app.auth import issue_test_token
from app.main import app
from app.settings import get_settings

GOLD_SINGLE = ["C", "D", "C", "B", "D", "A", "C", "D", "C", "D", "C", "A"]
GOLD_MULTI = ["ACD", "AC", "ABC", "BC"]


@pytest.fixture(autouse=True)
def _no_retry_backoff(monkeypatch):
    monkeypatch.setattr(ex, "_RETRY_BACKOFF_SECONDS", (0.0, 0.0, 0.0))


def _gold_items(page: int | None = None, *, rubric: bool = False) -> list[dict]:
    items = []
    for i, letter in enumerate(GOLD_SINGLE, start=1):
        items.append({"number": i, "type": "single_choice", "answer": letter, "score": 2})
    for i, letters in enumerate(GOLD_MULTI, start=13):
        items.append({"number": i, "type": "multi_choice", "answer": letters, "score": 4})
    for i in range(17, 22):
        items.append(
            {
                "number": i,
                "type": "short_answer",
                "answer": f"(1) 要点甲{i} (2) 要点乙{i}",
                "rubric": f"评分标准 {i}：每点 3 分" if rubric else "",
                "score": None,
                "sub_count": 2,
            }
        )
    return items


# ---------------------------------------------------------------- prompts / json


def test_prompts_come_from_skill_md():
    prompts = ex.load_prompts()
    assert "只返回 JSON 数组" in prompts["system"]
    assert "禁止默认填 1" in prompts["system"]
    assert "rubric" in prompts["system"]
    assert "{{text}}" in prompts["user_text"]
    assert "{{subject}}" in prompts["user_page"]
    assert "```" not in prompts["system"]


def test_prompt_missing_block_is_explicit():
    with pytest.raises(ex.ExtractError) as caught:
        ex.load_prompts("# nothing here")
    assert caught.value.code == "skill.invalid"


def test_parse_json_array_variants():
    fenced = '```json\n[{"number": 1, "answer": "C"}]\n```'
    assert ex.parse_json_array(fenced) == [{"number": 1, "answer": "C"}]
    wrapped = json.dumps({"questions": [{"number": 2, "answer": "D"}]})
    assert ex.parse_json_array(wrapped)[0]["number"] == 2
    ndjson = '{"number": 1, "answer": "C"}\n{"number": 2, "answer": "D"}'
    assert [q["number"] for q in ex.parse_json_array(ndjson)] == [1, 2]
    truncated = '[{"number": 1, "answer": "C"}, {"number": 2, "ans'
    repaired = ex.parse_json_array(truncated)
    assert repaired == [{"number": 1, "answer": "C"}]
    assert ex.parse_json_array("模型不可用") is None
    assert ex.parse_json_array("") is None


def test_normalize_keeps_null_score_and_splits_letters():
    item = ex.normalize_item({"number": "13", "type": "选择题", "answer": "A C D"}, page=2)
    assert item["type"] == "multi_choice"
    assert item["answer"] == "ACD"
    assert item["score"] is None
    assert item["options_count"] == 4
    assert item["source"] == {"page": 2, "quote": ""}
    essay = ex.normalize_item(
        {
            "number": 18,
            "type": "short_answer",
            "answer": "(1) 甲 (2) 乙",
            "score": "12",
            "quote": "x",
        },
        page=None,
    )
    assert essay["score"] == 12
    assert essay["sub_count"] == 2
    assert essay["options_count"] is None
    assert ex.normalize_item({"number": 0, "answer": "A"}, page=1) is None
    assert ex.normalize_item({"answer": "A"}, page=1) is None


def test_vision_miss_items_are_dropped_not_kept():
    text = json.dumps(
        [{"number": 1, "answer": "未收到第4/4页的图片"}, {"number": 2, "answer": "B"}]
    )
    items = ex.items_from_model_text(text, page=4)
    assert [q["number"] for q in items] == [2]


def test_flatten_section_envelope():
    text = json.dumps(
        [
            {
                "type": "单项选择题",
                "questionNumbers": [1, 2],
                "answers": ["C", "D"],
                "scorePerQuestion": 2,
            }
        ]
    )
    items = ex.items_from_model_text(text, page=1)
    assert [(q["number"], q["answer"], q["score"]) for q in items] == [(1, "C", 2), (2, "D", 2)]


def test_merge_keeps_first_answer_and_longest_rubric():
    p1 = ex.items_from_model_text(json.dumps(_gold_items()[:16]), page=1)
    p2 = ex.items_from_model_text(json.dumps(_gold_items(rubric=True)[12:]), page=2)
    merged = ex.merge_items([p1, p2])
    assert [q["number"] for q in merged] == list(range(1, 22))
    assert [q["answer"] for q in merged[:12]] == GOLD_SINGLE
    assert [q["answer"] for q in merged[12:16]] == GOLD_MULTI
    assert merged[12]["source"]["page"] == 1
    assert merged[16]["rubric"].startswith("评分标准 17")
    assert merged[16]["source"]["page"] == 2


def test_chunk_text_splits_on_lines():
    text = "\n".join(f"{i}. 答案{i}" for i in range(1, 400))
    chunks = ex.chunk_text(text, limit=500)
    assert len(chunks) > 1
    assert "\n".join(chunks) == text


# ---------------------------------------------------------------- pipeline (stub model)


def _stub(responses: dict[int | None, str] | str, calls: list | None = None):
    async def complete(messages, *, thinking=None, usage_out=None, model_out=None, **_):
        if calls is not None:
            calls.append(messages)
        if model_out is not None:
            model_out["model"] = "stub-model"
        if usage_out is not None:
            usage_out.update({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        if isinstance(responses, str):
            return responses
        content = messages[-1]["content"]
        page = None
        if isinstance(content, list):
            # page number is not in the message; tests encode it in the image payload
            img = next(p for p in content if p["type"] == "image")
            page = int(base64.b64decode(img["data_b64"]).decode())
        out = responses.get(page)
        if isinstance(out, BaseException):
            raise out
        return out or "[]"

    return complete


def _page(n: int) -> dict:
    return {"page": n, "mime": "image/jpeg", "data_b64": base64.b64encode(str(n).encode()).decode()}


def _page_in(n: int, mime: str = "image/jpeg") -> dict:
    return {"page": n, "mime": mime, "content_b64": base64.b64encode(str(n).encode()).decode()}


@pytest.mark.asyncio
async def test_extract_text_one_shot_gold():
    calls: list = []
    result = await ex.extract_text(
        "1. C\n2. D", subject_name="生物", complete=_stub(json.dumps(_gold_items()), calls)
    )
    assert result["mode"] == "text"
    assert result["model"] == "stub-model"
    assert len(calls) == 1
    system, user = calls[0]
    assert system["role"] == "system" and "只返回 JSON 数组" in system["content"]
    assert "（科目 生物）" in user["content"] and "1. C\n2. D" in user["content"]
    assert [q["answer"] for q in result["questions"][:12]] == GOLD_SINGLE
    assert result["questions"][16]["score"] is None
    assert any("null" in w for w in result["warnings"])
    assert result["usage"]["total_tokens"] == 15


@pytest.mark.asyncio
async def test_extract_pages_merges_and_tolerates_one_failed_page():
    responses = {
        1: json.dumps(_gold_items()[:12]),
        2: json.dumps(_gold_items()[12:16]),
        3: RuntimeError("upstream 502"),
        4: json.dumps(_gold_items(rubric=True)[16:]),
    }
    calls: list = []
    result = await ex.extract_pages(
        [_page(1), _page(2), _page(3), _page(4)], complete=_stub(responses, calls), concurrency=2
    )
    assert result["mode"] == "pages"
    assert [q["number"] for q in result["questions"]] == list(range(1, 22))
    assert result["questions"][0]["source"]["page"] == 1
    assert result["questions"][20]["rubric"]
    reports = {r["page"]: r for r in result["pages"]}
    assert reports[3]["ok"] is False and "502" in reports[3]["error"]
    assert reports[1]["count"] == 12
    assert any("没读成" in w for w in result["warnings"])
    for messages in calls:
        content = messages[-1]["content"]
        assert sum(1 for p in content if p["type"] == "image") == 1, "one page = one image"


@pytest.mark.asyncio
async def test_extract_pages_all_failed_is_model_failed():
    calls: list = []
    with pytest.raises(ex.ExtractError) as caught:
        await ex.extract_pages([_page(1)], complete=_stub({1: RuntimeError("boom")}, calls))
    assert caught.value.code == "model.failed"
    assert len(calls) == 3, "transient failures get PICO_EXAM_EXTRACT_ATTEMPTS (default 3) tries"


@pytest.mark.asyncio
async def test_page_retry_recovers_from_transient_relay_reset():
    """Live relay: 'upstream error: do request failed' on the first try, fine on the next."""
    attempts: list[int] = []
    slept: list[float] = []

    async def flaky(messages, *, thinking=None, usage_out=None, model_out=None, **_):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("Error code: 500 - upstream error: do request failed")
        return json.dumps(_gold_items()[:12])

    async def fake_sleep(seconds):
        slept.append(seconds)

    out = await ex._complete_with_retry(
        flaky,
        [{"role": "user", "content": "x"}],
        thinking=None,
        usage={},
        model_out={},
        sleep=fake_sleep,
    )
    assert json.loads(out)[0]["number"] == 1
    assert len(attempts) == 2 and slept == [0.0]


@pytest.mark.asyncio
async def test_retry_never_repeats_configuration_errors():
    calls: list = []

    async def unconfigured(messages, **_):
        calls.append(1)
        raise ex.ExtractError("model.unconfigured", "no brain")

    with pytest.raises(ex.ExtractError) as caught:
        await ex._complete_with_retry(
            unconfigured, [{"role": "user", "content": "x"}], thinking=False, usage={}, model_out={}
        )
    assert caught.value.code == "model.unconfigured" and len(calls) == 1


@pytest.mark.asyncio
async def test_pages_default_to_serial_calls(monkeypatch):
    monkeypatch.delenv("PICO_EXAM_EXTRACT_CONCURRENCY", raising=False)
    active = 0
    peak = 0

    async def slow(messages, *, thinking=None, usage_out=None, model_out=None, **_):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        img = next(p for p in messages[-1]["content"] if p["type"] == "image")
        page = int(base64.b64decode(img["data_b64"]).decode())
        return json.dumps([_gold_items()[page - 1]])

    result = await ex.extract_pages([_page(1), _page(2), _page(3)], complete=slow)
    assert peak == 1
    assert [q["number"] for q in result["questions"]] == [1, 2, 3]


@pytest.mark.asyncio
async def test_extract_empty_array_is_failure_not_guess():
    with pytest.raises(ex.ExtractError) as caught:
        await ex.extract_text("1. C", complete=_stub("[]"))
    assert caught.value.code == "extract.empty"
    with pytest.raises(ex.ExtractError) as caught2:
        await ex.extract_text("1. C", complete=_stub("【错误】模型不可用：gpt-x"))
    assert caught2.value.code == "extract.empty"
    assert "模型不可用" in str(caught2.value)


def test_message_conversion_for_both_backends():
    messages = [
        {"role": "system", "content": "sys"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "看图"},
                {"type": "image", "mime": "image/jpeg", "data_b64": "AAAA"},
            ],
        },
    ]
    chat = ex._to_chat_messages(messages)
    assert chat[1]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,AAAA"},
    }
    responses = ex._to_responses_messages(messages)
    assert responses[1]["content"][0] == {"type": "input_text", "text": "看图"}
    assert responses[1]["content"][1]["type"] == "input_image"
    assert responses[1]["content"][1]["image_url"] == "data:image/jpeg;base64,AAAA"
    assert ex._has_images(messages) is True
    assert ex._has_images([{"role": "user", "content": "x"}]) is False


# ---------------------------------------------------------------- HTTP adapter


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "exam-extract.db"
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("PICO_ENV", "development")
    from app import db as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    with TestClient(app) as test_client:
        yield test_client


def _headers(scopes=None) -> dict[str, str]:
    token = issue_test_token(
        school_id="school-a",
        membership_id="m-edu",
        scopes=scopes if scopes is not None else ["ai:run"],
        settings=get_settings(),
    )
    return {"authorization": f"Bearer {token}"}


def _usage_rows(tmp_path):
    with sqlite3.connect(tmp_path / "exam-extract.db") as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM usage_events")]


def test_route_requires_bearer_and_run_scope(client: TestClient):
    assert client.post("/v1/exam/answer-extract", json={"text": "1. C"}).status_code == 401
    res = client.post(
        "/v1/exam/answer-extract", json={"text": "1. C"}, headers=_headers(["ai:read"])
    )
    assert res.status_code == 403


def test_route_text_xor_pages(client: TestClient):
    res = client.post("/v1/exam/answer-extract", json={}, headers=_headers())
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "extract.invalid"
    res = client.post(
        "/v1/exam/answer-extract",
        json={"text": "1. C", "pages": [{"page": 1, "content_b64": "AAAA"}]},
        headers=_headers(),
    )
    assert res.status_code == 400


def test_route_text_ok_records_usage_with_tokens(client: TestClient, monkeypatch, tmp_path):
    monkeypatch.setattr(ex, "model_complete", _stub(json.dumps(_gold_items())))
    res = client.post(
        "/v1/exam/answer-extract",
        json={
            "text": "1. C\n2. D",
            "subject_code": "SW",
            "subject_name": "生物",
            "item_id": "sk-1",
        },
        headers=_headers(),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True and body["engine"] == ex.ENGINE and body["mode"] == "text"
    assert len(body["questions"]) == 21
    assert body["questions"][12]["answer"] == "ACD"
    assert "usage" not in body
    rows = _usage_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["source"] == "exam_answer_extract"
    assert rows[0]["total_tokens"] == 15
    assert rows[0]["tokens_unknown"] == 0
    assert rows[0]["idempotency_key"].startswith("exam_answer_extract:school-a:sk-1:")


def test_route_pages_ok(client: TestClient, monkeypatch):
    responses = {1: json.dumps(_gold_items()[:16]), 2: json.dumps(_gold_items()[16:])}
    monkeypatch.setattr(ex, "model_complete", _stub(responses))
    res = client.post(
        "/v1/exam/answer-extract",
        json={"pages": [_page_in(2), _page_in(1)]},
        headers=_headers(),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "pages"
    assert [p["page"] for p in body["pages"]] == [1, 2]
    assert len(body["questions"]) == 21


def test_route_page_validation(client: TestClient):
    res = client.post(
        "/v1/exam/answer-extract",
        json={"pages": [_page_in(1, "image/gif")]},
        headers=_headers(),
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "page.invalid"
    res = client.post(
        "/v1/exam/answer-extract",
        json={"pages": [_page_in(1), _page_in(1)]},
        headers=_headers(),
    )
    assert res.status_code == 400


def test_route_empty_and_failed_codes(client: TestClient, monkeypatch, tmp_path):
    monkeypatch.setattr(ex, "model_complete", _stub("[]"))
    res = client.post("/v1/exam/answer-extract", json={"text": "1. C"}, headers=_headers())
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "extract.empty"

    monkeypatch.setattr(ex, "model_complete", _stub({1: RuntimeError("boom")}))
    res = client.post("/v1/exam/answer-extract", json={"pages": [_page_in(1)]}, headers=_headers())
    assert res.status_code == 502
    assert res.json()["detail"]["code"] == "model.failed"

    async def unconfigured(*_, **__):
        raise ex.ExtractError("model.unconfigured", "no brain")

    monkeypatch.setattr(ex, "model_complete", unconfigured)
    res = client.post("/v1/exam/answer-extract", json={"text": "1. C"}, headers=_headers())
    assert res.status_code == 503
    rows = _usage_rows(tmp_path)
    # same text twice → one idempotent row; the page request is the second row
    assert len(rows) == 2 and all(r["tokens_unknown"] == 1 for r in rows)
