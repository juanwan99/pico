#!/usr/bin/env python3
"""Print agent safety proof JSON for PR evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from pico_orchestrator.safety import assert_dangerous_tools_off


def main() -> int:
    proof = assert_dangerous_tools_off(ROOT / "services/orchestrator/agents/pico.yaml")
    print(json.dumps(proof, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
