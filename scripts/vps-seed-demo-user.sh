#!/usr/bin/env bash
# Seed LibreChat demo user on Aliyun VPS. Run ON the server (宝塔命令助手).
#   bash /opt/pico/scripts/vps-seed-demo-user.sh
#
# Demo: teacher@example.com / pico-demo-123
# Does not print secrets beyond the known demo password (already public in DEMO.md).
set -euo pipefail
ROOT="${PICO_ROOT:-/opt/pico}"
EMAIL="${DEMO_EMAIL:-teacher@example.com}"
PASS="${DEMO_PASSWORD:-pico-demo-123}"
NAME="${DEMO_NAME:-Pico Teacher}"
USER="${DEMO_USERNAME:-teacher}"
LC_URL="${LIBRECHAT_URL:-http://127.0.0.1:8080}"

cd "$ROOT"

# 1) Ensure login works without mailbox (no SMTP on VPS)
for f in apps/librechat/.env .env; do
  [ -f "$f" ] || continue
  if grep -q '^ALLOW_UNVERIFIED_EMAIL_LOGIN=' "$f"; then
    sed -i 's|^ALLOW_UNVERIFIED_EMAIL_LOGIN=.*|ALLOW_UNVERIFIED_EMAIL_LOGIN=true|' "$f"
  else
    echo 'ALLOW_UNVERIFIED_EMAIL_LOGIN=true' >>"$f"
  fi
  if grep -q '^ALLOW_REGISTRATION=' "$f"; then
    sed -i 's|^ALLOW_REGISTRATION=.*|ALLOW_REGISTRATION=true|' "$f"
  else
    echo 'ALLOW_REGISTRATION=true' >>"$f"
  fi
done
# also force into compose env on next up — write librechat env hard
python3 - <<'PY'
from pathlib import Path
p = Path("apps/librechat/.env")
p.parent.mkdir(parents=True, exist_ok=True)
text = p.read_text() if p.exists() else ""
keys = {
    "ALLOW_UNVERIFIED_EMAIL_LOGIN": "true",
    "ALLOW_REGISTRATION": "true",
    "ALLOW_EMAIL_LOGIN": "true",
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
print("[pico] librechat .env registration/unverified flags set")
PY

# 2) Recreate librechat so env reloads
if [ -f docker-compose.host.yml ]; then
  docker compose -f docker-compose.host.yml up -d --force-recreate librechat || \
    docker compose -f docker-compose.host.yml up -d librechat
fi
echo "[pico] waiting for LibreChat..."
for i in $(seq 1 60); do
  if curl -sf -o /dev/null --max-time 2 "$LC_URL/login" || curl -sf -o /dev/null --max-time 2 "$LC_URL/"; then
    break
  fi
  sleep 1
done

# 3) Register (idempotent-ish)
echo "[pico] register attempt..."
reg=$(curl -sS --max-time 30 -o /tmp/pico-reg.json -w '%{http_code}' \
  -X POST "$LC_URL/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"$NAME\",\"username\":\"$USER\",\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"confirm_password\":\"$PASS\"}" || echo ERR)
echo "  register_http=$reg body=$(head -c 200 /tmp/pico-reg.json 2>/dev/null || true)"

# 4) Force emailVerified in Mongo if user exists
echo "[pico] ensure emailVerified=true in Mongo..."
docker exec pico-mongo-1 mongosh --quiet LibreChat --eval "
  const r = db.users.updateMany(
    { email: '$EMAIL' },
    { \$set: { emailVerified: true }, \$unset: { expiresAt: '' } }
  );
  printjson(r);
  const u = db.users.findOne({ email: '$EMAIL' }, { email:1, emailVerified:1, username:1, name:1 });
  printjson(u);
" 2>/dev/null || docker exec pico-mongo-1 mongo --quiet LibreChat --eval "
  db.users.updateMany({ email: '$EMAIL' }, { \$set: { emailVerified: true } });
  printjson(db.users.findOne({ email: '$EMAIL' }, { email:1, emailVerified:1 }));
" 2>/dev/null || echo "  mongo exec skipped (container name may differ — run: docker ps | grep mongo)"

# 5) If still no user, try docker exec create-user inside librechat
login_code=$(curl -sS --max-time 20 -o /tmp/pico-login.json -w '%{http_code}' \
  -X POST "$LC_URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" || echo ERR)
echo "[pico] login_http=$login_code body=$(head -c 180 /tmp/pico-login.json 2>/dev/null || true)"

if [ "$login_code" != "200" ]; then
  echo "[pico] login still failing — try create-user in container..."
  # discover librechat container
  LC_CID=$(docker ps --format '{{.Names}}' | grep -E 'librechat' | head -1 || true)
  if [ -n "$LC_CID" ]; then
    docker exec -w /app "$LC_CID" node config/create-user.js \
      "$EMAIL" "$NAME" "$USER" "$PASS" --email-verified=true \
      || docker exec -w /app "$LC_CID" npm run create-user -- \
      "$EMAIL" "$NAME" "$USER" "$PASS" --email-verified=true \
      || true
    docker exec pico-mongo-1 mongosh --quiet LibreChat --eval \
      "db.users.updateMany({email:'$EMAIL'},{\$set:{emailVerified:true}})" 2>/dev/null || true
    login_code=$(curl -sS --max-time 20 -o /tmp/pico-login.json -w '%{http_code}' \
      -X POST "$LC_URL/api/auth/login" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" || echo ERR)
    echo "[pico] login_http_retry=$login_code body=$(head -c 180 /tmp/pico-login.json 2>/dev/null || true)"
  fi
fi

if [ "$login_code" = "200" ]; then
  echo "[pico] DEMO_LOGIN=OK  email=$EMAIL"
  echo "[pico] open https://pico.aivia.asia/login and sign in"
else
  echo "[pico] DEMO_LOGIN=FAIL — check: docker compose -f docker-compose.host.yml logs --tail=50 librechat"
  echo "[pico] list users: docker exec pico-mongo-1 mongosh LibreChat --eval 'db.users.find({}, {email:1,emailVerified:1}).toArray()'"
  exit 1
fi
