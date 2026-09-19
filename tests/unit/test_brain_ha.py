from pico_orchestrator.brain_ha import (
    brain_candidates,
    fallback_teacher_note,
    should_failover,
)


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


def test_teacher_note_is_human() -> None:
    msg = fallback_teacher_note("gemini-3.8-flash", "grok-4.6")
    assert "备用" in msg
    assert "【错误】" not in msg
