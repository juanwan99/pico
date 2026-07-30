#!/usr/bin/env bash
# One-shot: pull seed hooks + recreate LibreChat + verify demo login.
# Run ON Aliyun VPS (宝塔命令助手):
#   bash /opt/pico/scripts/vps-fix-login.sh
set -euo pipefail
ROOT="${PICO_ROOT:-/opt/pico}"
EMAIL="${DEMO_EMAIL:-teacher@example.com}"
PASS="${DEMO_PASSWORD:-pico-demo-123}"
cd "$ROOT"

echo "[pico] pull branch…"
git fetch origin grok/pico-preview-librechat-p0 2>/dev/null || true
git checkout grok/pico-preview-librechat-p0 2>/dev/null || true
git pull --ff-only origin grok/pico-preview-librechat-p0 || true
git rev-parse --short HEAD || true

# ensure flags in librechat env file
mkdir -p apps/librechat
touch apps/librechat/.env
python3 - <<'PY'
from pathlib import Path
p = Path("apps/librechat/.env")
text = p.read_text() if p.exists() else ""
keys = {
    "ALLOW_REGISTRATION": "true",
    "ALLOW_EMAIL_LOGIN": "true",
    "ALLOW_UNVERIFIED_EMAIL_LOGIN": "true",
    "PICO_SEED_DEMO_USER": "true",
    "PICO_DEMO_EMAIL": "teacher@example.com",
    "PICO_DEMO_PASSWORD": "pico-demo-123",
    "PICO_DEMO_USERNAME": "teacher",
    "PICO_DEMO_NAME": "Pico Teacher",
    "DOMAIN_CLIENT": "https://pico.aivia.asia",
    "DOMAIN_SERVER": "https://pico.aivia.asia",
    "HOST": "127.0.0.1",
    "PORT": "8080",
    "MONGO_URI": "mongodb://127.0.0.1:27017/LibreChat",
    "OPENAI_REVERSE_PROXY": "http://127.0.0.1:18765/v1",
    "OPENAI_API_KEY": "pico-dev",
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
print("[pico] librechat .env updated")
PY

echo "[pico] recreate librechat (seed mounts + env)…"
docker compose -f docker-compose.host.yml up -d --force-recreate librechat

echo "[pico] wait ready…"
for i in $(seq 1 90); do
  if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/login || curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
    echo "  ready after ${i}s"
    break
  fi
  sleep 1
done
sleep 2

# API seed fallback (if boot seed missed)
curl -sS --max-time 20 -o /tmp/pico-reg.json -w "register=%{http_code}\n" \
  -X POST http://127.0.0.1:8080/api/auth/register \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"Pico Teacher\",\"username\":\"teacher\",\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"confirm_password\":\"$PASS\"}" || true
head -c 160 /tmp/pico-reg.json 2>/dev/null; echo

# force verified in mongo
MONGO=$(docker ps --format '{{.Names}}' | grep -E 'mongo' | head -1 || true)
if [ -n "$MONGO" ]; then
  docker exec "$MONGO" mongosh --quiet LibreChat --eval \
    "db.users.updateMany({email:'$EMAIL'},{\$set:{emailVerified:true},\$unset:{expiresAt:''}}); printjson(db.users.findOne({email:'$EMAIL'},{email:1,emailVerified:1,username:1}))" \
    2>/dev/null || true
fi

# create-user fallback inside container
if ! curl -sf --max-time 15 -X POST http://127.0.0.1:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" -o /tmp/pico-login.json; then
  LC=$(docker ps --format '{{.Names}}' | grep -E 'librechat' | head -1 || true)
  if [ -n "$LC" ]; then
    echo "[pico] create-user fallback in $LC"
    docker exec -w /app "$LC" node config/create-user.js \
      "$EMAIL" "Pico Teacher" teacher "$PASS" --email-verified=true || true
  fi
fi

code=$(curl -sS --max-time 20 -o /tmp/pico-login.json -w '%{http_code}' \
  -X POST http://127.0.0.1:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" || echo ERR)
echo "login_http=$code body=$(head -c 120 /tmp/pico-login.json 2>/dev/null || true)"
if [ "$code" = "200" ]; then
  echo "[pico] DEMO_LOGIN=OK"
  echo "[pico] → https://pico.aivia.asia/login  $EMAIL / $PASS"
  exit 0
fi
echo "[pico] DEMO_LOGIN=FAIL"
docker compose -f docker-compose.host.yml logs --tail=40 librechat || true
exit 1
