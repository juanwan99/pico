from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "kb-judge.py"
_spec = importlib.util.spec_from_file_location("kb_judge", SCRIPT)
assert _spec is not None and _spec.loader is not None
kj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kj)


def test_pick_items_stratifies_and_caps() -> None:
    items = [{"kind": "pdf", "id": i} for i in range(10)] + [
        {"kind": "xlsx", "id": 100 + i} for i in range(10)
    ]
    picked = kj.pick_items(items, 8, seed=7)
    assert len(picked) == 8
    kinds = {row["kind"] for row in picked}
    assert kinds == {"pdf", "xlsx"}


def test_render_table_has_judge_columns() -> None:
    md = kj.render_table(
        [
            {
                "question": "开学哪天",
                "hit_passage": "3月1日开学",
                "model_answer": "",
                "answer_quote": "春季学期于3月1日开学",
                "human_judge": "",
                "channel": "search_only",
            }
        ]
    )
    assert "问" in md
    assert "命中段" in md
    assert "模型答" in md
    assert "参考原句" in md
    assert "人判" in md
    assert "开学哪天" in md


def test_channel_red_detects_overload() -> None:
    assert kj.is_channel_red("http_503") is True
    assert kj.is_channel_red("overloaded") is True
    assert kj.is_channel_red("search_only") is False
