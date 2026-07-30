#!/usr/bin/env bash
# Replace Workbox SW with a self-destroying SW after client build.
# Stale LibreChat SW/caches are a common cause of blank shells behind proxies.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SW="$ROOT/apps/librechat/client/dist/sw.js"
if [ ! -f "$SW" ]; then
  echo "[pico] no dist/sw.js yet — skip"
  exit 0
fi
cat >"$SW" <<'EOF'
/* Pico self-destroying service worker — do not cache shell */
self.addEventListener('install', function (e) { self.skipWaiting(); });
self.addEventListener('activate', function (e) {
  e.waitUntil((async function () {
    try {
      var keys = await caches.keys();
      await Promise.all(keys.map(function (k) { return caches.delete(k); }));
    } catch (err) {}
    try { await self.registration.unregister(); } catch (err) {}
    try {
      var clientsList = await self.clients.matchAll({ type: 'window' });
      clientsList.forEach(function (c) { try { c.navigate(c.url); } catch (e) {} });
    } catch (err) {}
  })());
});
// no fetch handler → network default
EOF
echo "[pico] wrote self-destroying sw.js"
