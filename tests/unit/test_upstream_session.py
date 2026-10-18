"""pico#1344: one conversation = one upstream session; one teacher, one key, few at once.

AIProxy banned the key on 10-18: every request looked like a new conversation
and up to 6 ran at once (89 % from two ruler stacks side by side).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pico_orchestrator import provider, upstream
from pico_orchestrator.true_pi.runner import ProxyEntry, register_proxy, unregister_proxy

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "r" * 32
H = {"x-pico-runner-token": TOKEN}


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses look their module up
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _fresh() -> None:
    upstream.reset()


def test_session_is_fixed_per_conversation_and_hides_the_id() -> None:
    with upstream.caller_scope(conversation_id="conv-1", run_id="r1", membership_id="m1") as a:
        pass
    with upstream.caller_scope(conversation_id="conv-1", run_id="r2", membership_id="m1") as b:
        pass
    assert a.session == b.session and a.session.startswith("pcs-") and "conv-1" not in a.session
    assert len(a.session) <= 64
    with upstream.caller_scope(conversation_id=None, run_id="r3") as c:
        # No conversation: the run is its own conversation.
        assert upstream.CALLER.get() == c
    assert c.session == upstream.conversation_session("run:r3") and c.member == ""
    assert upstream.CALLER.get() == upstream.Caller()


def test_default_caps_are_the_measured_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(upstream.KEY_MAX_ENV, raising=False)
    monkeypatch.delenv(upstream.MEMBER_MAX_ENV, raising=False)
    assert (upstream.key_max(), upstream.member_max()) == (4, 2)
    monkeypatch.setenv(upstream.KEY_MAX_ENV, "1")
    assert upstream.key_max() == 1


@pytest.mark.asyncio
async def test_a_teacher_waits_for_their_own_slot_not_a_key_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(upstream.KEY_MAX_ENV, "4")
    monkeypatch.setenv(upstream.MEMBER_MAX_ENV, "2")
    with upstream.caller_scope(conversation_id="c", run_id="r", membership_id="busy"):
        held = [await upstream.acquire("k", "pi_step") for _ in range(2)]
        third = asyncio.ensure_future(upstream.acquire("k", "pi_step"))
        await asyncio.sleep(0.05)
        assert not third.done()  # waits in line, no error
    # Another teacher still gets through: the waiting one holds no key slot.
    with upstream.caller_scope(conversation_id="d", run_id="r", membership_id="other"):
        other = await asyncio.wait_for(upstream.acquire("k", "pi_step"), 1)
    assert upstream.stats()["inflight"] == {upstream.key_id("k"): 3}
    held[0]()
    release_third = await asyncio.wait_for(third, 1)
    for release in (held[1], other, release_third):
        release()
    assert upstream.stats()["inflight"] == {}


@pytest.mark.asyncio
async def test_the_key_cap_holds_across_teachers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(upstream.KEY_MAX_ENV, "4")
    releases = []
    for n in range(4):
        with upstream.caller_scope(conversation_id=f"c{n}", run_id="r", membership_id=f"m{n}"):
            releases.append(await upstream.acquire("k", "direct"))
    with upstream.caller_scope(conversation_id="c9", run_id="r", membership_id="m9"):
        fifth = asyncio.ensure_future(upstream.acquire("k", "direct"))
        await asyncio.sleep(0.05)
        assert not fifth.done()
    releases.pop()()
    (await asyncio.wait_for(fifth, 1))()
    for release in releases:
        release()
    assert upstream.stats()["peak"][upstream.key_id("k")] == 4


def _responses_stub(monkeypatch: pytest.MonkeyPatch, seen: list[dict]) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("PICO_MODEL_PROVIDER", "deepseek")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    provider._CLIENTS.clear()

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


@pytest.mark.asyncio
async def test_direct_call_in_a_conversation_carries_its_session(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []
    _responses_stub(monkeypatch, seen)
    for run in ("r1", "r2"):
        with upstream.caller_scope(conversation_id="conv-7", run_id=run, membership_id="m"):
            out = [p async for p in provider.stream_chat("hi", system="你是 Pico", model="pico-fast")]
        assert "".join(out) == "好"
    session = upstream.conversation_session("conv-7")
    for kw in seen:
        assert kw["prompt_cache_key"] == session
        assert kw["extra_headers"] == {"session_id": session}
    # Outside a conversation the old per-prompt key stays, with no session header.
    [p async for p in provider.stream_chat("hi", system="你是 Pico", model="pico-fast")]
    assert seen[-1]["prompt_cache_key"] == upstream.cache_key(seen[-1]["instructions"])
    assert "extra_headers" not in seen[-1]


@pytest.fixture
def proxy(monkeypatch: pytest.MonkeyPatch):
    from app import ws_proxy_router as mod
    from fastapi import FastAPI

    monkeypatch.setenv("PICO_RUNNER_TOKEN", TOKEN)
    seen: dict[str, Any] = {}

    async def fake_stream(method, target, headers, body, on_done=None, hedge=None, **door):
        from fastapi.responses import JSONResponse

        seen.update(headers=headers, caller=upstream.CALLER.get())
        if on_done is not None:
            on_done()
        return JSONResponse({"ok": True})

    monkeypatch.setattr(mod, "_stream", fake_stream)
    monkeypatch.setattr(mod, "request_on_loopback_socket", lambda request: True)
    app = FastAPI()
    app.include_router(mod.router)
    register_proxy(
        ProxyEntry(
            run_id="run5",
            llm_token="boxtok",
            llm_upstream="http://127.0.0.1:3000/v1",
            llm_key="REAL-KEY",
            tool_url="",
            tool_token="",
            model="gpt-5.6-sol",
            member="m" * 32,
            session="pcs-" + "c" * 32,
        )
    )
    yield TestClient(app), seen
    unregister_proxy("run5")


def test_proxy_sends_pi_session_and_waits_on_the_teacher(proxy) -> None:
    client, seen = proxy
    auth = {**H, "authorization": "Bearer boxtok", "session_id": "box-made-up"}
    body = {"model": "gpt-5.6-sol", "prompt_cache_key": "01a14ec4-7795-7284-a194-a8981fb3b7a2"}
    assert client.post("/internal/ws-proxy/l/run5/v1/responses", headers=auth, json=body).status_code == 200
    # Pi's cache key is its session (pinned per conversation): header and key agree.
    assert seen["headers"]["session_id"] == body["prompt_cache_key"]
    assert seen["caller"] == upstream.Caller(session=body["prompt_cache_key"], member="m" * 32)
    # No cache key in the body (chat/completions): the conversation's own session.
    r = client.post("/internal/ws-proxy/l/run5/v1/chat/completions", headers=auth, json={"model": "gpt-5.6-sol"})
    assert r.status_code == 200
    assert seen["headers"]["session_id"] == "pcs-" + "c" * 32
    assert upstream.CALLER.get() == upstream.Caller()


def test_proxy_entry_session_matches_the_direct_road() -> None:
    from pico_orchestrator.true_pi.runner import WorkspaceKey

    key = WorkspaceKey.for_run(school_id="s", membership_id="m", conversation_id="conv-7", run_id="r")
    assert upstream.SESSION_PREFIX + key.conv == upstream.conversation_session("conv-7")
    assert key.member == upstream.member_key("m")


def test_ruler_runs_take_turns_on_the_host(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ruler = _load("pico_ruler_lock", "scripts/pico-ruler.py")
    lock = str(tmp_path / "ruler.lock")
    first = ruler.hold_upstream_turn(lock)
    got: list[float] = []

    def second() -> None:
        fh = ruler.hold_upstream_turn(lock)
        got.append(time.monotonic())
        fh.close()

    t = threading.Thread(target=second)
    t.start()
    time.sleep(0.2)
    assert not got  # the second run waits
    first.close()
    t.join(2)
    assert got and "WAIT another ruler run" in capsys.readouterr().out


def _log(t: int, use: int, pt: int, cache: int, hint: str) -> tuple[int, int, int, str]:
    aff = {"key_path": "prompt_cache_key", "key_hint": hint, "key_fp": hint} if hint else {}
    return (t, use, pt, json.dumps({"cache_tokens": cache, "admin_info": {"channel_affinity": aff}}))


def test_pressure_report_reads_new_api_log() -> None:
    rep = _load("pressure_report", "scripts/pico-upstream-pressure-report.py")
    rows = [
        _log(100, 10, 1000, 0, "01a1...6aaa"),  # Pi session, step 1
        _log(105, 10, 1200, 900, "01a1...6aaa"),  # step 2 hits
        _log(106, 10, 1000, 0, "pcs-...ab12"),  # direct, conversation session
        _log(107, 10, 1000, 0, "pico...569e"),  # old per-prompt hash: no session header
        _log(108, 1, 1000, 0, ""),
    ]
    m = rep.measure(rows)
    assert m["peak"] == 4 and m["requests"] == 5
    assert m["kinds"] == {"pi_session": 2, "conversation": 1, "prompt_hash": 1, "none": 1}
    assert (m["later_steps"], m["later_hit"]) == (1, 1.0)
    assert m["cache_hit"] == pytest.approx(900 / 5200)
    # AIProxy is for long Pi sessions only: the direct road's one-shot calls miss.
    assert m["one_shot"] == 3
    assert rep.verdict(m) == ["一问请求 3 次（应为 0）"]
    rows.append(_log(109, 20, 10, 0, "01a1...6aaa"))
    rows.append(_log(110, 1, 10, 0, "01a1...7bbb"))  # a Pi run that ended in one step
    m = rep.measure(rows)
    assert m["single_request_sessions"] == 1
    assert rep.verdict(m)[-1] == "同时请求峰值 5 > 4"


def test_pressure_report_judges_only_picos_token(tmp_path: Path) -> None:
    db = tmp_path / "one-api.db"
    con = sqlite3.connect(db)
    con.execute("create table channels (id integer, name text)")
    con.execute(
        "create table logs (created_at int, type int, channel_id int, token_name text,"
        " use_time int, prompt_tokens int, other text)"
    )
    con.execute("insert into channels values (3, 'aiproxy-openai')")
    now = int(time.time())
    rows = [
        ("pico-gateway", _log(now - 60, 5, 1000, 0, "01a1...6aaa")),
        ("pico-gateway", _log(now - 50, 5, 1200, 900, "01a1...6aaa")),
        ("pico-probe", _log(now - 40, 1, 26, 0, "pico...2521")),  # platform smoke check
        ("pico-probe", _log(now - 30, 1, 26, 0, "pico...2521")),
    ]
    for token, (t, use, pt, other) in rows:
        con.execute("insert into logs values (?, 2, 3, ?, ?, ?, ?)", (t, token, use, pt, other))
    con.commit()
    run = subprocess.run(
        [sys.executable, str(ROOT / "scripts/pico-upstream-pressure-report.py"), "--db", str(db)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout
    assert "请求 2 " in run.stdout and "不判：pico-probe 2 次" in run.stdout
    assert "✅ 三条都过" in run.stdout



# --- AIProxy only for long multi-round sessions (owner 10-18 07:3x PDT) -------


def test_aiproxy_model_is_left_out_unless_the_call_is_a_long_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pico_orchestrator import brain_ha

    monkeypatch.delenv(brain_ha.LONG_SESSION_ENV, raising=False)
    monkeypatch.setenv("PICO_BRAIN_FALLBACKS", "grok-4.6,gpt-5.6-sol")
    assert brain_ha.brain_candidates("gemini-3.8-flash") == ["gemini-3.8-flash", "grok-4.6"]
    assert brain_ha.brain_candidates("gpt-5.6-sol") == ["grok-4.6"]
    assert brain_ha.brain_candidates("gemini-3.8-flash", long_session=True)[-1] == "gpt-5.6-sol"


@pytest.mark.asyncio
async def test_a_one_shot_call_never_reaches_aiproxy(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []
    _responses_stub(monkeypatch, seen)  # primary gpt-5.6-sol
    monkeypatch.delenv("PICO_LONG_SESSION_MODELS", raising=False)
    monkeypatch.setenv("PICO_BRAIN_FALLBACKS", "gpt-5.6-sol")
    with pytest.raises(RuntimeError, match="只给多轮会话用"):
        [p async for p in provider.stream_chat("hi", system="你是 Pico", model="pico-fast")]
    assert seen == []  # said so, no request went out


def test_a_ruler_stack_never_uses_aiproxy(tmp_path: Path) -> None:
    guard = ROOT / "scripts/pico-ruler-env-guard.py"
    env = tmp_path / "api.env"
    env.write_text("DEEPSEEK_MODEL=gemini-3.8-flash\nPICO_BRAIN_FALLBACKS=grok-4.6,gpt-5.6-sol\n")
    run = subprocess.run([sys.executable, str(guard), str(env)], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    lines = env.read_text().splitlines()
    assert "PICO_BRAIN_FALLBACKS=grok-4.6" in lines
    assert "PICO_LONG_SESSION_MODELS=gpt-5.6-sol" in lines
    # Fallbacks unset: the code default still names sol, so it is written out without it.
    env.write_text("DEEPSEEK_MODEL=gemini-3.8-flash\n")
    subprocess.run([sys.executable, str(guard), str(env)], check=True)
    assert "PICO_BRAIN_FALLBACKS=grok-4.6" in env.read_text().splitlines()
    # A sol-pinned stack does not start.
    env.write_text("DEEPSEEK_MODEL=gpt-5.6-sol\n")
    run = subprocess.run([sys.executable, str(guard), str(env)], capture_output=True, text=True, check=False)
    assert run.returncode == 4 and "DEEPSEEK_MODEL" in run.stderr
    assert env.read_text() == "DEEPSEEK_MODEL=gpt-5.6-sol\n"


@pytest.mark.asyncio
async def test_a_pi_run_may_fall_back_to_aiproxy(monkeypatch: pytest.MonkeyPatch) -> None:
    from pico_orchestrator import brain_ha
    from pico_orchestrator.run_types import RunCaps, RunResult
    from pico_orchestrator.true_pi import runtime as rt

    monkeypatch.delenv(brain_ha.LONG_SESSION_ENV, raising=False)
    monkeypatch.setenv("PICO_BRAIN_FALLBACKS", "gpt-5.6-sol")
    tried: list[str] = []

    async def once(*, emit, **kwargs) -> RunResult:
        tried.append(str(kwargs["caps"].backend_model))
        return RunResult(status="failed", final_text="", error="boom", code="true_pi.assistant_error")

    async def emit(kind: str, payload: dict) -> None:
        return None

    async def never() -> bool:
        return False

    monkeypatch.setattr(rt, "_run_true_pi_once", once)
    await rt.run_true_pi_agent(
        prompt="hi",
        principal=SimpleNamespace(school_id="s", membership_id="m"),
        emit=emit,
        is_cancelled=never,
        caps=RunCaps(backend_model="gemini-3.8-flash", ui_model="pico-fast"),
    )
    assert tried == ["gemini-3.8-flash", "gpt-5.6-sol"]
