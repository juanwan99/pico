#!/usr/bin/env bash
# Pico OneFlow status helper — NOT a second source of truth.
# Prints re-derivable git/CI/health hints. Authority remains GitHub PR/SHA/CI.
set -euo pipefail

SHA="${1:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Pico OneFlow status (advisory) ==="
echo "repo: $(git remote get-url origin 2>/dev/null || echo unknown)"
echo "branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
FULL="$(git rev-parse HEAD 2>/dev/null || true)"
echo "HEAD: ${FULL:-unknown}"
if [[ -n "$SHA" ]]; then
  echo "query: $SHA"
  git cat-file -t "$SHA" 2>/dev/null || echo "WARN: sha not in local repo"
fi

if command -v gh >/dev/null 2>&1; then
  echo "--- open PRs into main ---"
  gh pr list --base main --state open --limit 10 2>/dev/null || echo "gh pr list failed"
  if [[ -n "${FULL:-}" ]]; then
    echo "--- checks for HEAD (if any) ---"
    gh api "repos/juanwan99/pico/commits/${FULL}/status" --jq '{state}' 2>/dev/null || true
  fi
else
  echo "gh not installed — skip GitHub checks"
fi

if curl -sf --max-time 2 http://127.0.0.1:18765/health >/tmp/pico-health.json 2>/dev/null; then
  echo "--- local health ---"
  cat /tmp/pico-health.json
  echo
else
  echo "--- local health: unreachable (ok if not on prod host) ---"
fi

echo "=== loops (manual) ==="
echo "L3 CI green on candidate SHA?"
echo "L5 merged to main?"
echo "L6 health.git_sha == intended tip?"
echo "See docs/ONEFLOW.md §3"
