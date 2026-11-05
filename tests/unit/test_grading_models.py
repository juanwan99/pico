"""pico#1379: exam marking rides its own token and switchable models (edu-core#4576)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator import brain_ha
from pico_orchestrator.grading_models import current_grading_school, grading_model, grading_scope
from pico_orchestrator.provider import (
    OCR_LANE,
    resolve_model_id,
    resolve_provider_for_model,
    runtime_policy_for_model,
    thinking_extra_body,
)


@pytest.fixture
def relay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-chat")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("PICO_OCR_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("PICO_GRADING_API_KEY", "sk-grading")
    path = tmp_path / "grading-models.json"
    monkeypatch.setenv("PICO_GRADING_MODELS_PATH", str(path))
    return path


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")
    # mtime granularity: make each write visibly newer
    st = path.stat()
    os.utime(path, (st.st_atime, st.st_mtime + 1 + len(data.get("schools", {}))))


def _lanes() -> tuple[str, str]:
    cfg = resolve_provider_for_model("pico-fast")
    assert cfg is not None
    return resolve_model_id(OCR_LANE, cfg), resolve_model_id("pico-fast", cfg)


def test_chat_is_untouched_and_marking_keeps_todays_models_without_a_file(relay: Path) -> None:
    assert _lanes() == ("gemini-3.8-flash", "deepseek-flash")
    assert resolve_provider_for_model("pico-fast").api_key == "sk-chat"
    with grading_scope("school-a"):
        assert current_grading_school() == "school-a"
        assert _lanes() == ("gemini-3.8-flash", "deepseek-flash")
        # own New API token even before any model is switched
        assert resolve_provider_for_model("pico-fast").api_key == "sk-grading"
    assert current_grading_school() is None


def test_no_grading_key_falls_back_to_the_chat_key(relay: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PICO_GRADING_API_KEY")
    with grading_scope("school-a"):
        assert resolve_provider_for_model("pico-fast").api_key == "sk-chat"


def test_switch_takes_effect_without_restart_and_per_school(relay: Path) -> None:
    _write(relay, {"default": {"ocr": "gemini-3.8-flash", "score": "deepseek-flash"}})
    with grading_scope("g26"):
        assert _lanes() == ("gemini-3.8-flash", "deepseek-flash")
    _write(relay, {"default": {"score": "deepseek-flash"}, "schools": {"g26": {"score": "gemini-3.8-flash"}}})
    with grading_scope("g26"):
        assert _lanes() == ("gemini-3.8-flash", "gemini-3.8-flash")
        # Gemini on the wire, not DeepSeek's thinking object (empty answers otherwise)
        assert runtime_policy_for_model("pico-fast")["backend_model"] == "gemini-3.8-flash"
        assert "thinking" not in thinking_extra_body("pico-fast", thinking=False)
    with grading_scope("fengxi"):
        assert _lanes() == ("gemini-3.8-flash", "deepseek-flash")
    # chat never reads the marking file
    assert _lanes() == ("gemini-3.8-flash", "deepseek-flash")


def test_broken_file_keeps_last_good_models(relay: Path) -> None:
    _write(relay, {"default": {"score": "gemini-3.8-flash"}})
    assert grading_model("score", "x") == "gemini-3.8-flash"
    relay.write_text("{half", encoding="utf-8")
    os.utime(relay, (relay.stat().st_atime, relay.stat().st_mtime + 50))
    assert grading_model("score", "x") == "gemini-3.8-flash"


def test_marking_channel_gap_does_not_mark_chat_model_down(relay: Path) -> None:
    """The grading group may lack a channel chat has: no global mark_down from marking."""
    import asyncio

    from pico_orchestrator import provider

    brain_ha._down_until.clear()

    async def run() -> None:
        with grading_scope("g26"):
            gen = provider.stream_chat("hi", model="pico-fast", thinking=False)
            with pytest.raises(RuntimeError):
                async for _ in gen:
                    pass

    orig = provider._llm_client

    class _Client:
        class chat:
            class completions:
                @staticmethod
                async def create(**_k):
                    raise RuntimeError("no available channel for model")

    provider._llm_client = lambda _cfg: _Client()
    try:
        asyncio.run(run())
    finally:
        provider._llm_client = orig
    assert not any(brain_ha.is_down(m) for m in ("deepseek-flash", "gemini-3.8-flash"))


def test_second_scorer_lane_reads_score2_and_falls_back_to_score(relay: Path) -> None:
    """edu-core#4576 ⑨c: edu averages a second scorer in on some kinds via lane pico-score2."""
    from pico_orchestrator.provider import SCORE2_LANE

    def second() -> str:
        cfg = resolve_provider_for_model(SCORE2_LANE)
        assert cfg is not None
        return resolve_model_id(SCORE2_LANE, cfg)

    _write(relay, {"default": {"score": "gemini-3.8-flash"}})
    with grading_scope("g26"):
        # no score2 = the scorer itself: nothing changes for edu
        assert second() == "gemini-3.8-flash"
    _write(relay, {"default": {"score": "gemini-3.8-flash", "score2": "deepseek-flash"}, "schools": {"g26": {"score": "gemini-3.8-flash"}}})
    with grading_scope("g26"):
        assert second() == "deepseek-flash"
        assert _lanes() == ("gemini-3.8-flash", "gemini-3.8-flash")
        policy = runtime_policy_for_model(SCORE2_LANE)
        assert policy["backend_model"] == policy["fallback"] == "deepseek-flash"
        assert policy["thinking"] is False
        # DeepSeek on the wire: thinking object off, not Gemini's reasoning_effort
        assert thinking_extra_body(SCORE2_LANE, thinking=False) == {"thinking": {"type": "disabled"}}
        assert resolve_provider_for_model(SCORE2_LANE).api_key == "sk-grading"
    # chat asking for the lane never reads the marking file
    assert second() == "deepseek-flash"  # product brain (DEEPSEEK_MODEL), not score2
