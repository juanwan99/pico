#!/usr/bin/env bash
# Apply Sub2API HTTPS doors on ECS nginx.
# 1) pico.aivia.asia cookie-switch (public product door)
# 2) workbench.aivia.asia SNI → loopback (existing cert; DNS may still point elsewhere)
# Must run on ECS as ops. Writes conf via docker (root) then reloads nginx.
# Does not print secrets. Does not bind Sub2API off loopback.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PICO_SRC="$ROOT/deploy/nginx/pico.aivia.asia.conf"
WB_SRC="$ROOT/deploy/nginx/workbench.aivia.asia.sub2api.conf"

if ! command -v docker >/dev/null; then
  echo "docker required to write nginx conf" >&2
  exit 2
fi

check_src() {
  local src="$1"
  [[ -f "$src" ]] || { echo "missing $src" >&2; exit 2; }
  grep -q '127.0.0.1:8081' "$src" || { echo "refuse: $src must pin 127.0.0.1:8081" >&2; exit 2; }
  if grep -E '0\.0\.0\.0:8081|:22' "$src"; then
    echo "refuse: $src must not publish 8081/22" >&2
    exit 2
  fi
}

check_src "$PICO_SRC"
check_src "$WB_SRC"

install_conf() {
  local src="$1"
  local dest_name="$2"
  local bak="${dest_name}.bak-sub2api-${STAMP}"
  echo "[sub2api-edge] install ${dest_name} bak=${bak}"
  docker run --rm \
    -v /etc/nginx/conf.d:/conf \
    -v "$src":/src/incoming.conf:ro \
    alpine:3.20 \
    sh -c "cp /conf/${dest_name} /conf/${bak} && cp /src/incoming.conf /conf/${dest_name} && grep -q '127.0.0.1:8081' /conf/${dest_name}"
}

restore_conf() {
  local dest_name="$1"
  local bak="${dest_name}.bak-sub2api-${STAMP}"
  echo "[sub2api-edge] restore ${bak} -> ${dest_name}" >&2
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

echo "[sub2api-edge] reload"
if ! sudo -n /usr/bin/systemctl reload nginx; then
  restore_all
  exit 1
fi

echo "[sub2api-edge] pico tip (no door cookie)"
tip_ok=0
for i in 1 2 3 4 5 6; do
  sleep 1
  if curl -fsS --max-time 8 https://pico.aivia.asia/api/pico/tip | grep -q 'pico-api'; then
    tip_ok=1
    break
  fi
  echo "[sub2api-edge] tip retry $i" >&2
done
if [[ "$tip_ok" -ne 1 ]]; then
  restore_all
  exit 1
fi

echo "[sub2api-edge] pico door cookie -> sub2api /health"
COOKIES="$(mktemp)"
cleanup() { rm -f "$COOKIES"; }
trap cleanup EXIT
curl -fsS --max-time 8 -c "$COOKIES" -o /dev/null https://pico.aivia.asia/accounts/enter-sub2api
if ! grep -q pico_sub2api_door "$COOKIES"; then
  echo "[sub2api-edge] enter cookie missing" >&2
  restore_all
  exit 1
fi
if ! curl -fsS --max-time 8 -b "$COOKIES" https://pico.aivia.asia/health | grep -q '"status":"ok"'; then
  echo "[sub2api-edge] door health failed" >&2
  restore_all
  exit 1
fi

echo "[sub2api-edge] exit door"
curl -fsS --max-time 8 -c "$COOKIES" -b "$COOKIES" -o /dev/null https://pico.aivia.asia/accounts/exit-sub2api
if ! curl -fsS --max-time 8 https://pico.aivia.asia/api/pico/tip | grep -q 'pico-api'; then
  echo "[sub2api-edge] tip after exit failed" >&2
  restore_all
  exit 1
fi

echo "[sub2api-edge] OK"
