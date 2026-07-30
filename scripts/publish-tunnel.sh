#!/usr/bin/env bash
# Publish product UI (:8080) via Cloudflare quick tunnel → public HTTPS URL for the owner.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PICO_PUBLIC_PORT:-8080}"
LOG="${PICO_TUNNEL_LOG:-/tmp/cloudflared-8080.log}"
BIN="${CLOUDFLARED_BIN:-/tmp/cloudflared}"

if ! curl -sf -o /dev/null --max-time 3 "http://127.0.0.1:${PORT}/login"; then
  echo "[tunnel] product :${PORT} not up — run startup.sh / run-product.sh first" >&2
  exit 1
fi

if [ ! -x "$BIN" ]; then
  echo "[tunnel] downloading cloudflared…"
  curl -sL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" -o "$BIN"
  chmod +x "$BIN"
fi

# stop previous quick tunnel (best-effort)
if [ -f /tmp/cloudflared-8080.pid ]; then
  kill "$(cat /tmp/cloudflared-8080.pid)" 2>/dev/null || true
fi

: >"$LOG"
nohup "$BIN" tunnel --url "http://127.0.0.1:${PORT}" --no-autoupdate >>"$LOG" 2>&1 &
echo $! >/tmp/cloudflared-8080.pid

URL=""
for _ in $(seq 1 45); do
  URL=$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$LOG" | head -1 || true)
  if [ -n "$URL" ]; then
    break
  fi
  sleep 1
done

if [ -z "$URL" ]; then
  echo "[tunnel] failed to get URL — see $LOG" >&2
  exit 1
fi

echo "$URL" | tee /tmp/pico-public-url.txt
echo "[tunnel] public URL: $URL"
echo "[tunnel] set LibreChat DOMAIN_CLIENT and DOMAIN_SERVER to this URL, then restart backend."
echo "[tunnel] demo login: teacher@example.com / pico-demo-123"
