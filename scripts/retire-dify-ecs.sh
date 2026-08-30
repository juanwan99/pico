#!/usr/bin/env bash
# Retire Dify / aivia-workbench runtime on the shared ECS.
# Does not touch pico, new-api, or sub2api. Does not print secret values.
set -euo pipefail

echo "[retire-dify] stop user units"
systemctl --user stop aivia-edge-tunnel.service 2>/dev/null || true
systemctl --user disable aivia-edge-tunnel.service 2>/dev/null || true
systemctl --user stop aivia-bridge.service 2>/dev/null || true
systemctl --user disable aivia-bridge.service 2>/dev/null || true

echo "[retire-dify] stop container"
if docker ps -a --format '{{.Names}}' | grep -qx aivia-bridge; then
  docker stop aivia-bridge >/dev/null || true
  docker rm aivia-bridge >/dev/null || true
fi

echo "[retire-dify] archive secrets (names only)"
mkdir -p /home/ops/.secrets/retired-dify
chmod 700 /home/ops/.secrets/retired-dify
shopt -s nullglob
for f in /home/ops/.secrets/dify-*.env; do
  mv "$f" /home/ops/.secrets/retired-dify/
done

if [[ -d /home/ops/aivia-workbench && ! -e /home/ops/retired-aivia-workbench ]]; then
  mv /home/ops/aivia-workbench /home/ops/retired-aivia-workbench
fi

echo "[retire-dify] leftover check"
systemctl --user is-active aivia-edge-tunnel.service && echo "WARN tunnel still active" || echo "tunnel: inactive"
docker ps -a --format '{{.Names}}' | grep -iE 'dify|aivia-bridge' && echo "WARN container still present" || echo "bridge: gone"
ss -tlnp | grep 13080 && echo "WARN 13080 still listening" || echo "13080: none"
echo "[retire-dify] OK"
