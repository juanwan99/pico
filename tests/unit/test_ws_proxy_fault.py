"""#1104 T1 chaos switch: one 502 on the N-th model call, then the flag is gone."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from app import ws_proxy_router as wpr


def test_no_flag_file_never_faults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(wpr.FAULT_FILE_ENV, str(tmp_path / "absent"))
    wpr._model_calls.clear()
    assert all(not wpr.fault_injected("r1") for _ in range(5))
    assert not wpr._model_calls


def test_nth_call_faults_once_and_removes_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag = tmp_path / "fault"
    flag.write_text("3")
    monkeypatch.setenv(wpr.FAULT_FILE_ENV, str(flag))
    wpr._model_calls.clear()
    assert wpr.fault_injected("r1") is False
    assert wpr.fault_injected("r1") is False
    assert wpr.fault_injected("r1") is True
    assert not flag.exists()
    assert wpr.fault_injected("r1") is False


def test_bad_flag_content_defaults_to_second_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag = tmp_path / "fault"
    flag.write_text("nope")
    monkeypatch.setenv(wpr.FAULT_FILE_ENV, str(flag))
    wpr._model_calls.clear()
    assert wpr.fault_injected("r2") is False
    assert wpr.fault_injected("r2") is True
