#!/usr/bin/env bash
# H · public 502 long-window sampler (no secrets).
# Samples public /login and /health at a fixed interval; writes a result table.
#
# Usage:
#   bash scripts/public-502-monitor.sh              # default: 20 samples × 45s (~15min)
#   SAMPLES=30 INTERVAL_S=30 bash scripts/public-502-monitor.sh
#   ONCE=1 bash scripts/public-502-monitor.sh       # single sample
set -euo pipefail

BASE_URL="${BASE_URL:-https://pico.aivia.asia}"
SAMPLES="${SAMPLES:-20}"
INTERVAL_S="${INTERVAL_S:-45}"
ONCE="${ONCE:-0}"
OUT_DIR="${OUT_DIR:-/tmp/pico-502-monitor}"
mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CSV="$OUT_DIR/samples-${STAMP}.csv"
SUMMARY="$OUT_DIR/summary-${STAMP}.txt"

if [[ "$ONCE" == "1" ]]; then
  SAMPLES=1
fi

if ! [[ "$SAMPLES" =~ ^[0-9]+$ ]] || [[ "$SAMPLES" -lt 1 ]]; then
  echo "[pico] ERROR: SAMPLES must be positive integer" >&2
  exit 2
fi

echo "ts_utc,path,http_code,time_total_s,err" >"$CSV"
ok_login=0
ok_health=0
fail_login=0
fail_health=0
codes_login=()
codes_health=()

sample_one() {
  local path="$1"
  local out code t err
  err=""
  # shellcheck disable=SC2034
  out="$(curl -sS -o /dev/null -w '%{http_code} %{time_total}' --max-time 12 "${BASE_URL}${path}" 2>/tmp/pico-502-curl.err || true)"
  if [[ -s /tmp/pico-502-curl.err ]]; then
    err="$(tr '\n' ' ' </tmp/pico-502-curl.err | head -c 80)"
  fi
  code="$(echo "$out" | awk '{print $1}')"
  t="$(echo "$out" | awk '{print $2}')"
  if [[ -z "$code" ]]; then
    code="000"
    t="0"
  fi
  printf '%s,%s,%s,%s,%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$path" "$code" "$t" "$err" >>"$CSV"
  echo "$code"
}

echo "[pico] 502 monitor BASE=$BASE_URL samples=$SAMPLES interval=${INTERVAL_S}s -> $CSV"

for ((i = 1; i <= SAMPLES; i++)); do
  c_login="$(sample_one /login)"
  c_health="$(sample_one /health)"
  codes_login+=("$c_login")
  codes_health+=("$c_health")
  if [[ "$c_login" =~ ^[23] ]]; then
    ok_login=$((ok_login + 1))
  else
    fail_login=$((fail_login + 1))
  fi
  if [[ "$c_health" =~ ^[23] ]]; then
    ok_health=$((ok_health + 1))
  else
    fail_health=$((fail_health + 1))
  fi
  echo "[pico] sample $i/$SAMPLES login=$c_login health=$c_health"
  if [[ "$i" -lt "$SAMPLES" ]]; then
    sleep "$INTERVAL_S"
  fi
done

{
  echo "public-502-monitor summary"
  echo "base=$BASE_URL"
  echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "samples=$SAMPLES interval_s=$INTERVAL_S"
  echo "login_ok=$ok_login login_fail=$fail_login"
  echo "health_ok=$ok_health health_fail=$fail_health"
  echo "login_codes=${codes_login[*]}"
  echo "health_codes=${codes_health[*]}"
  echo "csv=$CSV"
  if [[ "$fail_login" -eq 0 && "$fail_health" -eq 0 ]]; then
    echo "verdict=NO_502_IN_WINDOW"
  else
    echo "verdict=HAS_NON_2XX"
  fi
} | tee "$SUMMARY"
