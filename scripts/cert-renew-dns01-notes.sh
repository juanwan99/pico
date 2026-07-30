#!/usr/bin/env bash
# Notes + helper for renewing pico.aivia.asia Let's Encrypt cert (DNS-01).
# Manual DNS-01 was used for first issue; auto-renew needs Aliyun DNS API or CF.
#
# Usage on VPS (interactive / with DNS API later):
#   bash scripts/cert-renew-dns01-notes.sh status
#   bash scripts/cert-renew-dns01-notes.sh check
set -euo pipefail
DOMAIN="${DOMAIN:-pico.aivia.asia}"
LIVE="/etc/letsencrypt/live/${DOMAIN}"

cmd="${1:-status}"
case "$cmd" in
  status)
    if [ -f "$LIVE/fullchain.pem" ]; then
      echo "[cert] path $LIVE"
      openssl x509 -in "$LIVE/fullchain.pem" -noout -dates -subject 2>/dev/null || true
    else
      echo "[cert] missing $LIVE — issue first with certbot certonly --manual --preferred-challenges dns -d $DOMAIN"
    fi
    ;;
  check)
    echo "[cert] HTTPS probe (local SNI may need public path)"
    echo | openssl s_client -connect 127.0.0.1:443 -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null || \
      echo "[cert] cannot read local 443 — check nginx + cert files"
    ;;
  remind)
    cat <<EOF
[cert] Renewal plan for $DOMAIN (DNS-01)

Current: manual TXT _acme-challenge.$DOMAIN (Codex issued; ~90 day LE)

Options:
  A) Aliyun DNS API + certbot dns plugin (recommended for 轻量)
     - create RAM access key with DNS edit only
     - certbot with aliyun DNS plugin or acme.sh --dns dns_ali
  B) Move zone to Cloudflare + certbot dns-cloudflare
  C) Calendar reminder 14 days before expiry + re-run DNS-01

After renew:
  nginx -t && nginx -s reload

Do NOT delete /etc/letsencrypt without backup.
EOF
    ;;
  *)
    echo "usage: $0 status|check|remind" >&2
    exit 2
    ;;
esac
