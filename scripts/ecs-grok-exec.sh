#!/usr/bin/env bash
# ecs-grok-exec — RETIRED. Disk entry cut (EXPERIENCE §80 · TOOLING-CATALOG).
# Executor is the owner's Grok sandbox. ECS only deploys.
# Archaeology: forbade cwd /opt/pico /opt/edu-cloud; used tmux; never reached.
set -euo pipefail

echo "[ecs-grok-exec] RETIRED: 执行者是本窗 Grok 沙箱。不要在 ECS 起 grok。ECS 只部。入口已断。见 docs/EXPERIENCE.md §80 · docs/TOOLING-CATALOG.md" >&2
echo "ok=false"
echo "runtime=retired"
echo "use=grok-sandbox-exec"
exit 1
