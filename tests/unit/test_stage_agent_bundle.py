import pytest

pytest.importorskip("kimi_agent_sdk")
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.kimi_runtime import _stage_agent_bundle


def test_stage_agent_bundle_at_work_dir_root(tmp_path: Path) -> None:
    staged = _stage_agent_bundle(tmp_path)
    assert staged == (tmp_path / "pico-kimi-runtime.yaml").resolve()
    assert staged.is_file()
    assert (tmp_path / "system.md").is_file()
    assert (tmp_path / "agent" / "system.md").is_file()
    text = staged.read_text(encoding="utf-8")
    assert "system_prompt_path: ./system.md" in text
