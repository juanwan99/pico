#!/usr/bin/env bash
# Sourced by prod-update.impl.sh. Same ECS host as edu-core: every edu-core
# acceptance run (after its ship, daily full suite, manual) holds
# ~/.edu-core/acceptance.lock and talks to Pico. Recreating pico-api mid-run
# turned edu-core acceptance red (edu-core#4696 → #4735). So the deploy queues
# for that lock before drain + recreate and holds it to the end (fd 7, closed
# on exit). Not edu-core's ship.lock: edu-core ship smoke does not hit Pico.
# No retry, no skip on timeout: past the wait we stop before touching containers.
# Host without ~/.edu-core: no-op.
edu_accept_lock_take() {
  local lock="${PICO_EDU_ACCEPT_LOCK:-$HOME/.edu-core/acceptance.lock}"
  local wait_min="${PICO_EDU_ACCEPT_LOCK_WAIT_MIN:-90}"
  if [ ! -d "$(dirname "$lock")" ]; then
    echo "[pico] edu-core acceptance lock: $(dirname "$lock") absent — skip"
    return 0
  fi
  exec 7>>"$lock"
  if ! flock -n 7; then
    echo "[pico] edu-core acceptance running ($(cat "$lock.owner" 2>/dev/null || echo unknown)) — waiting up to ${wait_min}m"
    if ! flock -w "$((wait_min * 60))" 7; then
      echo "[pico] BLOCKED: edu-core acceptance lock not free after ${wait_min}m ($lock.owner); containers untouched" >&2
      return 17
    fi
  fi
  # edu-core ship-follow only voids owners containing " ship "; this one it leaves alone.
  printf '%s pid=%s pico-deploy %s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)" "$$" "${PICO_DEPLOY_SHA:-?}" >"$lock.owner"
  echo "[pico] edu-core acceptance lock held"
}
