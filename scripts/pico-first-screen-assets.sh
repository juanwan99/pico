#!/usr/bin/env bash
# Shared public login and bundle requests for deploy warmup and live acceptance.

get_public_page() {
  local base="$1" route="$2" file="$3" timeout="$4" result
  shift 4
  if ! result="$(curl -fsS --compressed --max-time "$timeout" --output "$file" \
    --write-out '%{http_code} %{time_total}' "$@" "$base$route")"; then
    printf 'FAIL %s %s\n' "$route" "$result" >&2
    return 1
  fi
  if [[ "$result" != '200 '* ]]; then
    printf 'FAIL %s HTTP %s\n' "$route" "$result" >&2
    return 1
  fi
  printf 'PASS %s HTTP %ss\n' "$route" "$result"
}

list_first_screen_bundles() {
  python3 - "$1" <<'PY'
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


class Bundles(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            ref = attrs.get("src") or attrs.get("data-src", "")
        elif tag == "link" and attrs.get("rel") in {"modulepreload", "stylesheet"}:
            ref = attrs.get("href", "")
        else:
            return
        url = urljoin("/login", ref)
        path = urlsplit(url).path
        if re.fullmatch(r"/assets/[\w.-]+\.[\w-]+\.(js|css)", path) and url.startswith("/assets/"):
            self.urls[url] = path.rsplit(".", 1)[-1]


with open(sys.argv[1], encoding="utf-8") as file:
    page = Bundles()
    page.feed(file.read())
if "js" not in page.urls.values() or "css" not in page.urls.values():
    raise SystemExit("FAIL /login missing first-screen JS or CSS bundles")
print(*page.urls, sep="\n")
PY
}

fetch_first_screen_bundles() {
  local base="$1" login_html="$2" mode="$3"
  shift 3
  local assets asset result code media cached count=0 total=0 failed=0
  local format='%{http_code}\t%{content_type}'
  if [[ "$mode" == check ]]; then
    format+='\t%header{x-pico-edge-cache}'
  fi
  assets="$(list_first_screen_bundles "$login_html")" || return $?
  while IFS= read -r asset; do
    total=$((total + 1))
    if ! result="$(curl -fsS -H 'Accept-Encoding: gzip, deflate, br, zstd' --max-time 30 \
      --output /dev/null --write-out "$format" "$@" "$base$asset")"; then
      printf 'FAIL edge cache %s\n' "$asset" >&2
      failed=1
      continue
    fi
    IFS=$'\t' read -r code media cached <<<"$result"
    if [[ "$code" != 200 || "$media" == text/html* ||
      ( "$mode" == check && ! "$cached" =~ ^(HIT|STALE|UPDATING|REVALIDATED)$ ) ]]; then
      printf 'FAIL edge cache %s HTTP %s cache=%s type=%s\n' "$asset" "$code" "$cached" "$media" >&2
      failed=1
    else
      count=$((count + 1))
    fi
  done <<<"$assets"
  if [[ "$mode" == check ]]; then
    printf 'Edge cache served %s/%s bundles\n' "$count" "$total"
  else
    printf 'Edge cache warmup fetched %s/%s bundles\n' "$count" "$total"
  fi
  return "$failed"
}
