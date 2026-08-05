#!/usr/bin/env bash
# Sample public readiness paths without credentials or response bodies.
set -euo pipefail

base_url="${1:-https://pico.aivia.asia}"
samples="${2:-30}"
interval="${3:-30}"

if [[ ! "$samples" =~ ^[1-9][0-9]*$ || ! "$interval" =~ ^[0-9]+$ ]]; then
  echo "usage: $0 [https-base-url] [samples] [interval-seconds]" >&2
  exit 2
fi

printf 'timestamp_utc\tpath\tstatus\ttotal_seconds\n'
for ((i = 1; i <= samples; i++)); do
  for path in /health /login; do
    curl --silent --show-error --output /dev/null --max-time 10 \
      --write-out "$(date -u +%FT%TZ)\t${path}\t%{http_code}\t%{time_total}\n" \
      "${base_url%/}${path}" || printf '%s\t%s\t000\tfailed\n' "$(date -u +%FT%TZ)" "$path"
  done
  if ((i < samples)); then sleep "$interval"; fi
done
