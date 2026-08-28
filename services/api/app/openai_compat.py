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
    SIDEBAR_WEB_SYSTEM,
    SIDEBAR_WORKBENCH_HINT,
    asked_from_sidebar_prompt,
    honest_miss_json,
    inject_web_hits,
    is_json_only_propose,
    shape_web_hits,
)
from pico_orchestrator.day_use import apply_day_use
from pico_orchestrator.user_errors import user_message_for_error
from pydantic import BaseModel
