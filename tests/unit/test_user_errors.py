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
    assert "超时" in user_message_for_error("timeout after 120s")


def test_enrich():
    p = enrich_fail_payload({"status": "failed", "reason": "token_cap", "code": "token_cap"})
    assert "user_message" in p
    assert "上限" in p["user_message"]

def test_sqlite_lock_not_leaked_to_user() -> None:
    msg = user_message_for_error("(sqlite3.OperationalError) database is locked")
    assert "sqlite" not in msg.lower()
    assert "OperationalError" not in msg
    assert "重试" in msg or "繁忙" in msg

