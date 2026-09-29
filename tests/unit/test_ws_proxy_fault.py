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
    assert all(wpr.fault_injected("r1") == "" for _ in range(5))
    assert not wpr._model_calls


def test_nth_call_faults_once_and_removes_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag = tmp_path / "fault"
    flag.write_text("3")
    monkeypatch.setenv(wpr.FAULT_FILE_ENV, str(flag))
    wpr._model_calls.clear()
    assert wpr.fault_injected("r1") == ""
    assert wpr.fault_injected("r1") == ""
    assert wpr.fault_injected("r1") == "502"
    assert not flag.exists()
    assert wpr.fault_injected("r1") == ""


def test_bad_flag_content_defaults_to_second_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag = tmp_path / "fault"
    flag.write_text("nope")
    monkeypatch.setenv(wpr.FAULT_FILE_ENV, str(flag))
    wpr._model_calls.clear()
    assert wpr.fault_injected("r2") == ""
    assert wpr.fault_injected("r2") == "502"


def test_cut_mode_drops_stream_without_finish_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flag = tmp_path / "fault"
    flag.write_text("1 cut")
    monkeypatch.setenv(wpr.FAULT_FILE_ENV, str(flag))
    wpr._model_calls.clear()
    assert wpr.fault_injected("r3") == "cut"
    assert not flag.exists()
    assert "finish_reason\":null" in wpr._CUT_CHUNK and "[DONE]" not in wpr._CUT_CHUNK
    resp = wpr._cut_stream()
    assert resp.status_code == 200 and resp.media_type == "text/event-stream"


def test_count_keeps_faulting_consecutive_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``3 cut 6``: calls 3..8 are cut (more than Pi's 5 retries), then the flag is gone."""
    flag = tmp_path / "fault"
    flag.write_text("3 cut 6")
    monkeypatch.setenv(wpr.FAULT_FILE_ENV, str(flag))
    wpr._model_calls.clear()
    wpr._fault_hits = 0
    got = [wpr.fault_injected("r4") for _ in range(9)]
    assert got == ["", "", "cut", "cut", "cut", "cut", "cut", "cut", ""]
    assert not flag.exists()
    assert wpr._fault_hits == 0
