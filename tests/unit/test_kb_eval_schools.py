from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "kb-eval.py"
_spec = importlib.util.spec_from_file_location("kb_eval", SCRIPT)
assert _spec is not None and _spec.loader is not None
kb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kb)


def test_schools_none_is_wuxiao(monkeypatch, capsys) -> None:
    monkeypatch.setattr(kb, "meili_school_counts", dict)
    rc = kb.cmd_schools(argparse.Namespace(school=""))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "无校"
    assert out["schools"] == 0


def test_schools_missing_named_is_wuxiao(monkeypatch, capsys) -> None:
    monkeypatch.setattr(kb, "meili_school_counts", lambda: {"school-a": 12})
    rc = kb.cmd_schools(argparse.Namespace(school="school-b"))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "无校"
    assert out["docs"] == 0
