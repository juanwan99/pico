"""#1250 ③: brain switch preflights before touching .env."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("brain_switch", ROOT / "scripts" / "brain-switch.py")
bs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bs)


def test_rewrite_env_replaces_and_appends() -> None:
    text = "# c\nDEEPSEEK_MODEL=old\nOTHER=1\n"
    out = bs.rewrite_env(text, {"DEEPSEEK_MODEL": "new", "PICO_BRAIN_FALLBACKS": "a,b"})
    assert out == "# c\nDEEPSEEK_MODEL=new\nOTHER=1\nPICO_BRAIN_FALLBACKS=a,b\n"


def test_reply_text_reads_chat_and_responses_bodies() -> None:
    assert bs.reply_text({"choices": [{"message": {"content": "391"}}]}) == "391"
    responses = {"output": [{"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": "391"}]}]}
    assert bs.reply_text(responses) == "391"


def _fake(results: dict[tuple[str, str], bool]):
    def probe(base, key, model, content, want):
        kind = "text" if isinstance(content, str) else "image"
        return {"ok": results[(model, kind)], "s": 0, "err": "", "reply": ""}

    return probe


def test_preflight_blocks_primary_without_images(monkeypatch) -> None:
    monkeypatch.setattr(bs, "relay_probe", _fake({("p", "text"): True, ("p", "image"): False, ("f", "text"): True, ("f", "image"): True}))
    assert bs.preflight("b", "k", "p", ["f"]) is False


def test_preflight_blocks_when_no_fallback_reads_images(monkeypatch) -> None:
    monkeypatch.setattr(bs, "relay_probe", _fake({("p", "text"): True, ("p", "image"): True, ("f", "text"): True, ("f", "image"): False}))
    assert bs.preflight("b", "k", "p", ["f"]) is False


def test_preflight_passes_healthy_set(monkeypatch) -> None:
    monkeypatch.setattr(bs, "relay_probe", _fake({("p", "text"): True, ("p", "image"): True, ("f", "text"): True, ("f", "image"): True}))
    assert bs.preflight("b", "k", "p", ["f"]) is True


def test_preflight_keeps_a_down_backup_when_another_catches(monkeypatch) -> None:
    # #1261: sol's key suspended (403) may stay third backup; grok catches.
    monkeypatch.setattr(bs, "relay_probe", _fake({
        ("p", "text"): True, ("p", "image"): True,
        ("g", "text"): True, ("g", "image"): True,
        ("s", "text"): False, ("s", "image"): False,
    }))
    assert bs.preflight("b", "k", "p", ["g", "s"]) is True
    monkeypatch.setattr(bs, "relay_probe", _fake({
        ("p", "text"): True, ("p", "image"): True, ("s", "text"): False, ("s", "image"): False,
    }))
    assert bs.preflight("b", "k", "p", ["s"]) is False
