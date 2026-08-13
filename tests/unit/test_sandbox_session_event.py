import pytest
from pico_orchestrator.sandbox_session_event import sandbox_session_payload
from pico_orchestrator.true_pi.client import RpcEvent
from pico_orchestrator.true_pi.events import EventMapState, map_event


def test_sandbox_session_payload_drops_secrets_and_requires_sbox_id() -> None:
    assert sandbox_session_payload({"session_id": "nope", "url": "https://example.com/"}) is None
    out = sandbox_session_payload(
        {
            "session_id": "sbox_aaaaaaaaaaaaaaaaaaaaaaaa",
            "url": "https://example.com/",
            "title": "Example Domain",
            "password": "must-not-appear",
            "secret": "must-not-appear",
            "human_copy": "请在此画面自行登录，不要在聊天里发送密码",
        }
    )
    assert out is not None
    assert out["session_id"].startswith("sbox_")
    assert out["url"] == "https://example.com/"
    assert "password" not in out
    assert "secret" not in out
    assert "不要在聊天里发送密码" in out["human_copy"]


@pytest.mark.asyncio
async def test_true_pi_emits_sandbox_session_without_password() -> None:
    emitted: list[tuple[str, dict]] = []

    async def emit(kind: str, payload: dict) -> None:
        emitted.append((kind, payload))

    state = EventMapState()
    await map_event(
        RpcEvent(
            {
                "type": "tool_execution_end",
                "toolName": "sandbox_browser_open",
                "result": {
                    "session_id": "sbox_dddddddddddddddddddddddd",
                    "url": "https://example.com/",
                    "title": "Example Domain",
                    "password": "must-not-appear",
                },
            }
        ),
        emit=emit,
        state=state,
    )
    kinds = [k for k, _ in emitted]
    assert "tool.result" in kinds
    assert "sandbox.session" in kinds
    session = next(p for k, p in emitted if k == "sandbox.session")
    assert session["session_id"] == "sbox_dddddddddddddddddddddddd"
    assert "password" not in session
    dumped = str(emitted)
    assert "must-not-appear" not in dumped
