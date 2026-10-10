"""Repo-wide test defaults.

Office scripts run in-process during tests (``PICO_OFFICE_URL=embedded``) so the
same ``run_office_job`` code path is exercised without the pico-office container.
Production compose pins the unix socket instead; never ship "embedded".
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("PICO_OFFICE_URL", "embedded")


@pytest.fixture(autouse=True)
def _empty_json_only_replay():
    """#1204: a replayed answer from one test must not leak into the next."""
    try:
        from app import json_only_replay
    except ImportError:
        yield
        return
    json_only_replay.clear()
    yield
    json_only_replay.clear()
