"""Exam marking lane (pico#1379, edu-core#4576): its own New API token and models.

Owner 11-02「阅卷需要单列，至于用哪个模型 我需要灵活可方便切换」. A ticket with
``ai:exam-grading`` (edu AI marking only) runs the whole call under this scope:

- the relay key is ``PICO_GRADING_API_KEY`` (New API token ``pico-grading``,
  group ``grading``: which channels answer marking is set there, not here);
  unset = the chat key, as before;
- ``pico-ocr`` (handwriting transcription) → the ``ocr`` model, ``pico-score2``
  (edu's second scorer, edu-core#4576 ⑨c) → the ``score2`` model (unset = ``score``),
  every other lane (scoring) → the ``score`` model, from ``data/grading-models.json``::

      {"default": {"ocr": "gemini-3.8-flash", "score": "deepseek-flash"},
       "schools": {"<school_id>": {"score": "gemini-3.8-flash"}}}

  Missing file / key = today's models (``PICO_OCR_MODEL`` / the brain). The file
  is re-read when it changes: switching needs no restart
  (``scripts/grading-model.py`` writes it after a preflight).
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

logger = logging.getLogger(__name__)

GRADING_KEY_ENV = "PICO_GRADING_API_KEY"
PATH_ENV = "PICO_GRADING_MODELS_PATH"
LANE_TAG = "grading"

# School id of the marking ticket for this request; None = not marking.
_grading_school: ContextVar[str | None] = ContextVar("pico_grading_school", default=None)


def enter_grading(school_id: str | None) -> None:
    """Mark the rest of this request as exam marking (``None`` = not marking).

    Set on every request and never reset: each HTTP request runs in its own task
    context, and a streamed body keeps reading it after the endpoint has returned.
    """
    _grading_school.set(school_id)


@contextmanager
def grading_scope(school_id: str | None):
    if school_id is None:
        yield
        return
    token = _grading_school.set(school_id)
    try:
        yield
    finally:
        _grading_school.reset(token)


def current_grading_school() -> str | None:
    return _grading_school.get()


def config_path() -> Path:
    raw = (os.environ.get(PATH_ENV) or "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[3] / "data" / "grading-models.json"


_cache: tuple[str, float, dict] | None = None


def load_config() -> dict:
    """The file as written, ``{}`` when absent or unreadable (marking keeps today's models)."""
    global _cache
    path = config_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if _cache is not None and _cache[0] == str(path) and _cache[1] == mtime:
        return _cache[2]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # A half-written or hand-broken file must not stop marking: old models, loudly.
        logger.exception("grading models file unreadable: %s", path)
        return _cache[2] if _cache is not None and _cache[0] == str(path) else {}
    data = data if isinstance(data, dict) else {}
    _cache = (str(path), mtime, data)
    return data


def _pick(data: dict, school_id: str | None, role: str) -> str:
    schools = data.get("schools") if isinstance(data.get("schools"), dict) else {}
    for layer in (schools.get(school_id or "") if school_id else None, data.get("default")):
        if isinstance(layer, dict):
            mid = str(layer.get(role) or "").strip()
            if mid:
                return mid
    return ""


def grading_model(role: str, school_id: str | None = None) -> str:
    """``role`` = ``ocr`` | ``score`` | ``score2``; "" = no override (today's model)."""
    return _pick(load_config(), school_id, role)


def grading_api_key() -> str:
    return (os.environ.get(GRADING_KEY_ENV) or "").strip()
