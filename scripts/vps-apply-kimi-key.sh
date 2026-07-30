#!/usr/bin/env bash
# Run ON the Aliyun VPS (宝塔命令助手 / SSH). Does not print the key.
# Usage:
#   export KIMI_API_KEY='sk-...'
#   bash /opt/pico/scripts/vps-apply-kimi-key.sh
set -euo pipefail
export PICO_ROOT="${PICO_ROOT:-/opt/pico}"
ROOT="$PICO_ROOT"
export KIMI_API_KEY="${KIMI_API_KEY:-${1:-}}"
if [ -z "${KIMI_API_KEY}" ]; then
  echo "[pico] KIMI_API_KEY missing — pass env or arg" >&2
  exit 1
fi
if [ ! -d "$ROOT" ]; then
  echo "[pico] $ROOT not found" >&2
  exit 1
fi
cd "$ROOT"

if [ ! -f .env ]; then
  if [ -f .env.example ]; then cp .env.example .env; else touch .env; fi
fi

python3 - <<'PY'
import os
from pathlib import Path
root = Path(os.environ.get("PICO_ROOT", "/opt/pico"))
key = os.environ["KIMI_API_KEY"]
path = root / ".env"
text = path.read_text() if path.exists() else ""
keys = {
    "KIMI_API_KEY": key,
    "KIMI_BASE_URL": os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
    "KIMI_MODEL": os.environ.get("KIMI_MODEL", "kimi-k2.6"),
    "PICO_CORS_ORIGINS": "https://pico.aivia.asia,http://127.0.0.1:8080,http://localhost:8080",
    "PICO_ENV": "production",
    "PICO_API_HOST": "127.0.0.1",
    "PICO_API_PORT": "18765",
}
out, seen = [], set()
for line in text.splitlines():
    if not line or line.lstrip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    k = line.split("=", 1)[0].strip()
    if k in keys:
        out.append(f"{k}={keys[k]}")
        seen.add(k)
    else:
        out.append(line)
for k, v in keys.items():
    if k not in seen:
        out.append(f"{k}={v}")
path.write_text("\n".join(out) + "\n")
print(f"[pico] wrote {path} KIMI_API_KEY=SET len={len(key)}")
PY

mkdir -p apps/librechat
if [ ! -f apps/librechat/.env ]; then
  [ -f apps/librechat/.env.example ] && cp apps/librechat/.env.example apps/librechat/.env || touch apps/librechat/.env
fi
python3 - <<'PY'
from pathlib import Path
p = Path("/opt/pico/apps/librechat/.env")
text = p.read_text() if p.exists() else ""
keys = {
    "HOST": "127.0.0.1",
    "PORT": "8080",
    "DOMAIN_CLIENT": "https://pico.aivia.asia",
    "DOMAIN_SERVER": "https://pico.aivia.asia",
    "MONGO_URI": "mongodb://127.0.0.1:27017/LibreChat",
    "OPENAI_REVERSE_PROXY": "http://127.0.0.1:18765/v1",
    "OPENAI_API_KEY": "pico-dev",
    "ENDPOINTS": "openAI",
    "OPENAI_MODELS": "moonshot-v1-8k,kimi-k2.6,pico-agent",
    "APP_TITLE": "Pico",
    "ALLOW_REGISTRATION": "true",
    "SEARCH": "false",
}
out, seen = [], set()
for line in text.splitlines():
    if not line or line.lstrip().startswith("#") or "=" not in line:
        out.append(line); continue
    k = line.split("=", 1)[0].strip()
    if k in keys:
        out.append(f"{k}={keys[k]}"); seen.add(k)
    else:
        out.append(line)
for k, v in keys.items():
    if k not in seen:
        out.append(f"{k}={v}")
p.write_text("\n".join(out) + "\n")
print("[pico] librechat DOMAIN=https://pico.aivia.asia")
PY

if [ -f docker-compose.host.yml ]; then
  docker compose -f docker-compose.host.yml up -d
else
  docker compose -f docker-compose.product.yml up -d || true
fi

sleep 3
echo "[pico] health:"
curl -sS --max-time 5 http://127.0.0.1:18765/health || true
echo

echo "[pico] S1 chat smoke:"
code=$(curl -sS --max-time 90 -o /tmp/pico-s1.json -w '%{http_code}' \
  -H 'Authorization: Bearer pico-dev' \
  -H 'Content-Type: application/json' \
  -H 'X-Pico-Membership-Id: demo' \
  -d '{"model":"kimi-k2.6","stream":false,"messages":[{"role":"user","content":"【Pico-User:demo】只回：演示OK"}]}' \
  http://127.0.0.1:18765/v1/chat/completions || echo ERR)
echo "  http=$code"
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/tmp/pico-s1.json')
if not p.exists():
    print('  no body'); raise SystemExit
raw=p.read_text()
try:
    data=json.loads(raw)
except Exception as e:
    print('  body not json', e, raw[:240]); raise SystemExit
if 'error' in data:
    print('  error:', str(data.get('error'))[:240])
else:
    ch=(data.get('choices') or [{}])[0]
    msg=(ch.get('message') or {}).get('content') or ch.get('text') or ''
    print('  reply_snippet:', str(msg)[:160].replace('\n',' '))
PY

echo "[pico] loopback UI:"
curl -sS -o /dev/null -w '  8080_login=%{http_code}\n' --max-time 5 http://127.0.0.1:8080/login || true
echo "[pico] done — open https://pico.aivia.asia/login and chat"
