from pico_orchestrator.brain_ha import brain_candidates, should_failover


class _Res:
    def __init__(self, status: str, error: str = "", code: str = "") -> None:
        self.status = status
        self.error = error
        self.code = code


def test_candidates_primary_then_fallbacks(monkeypatch) -> None:
    monkeypatch.setenv("PICO_BRAIN_FALLBACKS", "grok-4.6,gpt-5.6-sol")
    assert brain_candidates("gemini-3.8-flash")[:3] == [
        "gemini-3.8-flash",
        "grok-4.6",
        "gpt-5.6-sol",
    ]


def test_failover_only_on_channel_death() -> None:
    assert should_failover(_Res("failed", "Failed to get available channel for model x"))
    assert not should_failover(_Res("succeeded", "ok"))
    assert not should_failover(_Res("cancelled"))
    assert not should_failover(_Res("failed", "timeout after 10s", "timeout"))


def test_resume_note_and_prompt_name_no_model() -> None:
    from pico_orchestrator.teacher_text import leaks
    from pico_orchestrator.true_pi.runtime import resume_prompt, resume_teacher_note

    assert not leaks(resume_teacher_note(1))
    assert not leaks(resume_teacher_note(2, tool_hang=True))
    raw = 'OpenAI API error (400): {"message":"Invalid request."}'
    assert "OpenAI" not in resume_prompt(raw)


async def _drive(monkeypatch, attempts):
    """Run the live HA loop over scripted attempts: [(events, RunResult), ...]."""
    from types import SimpleNamespace

    from pico_orchestrator.run_types import RunCaps
    from pico_orchestrator.true_pi import runtime

    monkeypatch.setenv("PICO_BRAIN_FALLBACKS", "grok-4.6")
    seen: list[tuple[str, dict]] = []
    tried: list[str] = []
    script = list(attempts)

    async def fake_once(*, emit, caps, **_kw):
        tried.append(caps.backend_model)
        events, result = script.pop(0)
        for kind, payload in events:
            await emit(kind, payload)
            # A live event must reach the real emitter before the attempt ends.
            if kind == "tool.call":
                assert ("tool.call", payload) in seen
        return result

    async def emit(kind, payload):
        seen.append((kind, payload))

    async def never():
        return False

    monkeypatch.setattr(runtime, "_run_true_pi_once", fake_once)
    last = await runtime.run_true_pi_agent(
        prompt="x",
        principal=SimpleNamespace(school_id="s", membership_id="m"),
        emit=emit,
        is_cancelled=never,
        caps=RunCaps(backend_model="gemini-3.8-flash"),
    )
    return last, seen, tried


async def test_events_stream_live_once_model_answers(monkeypatch) -> None:
    from pico_orchestrator.run_types import RunResult

    ok = RunResult(status="succeeded", final_text="done")
    last, seen, tried = await _drive(
        monkeypatch,
        [([("run.status", {"status": "running"}), ("tool.call", {"tool": "bash"})], ok)],
    )
    assert last.status == "succeeded"
    assert tried == ["gemini-3.8-flash"]
    assert [k for k, _ in seen] == ["run.status", "tool.call"]


async def test_dead_channel_before_output_fails_over_quietly(monkeypatch) -> None:
    from pico_orchestrator.run_types import RunResult

    dead = RunResult(status="failed", final_text="", error="upstream error: do request failed")
    ok = RunResult(status="succeeded", final_text="done")
    last, seen, tried = await _drive(
        monkeypatch,
        [
            ([("run.status", {"status": "running"})], dead),
            ([("tool.call", {"tool": "bash"})], ok),
        ],
    )
    assert last.status == "succeeded"
    assert tried == ["gemini-3.8-flash", "grok-4.6"]
    kinds = [k for k, _ in seen]
    # The switch is invisible: no note, no model name, only the live work.
    assert kinds == ["tool.call"]


async def test_no_restart_after_teacher_saw_progress(monkeypatch) -> None:
    from pico_orchestrator.run_types import RunResult

    dead = RunResult(status="failed", final_text="", error="upstream error: do request failed")
    last, seen, tried = await _drive(
        monkeypatch,
        [([("tool.call", {"tool": "bash"}), ("run.status", {"status": "failed"})], dead)],
    )
    assert last.status == "failed"
    assert tried == ["gemini-3.8-flash"]
    assert [k for k, _ in seen] == ["tool.call", "run.status"]
