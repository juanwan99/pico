#!/usr/bin/env bash
# spawn-executor — RETIRED. Disk entry cut (EXPERIENCE §80 · TOOLING-CATALOG).
# Executor is this Grok sandbox. ECS only deploys.
# Archaeology: forbade /opt/pico /opt/edu-cloud; never Cursor cloud API keys.
set -euo pipefail

echo "[spawn-executor] RETIRED: 执行者是本窗 Grok 沙箱。不要 SSH 调 ECS grok。ECS 只部（ssh-ecs / prod-update）。入口已断。见 docs/EXPERIENCE.md §80 · docs/TOOLING-CATALOG.md" >&2
echo "ok=false"
echo "runtime=retired"
echo "use=grok-sandbox-exec"
exit 1
