"""#1195: direct path keeps images; non-stream failures carry a machine code."""

from __future__ import annotations

import json

from app.openai_compat import (
    _EMPTY_OUTPUT,
    _EXHAUSTED_OUTPUT,
    _empty_output_error,
    _failure_code,
    _failure_response,
)
from pico_orchestrator.provider import _messages_for_chat, _responses_input_from_messages


def _img(data: str) -> dict:
    return {"type": "image", "data": data, "mimeType": "image/png"}


def test_direct_messages_carry_images_in_order() -> None:
    msgs = _messages_for_chat("转写", history=None, system="sys", images=[_img("A"), _img("B")])
    content = msgs[-1]["content"]
    assert content[0] == {"type": "text", "text": "转写"}
    assert [part["image_url"]["url"] for part in content[1:]] == [
        "data:image/png;base64,A",
        "data:image/png;base64,B",
    ]


def test_direct_messages_without_images_stay_text() -> None:
    assert _messages_for_chat("hi", history=None, system=None)[-1]["content"] == "hi"


def test_responses_input_maps_image_parts() -> None:
    msgs = _messages_for_chat("看图", history=None, system="sys", images=[_img("A")])
    instructions, items = _responses_input_from_messages(msgs)
    assert instructions == "sys"
    assert items[-1]["content"] == [
        {"type": "input_text", "text": "看图"},
        {"type": "input_image", "image_url": "data:image/png;base64,A"},
    ]


def _body(resp) -> tuple[int, dict]:
    return resp.status_code, json.loads(resp.body)["error"]


def test_failure_codes() -> None:
    status, err = _body(
        _failure_response("模型调用失败：Error code: 502 URLError", status="failed", run_id="r")
    )
    assert (status, err["code"], err["retryable"]) == (502, "upstream_error", True)
    status, err = _body(_failure_response("Read timed out", status="failed", run_id="r"))
    assert (status, err["code"]) == (504, "upstream_timeout")
    status, err = _body(_failure_response("Error code: 503 overloaded", status="failed", run_id="r"))
    assert (status, err["code"]) == (503, "upstream_overloaded")
    status, err = _body(_failure_response(None, status="failed", run_id="r", empty=True))
    assert (status, err["code"]) == (502, "empty_output")
    status, err = _body(_failure_response(None, status="cancelled", run_id="r"))
    assert (status, err["code"], err["retryable"]) == (409, "run_cancelled", False)


def test_thinking_used_whole_budget_is_not_retryable() -> None:
    """edu-core#5941: finish=length with no text — resending the same prompt burns the budget again."""
    status, err = _body(_failure_response(_EXHAUSTED_OUTPUT, status="failed", run_id="r", empty=True))
    assert (status, err["code"], err["retryable"]) == (502, "output_exhausted", False)
    assert "原样再问也一样" in err["message"]
    # usage row shares the code
    assert _failure_code(_EXHAUSTED_OUTPUT, status="failed", empty=True)[1] == "output_exhausted"


def test_only_a_full_budget_counts_as_exhausted() -> None:
    """edu-core#5941 review: length with a short think (provider rewrites #1116) stays retryable."""
    assert _empty_output_error("length", {"completion_tokens": 16384}, 16384) == _EXHAUSTED_OUTPUT
    assert _empty_output_error("length", {"completion_tokens": 300}, 16384) == _EMPTY_OUTPUT
    assert _empty_output_error("stop", {"completion_tokens": 16384}, 16384) == _EMPTY_OUTPUT
    assert _empty_output_error("length", None, 16384) == _EMPTY_OUTPUT
