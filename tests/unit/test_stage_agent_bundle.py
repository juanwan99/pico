from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.kimi_runtime import _stage_agent_bundle


def test_stage_agent_bundle_rewrites_system_prompt_path(tmp_path: Path) -> None:
    staged = _stage_agent_bundle(tmp_path)
    assert staged.is_file()
    text = staged.read_text(encoding="utf-8")
    assert "system_prompt_path:" in text
    assert "system.md" in text
    assert (tmp_path / "agent" / "system.md").is_file()
