from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.openai_compat import (
    ChatCompletionRequest,
    ChatMessage,
    _conversation_id_from,
    _extract_file_artifacts,
    _file_from_user_prompt,
    _model_preference_from_prompt,
)


def test_extract_file_fence_with_file_prefix() -> None:
    text = "如下：\n```file:hello.txt\nhi\n```\n完成"
    files = _extract_file_artifacts(text)
    assert files == [("hello.txt", "hi")]


def test_extract_file_fence_bare_name() -> None:
    text = "```hello.txt\nhello world\n```"
    files = _extract_file_artifacts(text)
    assert files[0][0] == "hello.txt"
    assert "hello world" in files[0][1]


def test_file_from_user_prompt_cn() -> None:
    files = _file_from_user_prompt("创建 hello.txt，内容为 hi")
    assert files == [("hello.txt", "hi")]


def test_file_from_user_prompt_no_match() -> None:
    assert _file_from_user_prompt("只回：演示OK") == []


def test_model_preference_routes_file_skill_to_pico_agent() -> None:
    assert _model_preference_from_prompt("【模型偏好：pico-agent】\n创建 hello.txt") == "pico-agent"


def test_model_preference_normalizes_kimi_alias_and_rejects_unknown() -> None:
    assert _model_preference_from_prompt("【模型偏好：Kimi-K3】") == "kimi-k3"
    assert _model_preference_from_prompt("【模型偏好：untrusted-model】") is None


def test_conversation_marker_wins_over_generic_body_user() -> None:
    body = ChatCompletionRequest(
        model="kimi-k2.6",
        user="librechat-user-id",
        messages=[ChatMessage(role="user", content="【Pico-Convo:pending_123】\n你好")],
    )
    assert _conversation_id_from(body, None) == "pending_123"
