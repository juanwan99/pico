#!/usr/bin/env bash
# Apply Pico LibreChat-only vhost + owner Sub2API console on workbench.aivia.asia.
# ECS as ops. Writes nginx via docker (root), then sudo -n systemctl reload nginx.
# Pico origin must stay LibreChat. Sub2API stays on 127.0.0.1:8081.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PICO_SRC="$ROOT/deploy/nginx/pico.aivia.asia.conf"
WB_SRC="$ROOT/deploy/nginx/workbench.aivia.asia.conf"

if ! command -v docker >/dev/null; then
  echo "docker required" >&2
  exit 2
fi
[[ -f "$PICO_SRC" && -f "$WB_SRC" ]] || { echo "missing nginx snippets" >&2; exit 2; }
if grep -E 'pico_sub2api_door|127.0.0.1:8081|13080|dify' "$PICO_SRC"; then
  echo "refuse: pico vhost must stay LibreChat-only" >&2
  exit 2
fi
if ! grep -q '127.0.0.1:8081' "$WB_SRC"; then
  echo "refuse: workbench must proxy Sub2API loopback 8081" >&2
  exit 2
fi
if grep -E '13080|dify_workbench' "$WB_SRC"; then
  echo "refuse: workbench must not revive Dify" >&2
  exit 2
fi

install_conf() {
  local src="$1"
  local dest_name="$2"
  local bak="${dest_name}.bak-gateway-${STAMP}"
  echo "[gateway-nginx] install ${dest_name} bak=${bak}"
  docker run --rm \
    -v /etc/nginx/conf.d:/conf \
    -v "$src":/src/incoming.conf:ro \
    alpine:3.20 \
    sh -c "cp /conf/${dest_name} /conf/${bak} && cp /src/incoming.conf /conf/${dest_name}"
}

restore_conf() {
  local dest_name="$1"
  local bak="${dest_name}.bak-gateway-${STAMP}"
  echo "[gateway-nginx] restore ${bak}" >&2
  docker run --rm -v /etc/nginx/conf.d:/conf alpine:3.20 \
    sh -c "cp /conf/${bak} /conf/${dest_name}"
}

install_conf "$PICO_SRC" "pico.aivia.asia.conf"
install_conf "$WB_SRC" "workbench.aivia.asia.conf"

restore_all() {
  restore_conf "pico.aivia.asia.conf"
  restore_conf "workbench.aivia.asia.conf"
  sudo -n /usr/bin/systemctl reload nginx || true
}

if ! sudo -n /usr/bin/systemctl reload nginx; then
  restore_all
  exit 1
fi

tip_ok=0
for i in 1 2 3 4 5 6; do
  sleep 1
  if curl -fsS --max-time 8 https://pico.aivia.asia/api/pico/tip | grep -q 'pico-api'; then
    tip_ok=1
    break
  fi
done
if [[ "$tip_ok" -ne 1 ]]; then
  restore_all
  exit 1
fi
if curl -sS --max-time 8 https://pico.aivia.asia/ | grep -q 'Sub2API'; then
  echo "[gateway-nginx] pico origin must not serve Sub2API" >&2
  restore_all
  exit 1
fi
wb_health="$(curl -fsS --max-time 8 https://workbench.aivia.asia/health || true)"
if ! grep -q '"status":"ok"' <<<"$wb_health"; then
  echo "[gateway-nginx] workbench /health must be Sub2API ok, got: ${wb_health}" >&2
  restore_all
  exit 1
fi
if ! curl -sS --max-time 8 https://workbench.aivia.asia/ | grep -q 'Sub2API'; then
  echo "[gateway-nginx] workbench origin must serve Sub2API" >&2
  restore_all
  exit 1
fi
echo "[gateway-nginx] OK"
