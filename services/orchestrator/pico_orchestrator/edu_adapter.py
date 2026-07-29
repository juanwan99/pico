"""Edu read adapter — Phase 3 swaps FakeEdu → live HTTP without renaming tools."""

from __future__ import annotations

import os
from typing import Any

import httpx


class EduAdapterError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def edu_mode() -> str:
    return (os.environ.get("PICO_EDU_MODE") or "fake").strip().lower()


async def list_classes_live(school_id: str, *, limit: int = 20) -> dict[str, Any]:
    base = (os.environ.get("PICO_EDU_BASE_URL") or "").rstrip("/")
    token = (os.environ.get("PICO_EDU_SERVICE_TOKEN") or "").strip()
    if not base or not token:
        raise EduAdapterError(
            "tool.upstream_error",
            "PICO_EDU_BASE_URL and PICO_EDU_SERVICE_TOKEN required for live mode",
        )
    timeout = float(os.environ.get("PICO_EDU_TIMEOUT_SECONDS") or "10")
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
    if edu_mode() == "live":
        return await list_classes_live(school_id, limit=limit)
    return await list_classes_fake(school_id, limit=limit)


async def push_change_proposal(body: dict[str, Any]) -> dict[str, Any] | None:
    """Optional Pico → edu handoff after human confirm."""
    if (os.environ.get("PICO_EDU_HANDOFF_ENABLED") or "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        return None
    base = (os.environ.get("PICO_EDU_BASE_URL") or "").rstrip("/")
    token = (os.environ.get("PICO_EDU_SERVICE_TOKEN") or "").strip()
    if not base or not token:
        raise EduAdapterError(
            "tool.upstream_error",
            "handoff enabled but PICO_EDU_BASE_URL/TOKEN missing",
        )
    timeout = float(os.environ.get("PICO_EDU_TIMEOUT_SECONDS") or "10")
    url = f"{base}/api/v1/pico/change-proposals"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=body, headers=headers)
    if resp.status_code >= 400:
        raise EduAdapterError(
            "tool.upstream_error", f"handoff HTTP {resp.status_code}: {resp.text[:300]}"
        )
    return resp.json()
