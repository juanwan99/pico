#!/usr/bin/env bash
# Bootstrap Pico on Aliyun 轻量应用服务器 (宝塔 / 2C2G).
# Run ON THE SERVER as root (宝塔「命令助手」或 SSH):
#   curl -fsSL … | bash   OR   bash scripts/vps-bootstrap-aivia.sh
#
# Prerequisites you set outside this script:
#   1) DNS: pico.aivia.asia  A  →  139.196.147.40
#   2) 防火墙放行 80/443（轻量控制台已常见放行）
#   3) 可选：.env 里填 KIMI_API_KEY
set -euo pipefail

PUBLIC_IP="${PUBLIC_IP:-139.196.147.40}"
DOMAIN="${DOMAIN:-pico.aivia.asia}"
REPO_URL="${REPO_URL:-https://github.com/juanwan99/pico.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/pico}"

echo "[pico] domain=https://${DOMAIN}  expect-ip=${PUBLIC_IP}"
echo "[pico] app dir ${APP_DIR}"

# --- swap for 2G build ---
if [ ! -f /swapfile ]; then
  echo "[pico] creating 2G swap…"
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi
free -h || true

# --- docker ---
if ! command -v docker >/dev/null 2>&1; then
  echo "[pico] installing docker…"
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi
if ! docker compose version >/dev/null 2>&1; then
  # plugin fallback
  apt-get update -qq && apt-get install -y -qq docker-compose-plugin || true
fi
docker --version
docker compose version

# --- clone ---
mkdir -p "$(dirname "$APP_DIR")"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH" || true
fi
cd "$APP_DIR"

# --- env ---
if [ ! -f .env ]; then
  echo "[pico] BLOCKED: create .env from .env.production.example and fill secrets" >&2
  exit 2
fi
grep -Eq '^PICO_ENV=(production|prod)$' .env || {
  echo "[pico] BLOCKED: PICO_ENV must be production" >&2
  exit 2
}
# export for compose
export DOMAIN_CLIENT="https://${DOMAIN}"
export DOMAIN_SERVER="https://${DOMAIN}"

# LibreChat env (file used by compose env_file)
mkdir -p apps/librechat
if [ ! -f apps/librechat/.env ]; then
  if [ -f apps/librechat/.env.example ]; then
    cp apps/librechat/.env.example apps/librechat/.env
  else
    touch apps/librechat/.env
  fi
fi
# append/overwrite critical keys
python3 - <<PY || true
from pathlib import Path
p = Path("apps/librechat/.env")
text = p.read_text() if p.exists() else ""
keys = {
  "HOST": "0.0.0.0",
  "PORT": "3080",
  "DOMAIN_CLIENT": "https://${DOMAIN}",
  "DOMAIN_SERVER": "https://${DOMAIN}",
  "MONGO_URI": "mongodb://mongo:27017/LibreChat",
  "OPENAI_REVERSE_PROXY": "http://pico-api:18765/v1",
  "ENDPOINTS": "openAI",
  "OPENAI_MODELS": "kimi-k2.6,pico-agent",
  "APP_TITLE": "Pico",
  "ALLOW_REGISTRATION": "false",
  "ALLOW_UNVERIFIED_EMAIL_LOGIN": "false",
  "SEARCH": "false",
}
out = []
seen = set()
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
p.write_text("\\n".join(out) + "\\n")
print("[pico] librechat .env DOMAIN=https://${DOMAIN}")
PY

# --- build & up ---
echo "[pico] docker compose build (may take 10–20 min on 2G)…"
DOCKER_BUILDKIT=1 docker compose -f docker-compose.product.yml build
docker compose -f docker-compose.product.yml up -d
docker compose -f docker-compose.product.yml ps

# health
sleep 3
curl -sf -o /dev/null -w "local8080=%{http_code}\\n" http://127.0.0.1:8080/ || \
  curl -sf -o /dev/null -w "local8080=%{http_code}\\n" http://127.0.0.1:8080/login || true

cat <<EOF

[pico] containers up. Next (宝塔面板):

1) 网站 → 添加站点：${DOMAIN}
2) 反向代理 → 目标 http://127.0.0.1:8080
3) SSL → Let's Encrypt 申请并强制 HTTPS
4) DNS 已解析？  pico.aivia.asia  A  ${PUBLIC_IP}

生产默认关闭注册和 demo seed；管理员账号请按部署清单创建。

检查：
  docker compose -f ${APP_DIR}/docker-compose.product.yml logs -f --tail=100
EOF
