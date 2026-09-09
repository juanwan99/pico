"""Repo-wide test defaults.

Office scripts run in-process during tests (``PICO_OFFICE_URL=embedded``) so the
same ``run_office_job`` code path is exercised without the pico-office container.
Production compose pins the unix socket instead; never ship "embedded".
"""

from __future__ import annotations

import os

os.environ.setdefault("PICO_OFFICE_URL", "embedded")
