"""Owner 2026-10-14 14:28: teachers never see a model / vendor name or the plumbing."""

from __future__ import annotations

import ast
from pathlib import Path

from pico_orchestrator.teacher_text import GENERIC_RETRY, leaks, teacher_safe
from pico_orchestrator.true_pi.runtime import resume_teacher_note
from pico_orchestrator.user_errors import enrich_fail_payload, user_message_for_error

ROOT = Path(__file__).resolve().parents[2]
ORCH = ROOT / "services/orchestrator/pico_orchestrator"

# Raw failures seen on live (pico.db runs / events), plus the usual relay errors.
LIVE_RAW = [
    'OpenAI API error (400): {"message":"Invalid request.","type":"invalid_request_error","param":"","code":"invalid_request_error"}',
    "Cannot read properties of undefined (reading 'startsWith')",
    "Failed to get available channel for model gpt-5.6-sol",
    '403: {"message":"预扣费额度失败, 用户剩余额度: ＄2.56","type":"new_api_error","code":"insufficient_user_quota"}',
    'OpenAI API error (500): {"message":"upstream error: do request failed","type":"new_api_error","code":"do_request_failed"}',
    'OpenAI API error (503): {"message":"AIProxy service is temporarily unavailable."}',
    "HTTP 524: AIProxy service is temporarily unavailable",
    "server_error: Our servers are currently overloaded.",
    "stream ended abnormally",
    "401 unauthorized",
    "rate limit exceeded (429)",
    "usage limit reached for gemini-3.8-flash",
    "empty model response",
    "connection reset by peer",
    "BLOCKED S1: no KIMI_API_KEY or DEEPSEEK_API_KEY",
    "出图尚未接通。请管理员配置 PICO_IMAGE_GATEWAY_URL + PICO_IMAGE_GATEWAY_KEY 后重试",
    "grok-4.6 returned an unexpected tool call",
    "Anthropic API error: overloaded_error",
    "mcp allowlist denied",
    "something odd happened",
]


def test_leak_list() -> None:
    for bad in (
        "主渠道（gpt-5.6-sol）暂时不可用，已改用备用模型 gemini-3.8-flash 继续。",
        "模型中转暂时不可用（上游 503）",
        "请管理员检查网关出网",
        "Claude 忙",
        "请配置 PICO_IMAGE_GATEWAY_URL",
        "HTTP 400",
    ):
        assert leaks(bad), bad
    for ok in (
        "这会儿有点忙，请稍等再发一次。不是你的问题写错。",
        "（稍等，正在重试，第 2 次）",
        "这次已经跑了约 4 小时，我先停在这里",
        "student_no 不对",
    ):
        assert not leaks(ok), ok
    assert teacher_safe("OpenAI API error (400)") == GENERIC_RETRY
    assert teacher_safe("回复中途断了。") == "回复中途断了。"


def test_every_live_raw_error_reaches_teacher_clean() -> None:
    for raw in LIVE_RAW:
        for code in (None, "true_pi.assistant_error", "model.unconfigured", "image.unconfigured"):
            msg = user_message_for_error(raw, code=code)
            assert msg and not leaks(msg), (raw, code, msg)
            payload = enrich_fail_payload({"status": "failed", "reason": raw, "code": code})
            assert not leaks(payload["user_message"]), (raw, payload)


def test_preset_user_message_is_scrubbed_too() -> None:
    out = enrich_fail_payload(
        {"status": "failed", "reason": "x", "user_message": "未能完成：OpenAI API error (400)"}
    )
    assert out["user_message"] == GENERIC_RETRY


def _returned_literals(path: Path) -> list[tuple[int, str]]:
    """String pieces a function in ``path`` can hand back (returns + raised messages)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[int, str]] = []
    roots: list[ast.AST] = [n.value for n in ast.walk(tree) if isinstance(n, ast.Return) and n.value]
    roots += [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id.endswith("_MESSAGE") for t in n.targets)
    ]
    for root in roots:
        for node in ast.walk(root):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append((node.lineno, node.value))
    return out


def test_teacher_copy_in_source_names_no_model() -> None:
    files = [
        ORCH / "user_errors.py",
        ORCH / "brain_ha.py",
        ORCH / "image_generate.py",
        ORCH / "teacher_text.py",
    ]
    bad = []
    for path in files:
        for line, text in _returned_literals(path):
            # Lowercase single tokens are markers / codes, never shown.
            if text.isascii() and " " not in text.strip():
                continue
            if leaks(text):
                bad.append(f"{path.name}:{line}: {text}")
    assert not bad, "\n".join(bad)


def test_retry_notes_are_quiet() -> None:
    for i in (1, 2, 3):
        assert not leaks(resume_teacher_note(i))
        assert not leaks(resume_teacher_note(i, tool_hang=True))
