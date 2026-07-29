#!/bin/sh
# Grok sandbox revive entry — product stack for Live Preview
set -eu
cd /workspace

if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/login; then
  ASSET=$(grep -oE 'assets/index\.[A-Za-z0-9_-]+\.js' /workspace/apps/librechat/client/dist/index.html 2>/dev/null | head -1 || true)
  if [ -n "$ASSET" ] && curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:8080/$ASSET"; then
    curl -sf -o /dev/null --max-time 2 -X POST http://127.0.0.1:6015/__control/target \
      -H 'Content-Type: application/json' -d '{"port":8080}' || true
    exit 0
  fi
  # HTML up but main JS missing — fall through to restart product stack
fi

# Mongo portable
if ! python3 -c "import socket;s=socket.create_connection(('127.0.0.1',27017),1);s.close()" 2>/dev/null; then
  if [ -x /tmp/mongodb/bin/mongod ]; then
    mkdir -p /tmp/mongo-data /tmp/mongo-log
    /tmp/mongodb/bin/mongod --dbpath /tmp/mongo-data --bind_ip 127.0.0.1 --port 27017 \
      --fork --logpath /tmp/mongo-log/mongod.log || true
  fi
fi

# Unset proxy vars that break LibreChat undici
unset PROXY HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true

sh /workspace/scripts/run-product.sh >>/tmp/app-startup.log 2>&1 || true

# Pin Live Preview to product UI
curl -sf -o /dev/null --max-time 2 -X POST http://127.0.0.1:6015/__control/target \
  -H 'Content-Type: application/json' -d '{"port":8080}' || true

# Background pin keep-alive
if [ -x /workspace/scripts/pin-preview-8080.sh ]; then
  if ! pgrep -f 'pin-preview-8080' >/dev/null 2>&1; then
    nohup /workspace/scripts/pin-preview-8080.sh >>/tmp/pin-preview.log 2>&1 &
  fi
fi
