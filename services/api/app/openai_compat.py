"""OpenAI-compatible /v1/chat/completions for LibreChat and API clients."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pico_orchestrator.edu_sidebar import (
    EDU_SIDEBAR_ALLOWED_TOOLS,
    SIDEBAR_WEB_SYSTEM,
    SIDEBAR_WORKBENCH_HINT,
    asked_from_sidebar_prompt,
    edu_sidebar_tool_ceiling,
    honest_miss_json,
    inject_web_hits,
    is_json_only_propose,
    shape_web_hits,
    sidebar_chat_only,
    with_sidebar_workbench_hint,
)
from pico_orchestrator.sse_keepalive import (
    SSE_COMMENT_KEEPALIVE,
    SSE_KEEPALIVE_SECONDS,
    SSE_STREAM_HEADERS,
    iter_with_idle_ticks,
)
from pico_orchestrator.user_errors import user_message_for_error
from pydantic import BaseModel

from app.auth import (
    LEGACY_PROXY_MEMBERSHIP_ID,
    Principal,
    decode_token,
    enforce_scope,
    prompt_membership_conflicts_header,
    scope_proxy_principal,
)
from app.db import RunRow, TaskRow, append_event, new_id, session_factory
from app.settings import Settings, get_settings

router = APIRouter(tags=["openai-compat"])
