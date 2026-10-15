"""pico#1271 second cut: one New API token per use, request tags, a paced full rebuild."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pico_orchestrator import meili_kb, provider, upstream
from probe_key import probe_key

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_probe_scripts_refuse_the_production_and_kb_tokens(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Not created yet: production key, loudly — brain-switch must still work.
    assert probe_key({"DEEPSEEK_API_KEY": "sk-prod"}) == "sk-prod"
    assert "未设 pico-probe" in capsys.readouterr().err
    with pytest.raises(SystemExit, match="production"):
        probe_key({"DEEPSEEK_API_KEY": "sk-prod", "PICO_PROBE_API_KEY": "sk-prod"})
    with pytest.raises(SystemExit, match="production"):
        probe_key({"PICO_KB_API_KEY": "sk-kb", "PICO_PROBE_API_KEY": "sk-kb"})
    assert probe_key({"DEEPSEEK_API_KEY": "sk-prod", "PICO_PROBE_API_KEY": "sk-probe"}) == "sk-probe"


def test_brain_switch_preflights_on_the_probe_token(monkeypatch: pytest.MonkeyPatch) -> None:
    bs = _load("brain_switch_tokens", "scripts/brain-switch.py")
    env = {
        "DEEPSEEK_BASE_URL": "http://127.0.0.1:3000/v1",
        "DEEPSEEK_API_KEY": "sk-prod",
        "PICO_OPENAI_PROXY_KEY": "pico-token",
    }
    monkeypatch.setattr(bs, "env_file", lambda _p: dict(env))
    used: list[str] = []
    monkeypatch.setattr(bs, "preflight", lambda _b, key, *_a: used.append(key) or False)
    argv = ["brain-switch.py", "--primary", "gemini-3.8-flash", "--card", "pico#1271", "--why", "t"]
    monkeypatch.setattr(sys, "argv", argv)
    assert bs.main() == 1
    assert used == ["sk-prod"]  # no pico-probe yet: production, with a warning

    env["PICO_PROBE_API_KEY"] = "sk-prod"
    with pytest.raises(SystemExit, match="production"):
        bs.main()
    assert used == ["sk-prod"]  # refused before anything is sent

    env["PICO_PROBE_API_KEY"] = "sk-probe"
    assert bs.main() == 1
    assert used == ["sk-prod", "sk-probe"]


def test_kb_uses_its_own_token_and_marks_it_for_meili(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-prod")
    monkeypatch.delenv("PICO_KB_API_KEY", raising=False)
    assert meili_kb.new_api_embedder_spec()["apiKey"] == "sk-prod"  # until the kb token is set

    monkeypatch.setenv("PICO_KB_API_KEY", "sk-kb")
    spec = meili_kb.new_api_embedder_spec()
    assert spec["apiKey"] == "sk-kb"
    assert spec["headers"] == {"X-Pico-Key": meili_kb.key_mark("sk-kb")}
    # Batched input re-embeds every document on Meili v1.13.3: stays one text per call.
    assert spec["request"]["input"] == ["{{text}}"]

    sent: list[dict] = []

    def fake_request(_self, method, url, *, json=None, headers=None, timeout=None):
        sent.append(headers or {})
        return 200, {"results": [{"index": 0, "relevance_score": 0.9, "document": {"text": "a"}}]}

    monkeypatch.setattr(meili_kb.HttpxClient, "request", fake_request)
    meili_kb.rerank_documents_with_usage("q", ["a"])
    assert sent[0]["Authorization"] == "Bearer sk-kb"


def test_meili_sees_a_new_kb_token_without_reembedding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Meili masks apiKey on read; the header mark is what tells a key change apart."""
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-prod")
    monkeypatch.setenv("PICO_KB_API_KEY", "sk-kb")
    want = {"default": meili_kb.new_api_embedder_spec()}
    live = dict(want["default"], apiKey="XXX...")
    idx = meili_kb.MeiliIndex(client=SimpleNamespace())
    body = {"filterableAttributes": meili_kb.FILTERABLE, "embedders": {"default": live}}
    monkeypatch.setattr(idx, "_settings_body", lambda: body)
    assert idx._embedder_url_match(want)

    live["headers"] = {"X-Pico-Key": meili_kb.key_mark("sk-prod")}
    assert not idx._embedder_url_match(want)  # ensure() PATCHes apiKey + header
    live.pop("headers")
    assert not idx._embedder_url_match(want)  # first deploy adds the header


@pytest.mark.asyncio
async def test_full_rebuild_is_paced(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import kb_rebuild

    slept: list[float] = []

    async def fake_sleep(s: float) -> None:
        slept.append(s)

    monkeypatch.setattr(kb_rebuild.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(kb_rebuild.time, "monotonic", lambda: 100.0)
    pace = kb_rebuild._Pace(600)
    for _ in range(7):
        await pace.after(80)  # 560: inside the first minute's worth, no wait
    assert slept == []
    await pace.after(80)  # 640 → 40 over at 10 a second
    assert slept == [pytest.approx(4.0)]

    monkeypatch.setenv("PICO_KB_REBUILD_PER_MIN", "5")
    assert kb_rebuild.rebuild_per_min() == 60  # floor
    monkeypatch.delenv("PICO_KB_REBUILD_PER_MIN")
    assert kb_rebuild.rebuild_per_min() == 600


def test_requests_name_their_road_and_share_a_prompt_cache() -> None:
    assert upstream.caller("exam") == "pico-exam"
    assert upstream.cache_key("") is None
    assert upstream.cache_key("你是 Pico") == upstream.cache_key("你是 Pico")
    assert upstream.cache_key("你是 Pico") != upstream.cache_key("另一段")


@pytest.mark.asyncio
async def test_direct_requests_carry_user_and_prompt_cache_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    provider._CLIENTS.clear()
    seen: list[dict] = []

    class _Events:
        def __init__(self) -> None:
            self.items = [SimpleNamespace(type="response.output_text.delta", delta="好")]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.items:
                return self.items.pop(0)
            raise StopAsyncIteration

    async def create(**kwargs):
        seen.append(kwargs)
        return _Events()

    monkeypatch.setattr(
        "pico_orchestrator.provider.AsyncOpenAI",
        lambda **_kw: SimpleNamespace(responses=SimpleNamespace(create=create)),
    )
    out = [p async for p in provider.stream_chat("hi", system="你是 Pico", model="pico-fast")]
    assert "".join(out) == "好"
    assert seen[0]["user"] == "pico-direct"
    assert seen[0]["prompt_cache_key"] == upstream.cache_key(seen[0]["instructions"])
