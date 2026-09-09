#!/usr/bin/env bash
# Production update bootstrap. Fetch + checkout a main SHA, then exec the
# impl from that tree. Deploy behavior must not live here: bash keeps the
# old inode open across `git checkout`, so a monolith cannot apply its own
# changes in the same run.
# Usage: PICO_DEPLOY_SHA=<full-40-char-main-sha> bash /opt/pico/scripts/prod-update.sh
set -euo pipefail

ROOT="${PICO_ROOT:-/opt/pico}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.host.yml}"
DEPLOY_SHA="${PICO_DEPLOY_SHA:-}"

if [[ ! "$DEPLOY_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "[pico] BLOCKED: PICO_DEPLOY_SHA must be a full 40-character commit SHA" >&2
  exit 2
fi

cd "$ROOT"
echo "[pico] update $(hostname) $(date -Is)"
echo "[pico] before: $(git rev-parse HEAD 2>/dev/null || echo none)"

# Production checkouts are immutable inputs. Never hide local edits in an automatic stash.
if [ -n "$(git status --porcelain --untracked-files=normal)" ]; then
  echo "[pico] BLOCKED: production worktree has local changes; inspect them before deploy" >&2
  git status --short >&2
  exit 2
fi

print_main_refspec_help() {
  echo "[pico] configured remote.origin.fetch:" >&2
  git config --get-all remote.origin.fetch 2>/dev/null | sed 's/^/[pico]   /' >&2 || true
  echo "[pico] fix: git config --replace-all remote.origin.fetch '+refs/heads/main:refs/remotes/origin/main'" >&2
  echo "[pico] then rerun: git fetch origin main" >&2
}

git fetch origin main
if ! FETCH_SHA="$(git rev-parse --verify 'FETCH_HEAD^{commit}' 2>/dev/null)"; then
  echo "[pico] BLOCKED: fetch completed but FETCH_HEAD is not a commit" >&2
  print_main_refspec_help
  exit 3
fi
if ! MAIN_SHA="$(git rev-parse --verify 'refs/remotes/origin/main^{commit}' 2>/dev/null)"; then
  echo "[pico] BLOCKED: origin/main is missing after fetching main" >&2
  print_main_refspec_help
  exit 3
fi
if [ "$MAIN_SHA" != "$FETCH_SHA" ]; then
  echo "[pico] BLOCKED: origin/main did not advance to the fetched main tip" >&2
  echo "[pico] FETCH_HEAD=$FETCH_SHA" >&2
  echo "[pico] origin/main=$MAIN_SHA" >&2
  print_main_refspec_help
  exit 3
fi

ORIGIN_FETCH_REFSPECS="$(git config --get-all remote.origin.fetch 2>/dev/null || true)"
FETCH_TRACKS_MAIN=0
while IFS= read -r refspec; do
  normalized_refspec="${refspec#+}"
  if [ "$normalized_refspec" = 'refs/heads/main:refs/remotes/origin/main' ] || \
    [ "$normalized_refspec" = 'refs/heads/*:refs/remotes/origin/*' ]; then
    FETCH_TRACKS_MAIN=1
    break
  fi
done <<<"$ORIGIN_FETCH_REFSPECS"
if [ "$FETCH_TRACKS_MAIN" -ne 1 ]; then
  echo "[pico] BLOCKED: remote.origin.fetch does not track main as origin/main" >&2
  print_main_refspec_help
  exit 3
fi

if ! git cat-file -e "${DEPLOY_SHA}^{commit}" 2>/dev/null; then
  echo "[pico] BLOCKED: requested SHA is not in this clone after fetching main" >&2
  echo "[pico] requested=$DEPLOY_SHA" >&2
  exit 3
fi
if ! git merge-base --is-ancestor "$DEPLOY_SHA" "$MAIN_SHA"; then
  echo "[pico] BLOCKED: requested SHA is not on origin/main" >&2
  echo "[pico] 旁支不准部。先 squash 合进 origin/main。" >&2
  echo "[pico] requested=$DEPLOY_SHA" >&2
  echo "[pico] origin/main=$MAIN_SHA" >&2
  exit 3
fi
if [ "$DEPLOY_SHA" != "$MAIN_SHA" ]; then
  echo "[pico] NOTE: deploying older main SHA (rollback), not tip" >&2
  echo "[pico] requested=$DEPLOY_SHA origin/main=$MAIN_SHA" >&2
fi

# Detached checkout prevents a server-local branch from becoming a second release source.
git checkout --detach "$DEPLOY_SHA"
CURRENT_SHA="$(git rev-parse HEAD)"
if [ "$CURRENT_SHA" != "$DEPLOY_SHA" ]; then
  echo "[pico] FATAL: checkout mismatch got=$CURRENT_SHA want=$DEPLOY_SHA" >&2
  exit 3
fi
echo "[pico] deploying: $CURRENT_SHA"
git log -1 --oneline

IMPL="$ROOT/scripts/prod-update.impl.sh"
if [ ! -f "$IMPL" ]; then
  echo "[pico] FATAL: $IMPL missing after checkout — this SHA is not a valid deploy tree" >&2
  exit 3
fi
echo "[pico] exec impl from $CURRENT_SHA"
exec bash "$IMPL"
