#!/usr/bin/env bash
# Fixture tests for scripts/pr-ci-ready.sh. No gh / no poll.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/scripts/pr-ci-ready.sh"
fail=0
n=0

run() {
  local name="$1" expect="$2" json="$3"
  shift 3
  n=$((n + 1))
  set +e
  out="$(PR_CI_READY_JSON="$json" bash "$BIN" "$@" 2>&1)"
  rc=$?
  set -e
  if [[ "$rc" -ne "$expect" ]]; then
    echo "FAIL $n $name: want exit $expect got $rc"
    printf '%s\n' "$out"
    fail=1
  else
    echo "ok   $n $name (exit $rc)"
  fi
}

run "usage-no-pr" 3 ""
run "usage-bad-pr" 3 '{"state":"OPEN","statusCheckRollup":[]}' --pr x

run "green-checkrun" 0 \
  '{"state":"OPEN","mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"python-lint-test","conclusion":"SUCCESS","status":"COMPLETED"},{"name":"product-ui-tests","conclusion":"SUCCESS","status":"COMPLETED"},{"name":"product-ui-librechat-shell","conclusion":"SUCCESS","status":"COMPLETED"}]}' \
  --pr 1

run "green-skipped-neutral" 0 \
  '{"state":"OPEN","mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"a","conclusion":"SKIPPED"},{"name":"b","conclusion":"NEUTRAL"}]}' \
  --pr 2

run "green-status-context" 0 \
  '{"state":"OPEN","mergeStateStatus":"CLEAN","statusCheckRollup":[{"context":"continuous-integration","state":"SUCCESS"}]}' \
  --pr 3

run "pending-in-progress" 1 \
  '{"state":"OPEN","mergeStateStatus":"UNKNOWN","statusCheckRollup":[{"name":"python-lint-test","status":"IN_PROGRESS"}]}' \
  --pr 4

run "pending-empty" 1 \
  '{"state":"OPEN","mergeStateStatus":"UNKNOWN","statusCheckRollup":[]}' \
  --pr 5

run "pending-queued" 1 \
  '{"state":"OPEN","statusCheckRollup":[{"name":"a","status":"QUEUED"}]}' \
  --pr 6

run "pending-status-context" 1 \
  '{"state":"OPEN","statusCheckRollup":[{"context":"ci","state":"PENDING"}]}' \
  --pr 7

run "pending-blocked-merge" 1 \
  '{"state":"OPEN","mergeStateStatus":"BLOCKED","statusCheckRollup":[{"name":"a","conclusion":"SUCCESS"}]}' \
  --pr 8

run "red-failure" 2 \
  '{"state":"OPEN","mergeStateStatus":"UNSTABLE","statusCheckRollup":[{"name":"a","conclusion":"FAILURE"}]}' \
  --pr 9

run "red-cancelled" 2 \
  '{"state":"OPEN","statusCheckRollup":[{"name":"a","conclusion":"CANCELLED"}]}' \
  --pr 10

run "red-timed-out" 2 \
  '{"state":"OPEN","statusCheckRollup":[{"name":"a","conclusion":"TIMED_OUT"}]}' \
  --pr 11

run "red-action-required" 2 \
  '{"state":"OPEN","statusCheckRollup":[{"name":"a","conclusion":"ACTION_REQUIRED"}]}' \
  --pr 12

run "red-closed" 2 \
  '{"state":"CLOSED","statusCheckRollup":[{"name":"a","conclusion":"SUCCESS"}]}' \
  --pr 13

run "red-merged" 2 \
  '{"state":"MERGED","statusCheckRollup":[{"name":"a","conclusion":"SUCCESS"}]}' \
  --pr 14

run "red-dirty" 2 \
  '{"state":"OPEN","mergeStateStatus":"DIRTY","statusCheckRollup":[{"name":"a","conclusion":"SUCCESS"}]}' \
  --pr 15

run "bad-json" 3 \
  '{not-json' \
  --pr 16

if [[ "$fail" -ne 0 ]]; then
  echo "pr-ci-ready.test.sh FAILED"
  exit 1
fi
echo "pr-ci-ready.test.sh passed ($n)"
