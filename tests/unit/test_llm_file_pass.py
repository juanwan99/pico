"""GPT file pass: originals only, never a Pico reader."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.llm_file_pass import (
    NativeFile,
    accept_native,
    forget_turn_files,
    has_turn_files,
    native_ext,
    pass_base_url,
    remember_turn_files,
    splice_responses_body,
)


def test_accepts_pdf_docx_rejects_legacy_doc() -> None:
    assert native_ext("通知.pdf") == ".pdf"
    assert native_ext("表.xlsx") == ".xlsx"
    assert native_ext("计划.doc") == ".docx"
    assert native_ext("通知.docx") == ".docx"
    assert accept_native("计划.doc", b"OLE") is None
    converted = accept_native("计划.doc", b"PK\x03\x04ooxml")
    assert converted is not None
    assert converted.filename == "计划.docx"
    assert converted.ext == ".docx"
    assert accept_native("a.pdf", b"%PDF") is not None
    assert accept_native("a.pdf", b"") is None


def test_splice_adds_input_file_to_last_user() -> None:
    pdf = NativeFile(filename="通知.pdf", data=b"%PDF-1.4 hi")
    body = {
        "model": "gpt-5.6-sol",
        "input": [
            {"role": "user", "content": "这是什么"},
        ],
        "stream": True,
    }
    out = splice_responses_body(body, [pdf])
    content = out["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "这是什么"}
    assert content[1]["type"] == "input_file"
    assert content[1]["filename"] == "通知.pdf"
    assert content[1]["file_data"].startswith("data:application/pdf;base64,")
    assert "hi" not in (body["input"][0]["content"] if isinstance(body["input"][0]["content"], str) else "")
    # original body unchanged
    assert body["input"][0]["content"] == "这是什么"


def test_splice_string_input() -> None:
    pdf = NativeFile(filename="a.pdf", data=b"%PDF")
    out = splice_responses_body({"input": "hello"}, [pdf])
    assert out["input"][0]["role"] == "user"
    types = [p["type"] for p in out["input"][0]["content"]]
    assert types == ["input_text", "input_file"]


def test_remember_and_pass_url() -> None:
    pdf = NativeFile(filename="a.pdf", data=b"%PDF")
    remember_turn_files("run-1", [pdf])
    assert has_turn_files("run-1")
    assert "/internal/llm-pass/run-1/v1" in pass_base_url("run-1", port="18765")
    forget_turn_files("run-1")
    assert not has_turn_files("run-1")


def test_turn_files_key_is_exact_run_id() -> None:
    pdf = NativeFile(filename="a.pdf", data=b"%PDF")
    remember_turn_files("ledger-run", [pdf])
    assert has_turn_files("ledger-run")
    assert not has_turn_files("tp-abc")
    forget_turn_files("ledger-run")
