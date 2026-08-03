"""Tenant identity redaction for teacher-visible agent/tool text (stage #265)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.redact import redact_tenant_payload, redact_tenant_text
from pico_orchestrator.user_errors import user_message_for_error


def test_redact_key_value_pairs() -> None:
    raw = 'school_id=school-a membership_id=member-9 token_school_id:"abc"'
    out = redact_tenant_text(raw, school_id="school-a", membership_id="member-9")
    assert "school-a" not in out
    assert "member-9" not in out
    assert "已脱敏" in out or "学校标识" in out


def test_redact_payload_strips_id_keys() -> None:
    payload = {
        "proposal": {
            "title": "t",
            "school_id": "school-a",
            "membership_id": "m-1",
            "note": "ok",
        }
    }
    out = redact_tenant_payload(payload, school_id="school-a", membership_id="m-1")
    assert out["proposal"]["school_id"] == "[已脱敏]"
    assert out["proposal"]["membership_id"] == "[已脱敏]"
    assert out["proposal"]["title"] == "t"


def test_cross_school_message_is_chinese() -> None:
    msg = user_message_for_error("Cross-school deny: token=school-a tool=school-b", code="tenant.cross_school")
    assert "school-a" not in msg
    assert "跨校" in msg


def test_max_steps_message_is_chinese() -> None:
    msg = user_message_for_error("max_steps exceeded after 40 steps")
    assert "步骤" in msg
    assert "traceback" not in msg.lower()
