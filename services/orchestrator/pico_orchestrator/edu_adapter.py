"""Edu read adapter — Phase 3 swaps FakeEdu → live HTTP without renaming tools."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

CHANGE_HANDOFF_PATH = "/internal/pico/change-proposals"
_HANDOFF_FIELDS = {
    "pico_change_id",
    "school_id",
    "membership_id",
    "title",
    "summary",
    "payload",
    "confirmed_at",
    "confirmed_by",
}


class EduAdapterError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def edu_mode() -> str:
    mode = (os.environ.get("PICO_EDU_MODE") or "fake").strip().lower()
    if mode not in {"fake", "live"}:
        raise EduAdapterError(
            "edu.config_error",
            "PICO_EDU_MODE must be fake or live",
        )
    return mode


def _live_config() -> tuple[str, str, float]:
    base = (os.environ.get("PICO_EDU_BASE_URL") or "").rstrip("/")
    token = (os.environ.get("PICO_EDU_SERVICE_TOKEN") or "").strip()
    if not base or not token:
        raise EduAdapterError(
            "edu.config_error",
            "live mode requires PICO_EDU_BASE_URL and PICO_EDU_SERVICE_TOKEN",
        )
    timeout = float(os.environ.get("PICO_EDU_TIMEOUT_SECONDS") or "10")
    return base, token, timeout


def build_change_handoff(
    *,
    pico_change_id: str,
    school_id: str,
    membership_id: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
    confirmed_at: datetime,
    confirmed_by: str,
) -> dict[str, Any]:
    return validate_change_handoff(
        {
            "pico_change_id": pico_change_id,
            "school_id": school_id,
            "membership_id": membership_id,
            "title": title,
            "summary": summary,
            "payload": payload,
            "confirmed_at": (
                confirmed_at
                if confirmed_at.tzinfo is not None
                else confirmed_at.replace(tzinfo=UTC)
            ).isoformat(),
            "confirmed_by": confirmed_by,
        }
    )


def validate_change_handoff(body: dict[str, Any]) -> dict[str, Any]:
    missing = _HANDOFF_FIELDS - body.keys()
    extra = body.keys() - _HANDOFF_FIELDS
    if missing or extra:
        raise EduAdapterError(
            "edu.contract_error",
            f"invalid change handoff fields missing={sorted(missing)} extra={sorted(extra)}",
        )
    for field in (
        "pico_change_id",
        "school_id",
        "membership_id",
        "title",
        "confirmed_at",
        "confirmed_by",
    ):
        value = body[field]
        if not isinstance(value, str) or not value.strip():
            raise EduAdapterError(
                "edu.contract_error",
                f"change handoff {field} must be a non-empty string",
            )
    if not isinstance(body["summary"], str):
        raise EduAdapterError(
            "edu.contract_error",
            "change handoff summary must be a string",
        )
    if not isinstance(body["payload"], dict):
        raise EduAdapterError(
            "edu.contract_error",
            "change handoff payload must be an object",
        )
    try:
        parsed_at = datetime.fromisoformat(body["confirmed_at"])
    except ValueError as exc:
        raise EduAdapterError(
            "edu.contract_error",
            "change handoff confirmed_at must be ISO-8601",
        ) from exc
    if "T" not in body["confirmed_at"] or parsed_at.tzinfo is None:
        raise EduAdapterError(
            "edu.contract_error",
            "change handoff confirmed_at must include time and timezone",
        )
    return {field: body[field] for field in _HANDOFF_FIELDS}


async def list_classes_live(school_id: str, *, limit: int = 20) -> dict[str, Any]:
    base, token, timeout = _live_config()
    url = f"{base}/api/v1/pico/classes"
    headers = {"Authorization": f"Bearer {token}", "X-Pico-School-Id": school_id}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, params={"school_id": school_id, "limit": limit}, headers=headers)
    if resp.status_code == 403:
        raise EduAdapterError("tenant.cross_school", resp.text)
    if resp.status_code >= 400:
        raise EduAdapterError("tool.upstream_error", f"edu HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    classes = data.get("classes") or data.get("items") or []
    return {
        "school_id": data.get("school_id") or school_id,
        "classes": [
            {"id": str(c.get("id", "")), "name": str(c.get("name", ""))}
            for c in classes[:limit]
        ],
        "source": "edu_live",
    }


async def list_classes_fake(school_id: str, *, limit: int = 20) -> dict[str, Any]:
    catalog = {
        "school-a": [
            {"id": "cls-a1", "name": "一年级 1 班"},
            {"id": "cls-a2", "name": "一年级 2 班"},
        ],
        "school-b": [
            {"id": "cls-b1", "name": "二年级 1 班"},
        ],
    }
    classes = catalog.get(school_id, [])
    return {
        "school_id": school_id,
        "classes": classes[:limit],
        "source": "fake_edu",
    }


async def list_classes(school_id: str, *, limit: int = 20) -> dict[str, Any]:
    mode = edu_mode()
    if mode == "live":
        return await list_classes_live(school_id, limit=limit)
    return await list_classes_fake(school_id, limit=limit)


async def push_change_proposal(body: dict[str, Any]) -> dict[str, Any] | None:
    """Optional Pico → edu handoff after human confirm."""
    envelope = validate_change_handoff(body)
    if edu_mode() == "fake":
        return None
    if (os.environ.get("PICO_EDU_HANDOFF_ENABLED") or "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        return None
    base, token, timeout = _live_config()
    url = f"{base}{CHANGE_HANDOFF_PATH}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=envelope, headers=headers)
    if resp.status_code >= 400:
        raise EduAdapterError(
            "tool.upstream_error", f"handoff HTTP {resp.status_code}: {resp.text[:300]}"
        )
    return resp.json()
