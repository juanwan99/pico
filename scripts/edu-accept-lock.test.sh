#!/usr/bin/env bash
# Fixture tests for scripts/edu-accept-lock.sh (edu-core#4735). Temp lock dir, no docker.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"
trap 'pkill -P $$ 2>/dev/null; kill $(jobs -p) 2>/dev/null; rm -rf "$T"' EXIT
fail=0
n=0
check() {  # check <name> <want-rc> <got-rc> <out> <grep>
  n=$((n + 1))
  if [ "$3" -ne "$2" ] || ! grep -q -- "$5" <<<"$4"; then
    echo "FAIL $n $1: want rc=$2 + '$5', got rc=$3"; printf '%s\n' "$4"; fail=1
  else
    echo "ok   $n $1"
  fi
}
take() {  # run in a child shell like the impl does
  PICO_EDU_ACCEPT_LOCK="$1" PICO_EDU_ACCEPT_LOCK_WAIT_MIN="${2:-90}" PICO_DEPLOY_SHA=abc \
    bash -c ". '$ROOT/scripts/edu-accept-lock.sh'; edu_accept_lock_take; rc=\$?; [ \$rc -eq 0 ] && flock -n 7 && echo HELD7; exit \$rc" 2>&1
}

out="$(take "$T/none/acceptance.lock")"; check "no ~/.edu-core → skip" 0 $? "$out" "absent — skip"

L="$T/acceptance.lock"
out="$(take "$L")"; check "free lock → held" 0 $? "$out" "HELD7"
grep -q " pico-deploy abc$" "$L.owner" && echo "ok   owner pico-deploy" || { echo "FAIL owner: $(cat "$L.owner")"; fail=1; }

echo "x ship-queue sha" >"$L.owner"
flock "$L" sleep 3 >/dev/null 2>&1 & sleep 0.3
t0=$SECONDS; out="$(take "$L")"; rc=$?
check "busy → waits, then held" 0 $rc "$out" "waiting up to"
[ $((SECONDS - t0)) -ge 2 ] && echo "ok   waited for holder" || { echo "FAIL did not wait"; fail=1; }

flock "$L" sleep 100 >/dev/null 2>&1 & sleep 0.3
out="$(PICO_EDU_ACCEPT_LOCK="$L" PICO_EDU_ACCEPT_LOCK_WAIT_MIN=0 bash -c ". '$ROOT/scripts/edu-accept-lock.sh'; edu_accept_lock_take || exit \$?; echo REACHED" 2>&1)"
check "timeout → BLOCKED rc 17, stops" 17 $? "$out" "BLOCKED"
grep -q REACHED <<<"$out" && { echo "FAIL went on after timeout"; fail=1; }

grep -q 'edu_accept_lock_take' "$ROOT/scripts/prod-update.impl.sh" \
  && awk '/edu_accept_lock_take/{a=NR} /^inflight="\$\(inflight_runs_now\)"/{b=NR} END{exit !(a && b && a<b)}' "$ROOT/scripts/prod-update.impl.sh" \
  && echo "ok   impl takes lock before drain / recreate" || { echo "FAIL impl wiring"; fail=1; }

grep -q 'force=1" >"$REINDEX_LOG" 2>&1 7>&- &' "$ROOT/scripts/prod-update.impl.sh" \
  && echo "ok   background reindex drops fd 7" || { echo "FAIL background reindex keeps lock"; fail=1; }

[ "$fail" = 0 ] && echo "edu-accept-lock: all ok" || exit 1
