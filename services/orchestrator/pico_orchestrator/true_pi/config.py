"""True-Pi flags and paths (phase 1 shadow + phase 2 cutover).

Environment (documented · no secrets):
  PICO_TRUE_PI_SHADOW=1      — after hosted multi-step, run shadow + write diff
  PICO_TRUE_PI_BYPASS=1      — force true-pi for all multi-step (ops/test)
  PICO_TRUE_PI_DEFAULT=1     — production default multi-step = true Pi
  PICO_TRUE_PI_CANARY        — joint keys school:member,... or * (gray release)
  PICO_HOSTED_LOOP=1         — force hosted pi_runtime (rollback one-shot)
  PICO_TRUE_PI_BIN           — pi executable (default: pi)
  PICO_TRUE_PI_PACKAGE       — npm package pin
  PICO_TRUE_PI_SESSION_ROOT  — session dir parent
  PICO_TRUE_PI_HISTORY_N     — max history turns injected (default 10)
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from collections.abc import Collection
from pathlib import Path

TRUE_PI_SHADOW_ENV = "PICO_TRUE_PI_SHADOW"
TRUE_PI_BYPASS_ENV = "PICO_TRUE_PI_BYPASS"
TRUE_PI_DEFAULT_ENV = "PICO_TRUE_PI_DEFAULT"
TRUE_PI_CANARY_ENV = "PICO_TRUE_PI_CANARY"
HOSTED_LOOP_ENV = "PICO_HOSTED_LOOP"
TRUE_PI_BIN_ENV = "PICO_TRUE_PI_BIN"
TRUE_PI_PACKAGE_ENV = "PICO_TRUE_PI_PACKAGE"
TRUE_PI_SESSION_ROOT_ENV = "PICO_TRUE_PI_SESSION_ROOT"
TRUE_PI_HISTORY_N_ENV = "PICO_TRUE_PI_HISTORY_N"

# npm pin for deploy notes
PINNED_PI_PACKAGE = "@earendil-works/pi-coding-agent@0.84.4"
RUNTIME_LABEL = "pi-true"
HOSTED_RUNTIME_LABEL = "pi-agent"
