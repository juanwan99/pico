"""pico#1379: marking model switch preflights on the marking token, layers school > default > env."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("grading_model", ROOT / "scripts" / "grading-model.py")
gm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gm)

ENV = {"PICO_OCR_MODEL": "gemini-3.8-flash", "DEEPSEEK_MODEL": "deepseek-flash"}


def test_effective_layers_school_over_default_over_env() -> None:
    assert gm.effective({}, "g26", ENV) == {"ocr": "gemini-3.8-flash", "score": "deepseek-flash", "score2": "deepseek-flash"}
    data = {"default": {"score": "grok-x"}, "schools": {"g26": {"score": "gemini-3.8-flash"}}}
    assert gm.effective(data, "g26", ENV)["score"] == "gemini-3.8-flash"
    assert gm.effective(data, "fengxi", ENV)["score"] == "grok-x"
    assert gm.effective(data, None, ENV)["ocr"] == "gemini-3.8-flash"
    # edu-core#4576 ⑨c: score2 unset follows the effective scorer; set at default it applies to every school.
    assert gm.effective(data, "g26", ENV)["score2"] == "gemini-3.8-flash"
    data["default"]["score2"] = "deepseek-flash"
    assert gm.effective(data, "g26", ENV)["score2"] == "deepseek-flash"


def _fake(results: dict[tuple[str, str], bool]):
    def probe(base, key, model, content, want):
        kind = "text" if isinstance(content, str) else "image"
        return {"ok": results[(model, kind)], "s": 0, "err": "", "reply": ""}

    return probe


def test_score_model_must_answer_text_and_read_images(monkeypatch) -> None:
    monkeypatch.setattr(gm.bs, "relay_probe", _fake({("m", "text"): True, ("m", "image"): False}))
    assert gm.preflight("b", "k", {"score": "m"}, frozenset()) is False
    monkeypatch.setattr(gm.bs, "relay_probe", _fake({("m", "text"): True, ("m", "image"): True}))
    assert gm.preflight("b", "k", {"score": "m"}, frozenset()) is True


def test_ocr_model_needs_images_only_and_long_session_models_are_refused(monkeypatch) -> None:
    monkeypatch.setattr(gm.bs, "relay_probe", _fake({("o", "image"): True}))
    assert gm.preflight("b", "k", {"ocr": "o"}, frozenset()) is True
    assert gm.preflight("b", "k", {"ocr": "gpt-5.6-sol"}, frozenset({"gpt-5.6-sol"})) is False
