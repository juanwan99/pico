#!/usr/bin/env bash
# Public workbench check. Use a dedicated drill account via PICO_E2E_EMAIL/PASSWORD.
set -euo pipefail

cd "$(dirname "$0")/../.."
base="${PICO_PUBLIC_BASE:-https://pico.aivia.asia}"
base="${base%/}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

get_page() {
  local route="$1" file="$2" result
  if ! result="$(curl -fsS --compressed --max-time 3 --output "$file" \
    --write-out '%{http_code} %{time_total}' "$base$route")"; then
    printf 'FAIL %s %s\n' "$route" "$result" >&2
    return 1
  fi
  if [[ "$result" != '200 '* ]]; then
    printf 'FAIL %s HTTP %s\n' "$route" "$result" >&2
    return 1
  fi
  printf 'PASS %s HTTP %ss\n' "$route" "$result"
}

get_page /login "$work/login.html"
get_page /api/pico/tip "$work/tip.json"

python3 - "$work/tip.json" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as file:
    tip = json.load(file)
sha = tip.get("git_sha", "")
if tip.get("ok") is not True or not re.fullmatch(r"[0-9a-f]{40}", sha):
    raise SystemExit("FAIL /api/pico/tip did not return a release SHA")
print(f"PASS tip {sha}")
PY

python3 - "$work/login.html" >"$work/assets" <<'PY'
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

# Check the cache as a visitor finds it, without filling it first.
count=0
failed=0
while IFS= read -r asset; do
  result="$(curl -fsS --compressed --max-time 30 --output /dev/null \
    --write-out '%{http_code}\t%{content_type}\t%header{x-pico-edge-cache}' "$base$asset")"
  IFS=$'\t' read -r code media cached <<<"$result"
  if [[ "$code" == 200 && "$media" != text/html* && "$cached" == HIT ]]; then
    count=$((count + 1))
  else
    printf 'FAIL edge cache %s HTTP %s cache=%s type=%s\n' "$asset" "$code" "$cached" "$media" >&2
    failed=1
  fi
done <"$work/assets"
printf 'Edge cache HIT %s/%s bundles\n' "$count" "$(wc -l <"$work/assets")"
if [[ "$failed" == 1 ]]; then
  exit 1
fi

PICO_PUBLIC_BASE="$base" node --input-type=module <<'JS'
import { emailPass, loadPlaywright } from './scripts/night-sandbox/lib.mjs';

const { email, password } = emailPass();
if (!email || !password) {
  console.error('BLOCKED login and chat require PICO_E2E_EMAIL and PICO_E2E_PASSWORD');
  process.exit(2);
}

const { chromium } = loadPlaywright();
const browser = await chromium.launch();
let step = 'login';
try {
  const page = await browser.newPage({ locale: 'zh-CN' });
  await page.goto(new URL('/login', process.env.PICO_PUBLIC_BASE).href);
  await page.locator('#email').fill(email);
  await page.locator('#password').fill(password);
  await page.getByTestId('login-button').click();
  const composer = page.locator('#pico-wb-home-input');
  await composer.waitFor({ state: 'visible', timeout: 45_000 });
  console.log('PASS workbench login');
  step = 'chat';
  await composer.fill('请只回复「工作台连通」这五个字。');
  await page.getByTestId('send-button').click();
  await page.locator('.agent-turn .message-content')
    .getByText('工作台连通', { exact: true }).waitFor({ state: 'visible', timeout: 90_000 });
  await page.getByTestId('stop-generation-button').waitFor({ state: 'hidden', timeout: 10_000 });
  console.log('PASS workbench chat');
} catch (error) {
  // Playwright's action log can include values entered in the login form.
  console.error(`FAIL workbench ${step} (${error.name})`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
JS
