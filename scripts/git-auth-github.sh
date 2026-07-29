#!/usr/bin/env bash
# Refresh non-interactive git auth for github.com using `gh auth token`.
set -euo pipefail
if ! command -v gh >/dev/null; then
  echo "gh not found" >&2
  exit 1
fi
TOKEN=$(gh auth token)
if [ -z "$TOKEN" ]; then
  echo "gh auth token empty — re-login / inject GH_TOKEN" >&2
  exit 1
fi
BASIC=$(printf 'x-access-token:%s' "$TOKEN" | base64 -w0 2>/dev/null || printf 'x-access-token:%s' "$TOKEN" | base64)
git config --global http.https://github.com/.extraheader "Authorization: Basic ${BASIC}"
git config --global credential.helper ''
export GH_TOKEN="$TOKEN"
echo "git↔github.com auth refreshed (token_len=${#TOKEN})"
# smoke
git ls-remote "https://github.com/juanwan99/pico.git" HEAD >/dev/null
echo "smoke ok"
