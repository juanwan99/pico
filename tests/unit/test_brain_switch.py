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


def test_preflight_never_probes_aiproxy(monkeypatch) -> None:
    """pico#1344: a probe is a one-shot call; AIProxy is for long sessions only."""
    probed: list[str] = []
    fake = _fake({("p", "text"): True, ("p", "image"): True, ("g", "text"): True, ("g", "image"): True})

    def probe(base, key, model, content, want):
        probed.append(model)
        return fake(base, key, model, content, want)

    monkeypatch.setattr(bs, "relay_probe", probe)
    assert bs.preflight("b", "k", "p", ["g", "s"], frozenset({"s"})) is True
    assert "s" not in probed
    assert bs.preflight("b", "k", "s", ["g"], frozenset({"s"})) is False


def test_preflight_ocr_model_must_read_images(monkeypatch) -> None:
    """edu-core#3522: --ocr names the handwriting model; it is probed once even
    when it is also a fallback, and must pass the image turn."""
    probed: list[str] = []
    fake = _fake({
        ("p", "text"): True, ("p", "image"): True,
        ("g", "text"): True, ("g", "image"): True,
        ("o", "text"): True, ("o", "image"): False,
    })

    def probe(base, key, model, content, want):
        probed.append(model)
        return fake(base, key, model, content, want)

    monkeypatch.setattr(bs, "relay_probe", probe)
    assert bs.preflight("b", "k", "p", ["g", "p"], ocr="g") is True
    assert probed.count("g") == 2 and probed.count("p") == 2  # text + image, once each
    assert bs.preflight("b", "k", "p", ["g"], ocr="o") is False


def test_switch_rolls_back_when_api_does_not_come_up(monkeypatch, tmp_path) -> None:
    """A new env pico-api cannot boot on must restore the backup, not exit mid-switch."""
    env = tmp_path / ".env"
    env.write_text(
        "DEEPSEEK_BASE_URL=http://127.0.0.1:3000/v1\nPICO_OPENAI_PROXY_KEY=t\nDEEPSEEK_MODEL=old\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bs, "PICO_ENV", env)
    monkeypatch.setattr(bs, "probe_key", lambda e: "k")
    monkeypatch.setattr(bs, "preflight", lambda *a, **k: True)
    monkeypatch.setattr(bs, "trail", lambda card, why: None)
    calls: list[str] = []

    def recreate() -> None:
        calls.append(env.read_text(encoding="utf-8"))
        if len(calls) == 1:
            raise RuntimeError("pico-api not healthy after recreate")

    monkeypatch.setattr(bs, "recreate_api", recreate)
    monkeypatch.setattr(
        bs.sys, "argv",
        ["brain-switch", "--primary", "new", "--ocr", "o", "--card", "c", "--why", "w"],
    )
    assert bs.main() == 1
    assert "DEEPSEEK_MODEL=new" in calls[0] and "PICO_OCR_MODEL=o" in calls[0]
    assert "DEEPSEEK_MODEL=old" in env.read_text(encoding="utf-8")
    assert len(calls) == 2  # recreated again on the restored env
