import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "user_errors",
    Path(__file__).resolve().parents[2]
    / "services/orchestrator/pico_orchestrator/user_errors.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_mod)
user_message_for_error = _mod.user_message_for_error
enrich_fail_payload = _mod.enrich_fail_payload


def test_no_key_message():
    msg = user_message_for_error("BLOCKED S1: no KIMI_API_KEY or DEEPSEEK_API_KEY")
    assert "密钥" in msg or "模型" in msg
    assert "BLOCKED" not in msg


def test_timeout():
    msg = user_message_for_error("Kimi Agent timeout after 120s", code="timeout")
    assert "超时" in msg
    assert "再跑一次" in msg


def test_ask_timeout_is_not_run_budget():
    msg = user_message_for_error(
        "超时未选，没有执行。请再发一次并选「确认执行」。",
        code="ask.timeout",
    )
    assert "超时未选" in msg
    assert "15 分钟" not in msg
    assert "确认执行" in msg


def test_max_steps_mentions_retry():
    msg = user_message_for_error("Kimi Agent reached the step limit", code="kimi.max_steps")
    assert "步骤" in msg
    assert "再跑一次" in msg


def test_enrich():
    p = enrich_fail_payload({"status": "failed", "reason": "token_cap", "code": "token_cap"})
    assert "user_message" in p
    assert "上限" in p["user_message"]

def test_sqlite_lock_not_leaked_to_user() -> None:
    msg = user_message_for_error("(sqlite3.OperationalError) database is locked")
    assert "sqlite" not in msg.lower()
    assert "OperationalError" not in msg
    assert "重试" in msg or "繁忙" in msg


def test_kimi_contract_and_runtime_errors_are_user_safe() -> None:
    msg = user_message_for_error("partial ToolCall", code="kimi.event_contract")
    assert "智能体" in msg
    assert "ToolCall" not in msg
    msg2 = user_message_for_error(
        "FileNotFoundError: /tmp/x/system.md", code="kimi.runtime_error"
    )
    assert "智能体" in msg2
    assert "FileNotFound" not in msg2


def test_capacity_and_emergency_messages_are_human() -> None:
    busy = user_message_for_error("chat capacity exceeded", code="concurrency_limit")
    assert "繁忙" in busy or "并发" in busy
    assert "traceback" not in busy.lower()
    rl = user_message_for_error("429 rate limit", code="rate_limit")
    assert "限流" in rl or "频繁" in rl
    noop = user_message_for_error(
        "PICO_LEGACY_AGENT_LOOP_EMERGENCY is no-op",
        code="runtime.emergency_noop",
    )
    assert "Pi" in noop or "编排" in noop or "Kimi" in noop or "过渡" in noop
    assert "run_agent_loop" not in noop


def test_api_restart_owner_lost_is_human_with_rerun_cta() -> None:
    msg = user_message_for_error(
        "run owner was lost during API restart", code="api.restart"
    )
    assert "重启" in msg or "维护" in msg
    assert "重新运行" in msg
    assert "owner was lost" not in msg.lower()
    cancelled = user_message_for_error("cancelled", code="cancelled")
    assert "云端" in cancelled or "停止" in cancelled
    assert "停止生成" not in cancelled  # not the input-bar screen-only copy


def test_stream_terminated_english_is_human_with_rerun_cta() -> None:
    """LibreChat main bubble often surfaces this after process kill — never leave raw English."""
    for raw in (
        "terminated",
        "An error occurred while processing the request: terminated",
        "Something went wrong. Here's the specific error message we encountered: terminated",
    ):
        msg = user_message_for_error(raw)
        assert "维护" in msg or "重启" in msg
        assert "重新运行" in msg
        assert "terminated" not in msg.lower()
        assert "something went wrong" not in msg.lower()


def test_image_unconfigured_not_model_key() -> None:
    msg = user_message_for_error(
        "出图尚未接通。请管理员在主机写入 GEMINI_API_KEY"
        "（或 PICO_IMAGE_GATEWAY_URL + PICO_IMAGE_GATEWAY_KEY）后重试，不能编造图片。",
        code="image.unconfigured",
    )
    assert "不能编造" in msg
    assert "DEEPSEEK" not in msg
    assert "SILICONFLOW" not in msg


def test_image_provider_run_fail_not_blamed_on_missing_zhipu() -> None:
    """Live bug 2026-08-27: tool returned image.provider; run failed as
    tool.write_failed with already-humanized「这次没能出图」; enrich remapped
    that copy to「ZHIPU_API_KEY 尚未接通」because code was not image.*.
    """
    from pico_orchestrator.user_errors import enrich_fail_payload

    human = "这次没能出图。请稍后重试，不能编造图片。"
    # Direct remap with run-level code (what enrich_fail_payload does).
    msg = user_message_for_error(human, code="tool.write_failed")
    assert "ZHIPU" not in msg
    assert "尚未接通" not in msg
    assert "没能出图" in msg

    payload = enrich_fail_payload(
        {
            "status": "failed",
            "reason": human,
            "code": "tool.write_failed",
            "runtime": "pi-true",
        }
    )
    assert "ZHIPU" not in payload["user_message"]
    assert "尚未接通" not in payload["user_message"]
    assert "没能出图" in payload["user_message"]


def test_image_siliconflow_rejected_copy() -> None:
    msg = user_message_for_error(
        "出图提供商硅基流动已否决，不再调用。请使用 Gemini 或智谱出图，不能编造图片。",
        code="image.provider_rejected",
    )
    assert "否决" in msg
    assert "Gemini" in msg or "智谱" in msg
    assert "SILICONFLOW" not in msg


def test_enrich_restart_payload_sets_user_message() -> None:
    p = enrich_fail_payload(
        {
            "status": "failed",
            "error": "run owner was lost during API restart",
            "code": "api.restart",
        }
    )
    assert "user_message" in p
    assert "重新运行" in p["user_message"]
    assert "owner was lost" not in p["user_message"].lower()

