#!/usr/bin/env bash
# tool-status — ECS tooling probe for TOOLING-CATALOG (#386/#387).
# Prints human summary or --json. NEVER prints secret values.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JSON=0
[[ "${1:-}" == "--json" || "${1:-}" == "-j" ]] && JSON=1

have_cmd() { command -v "$1" >/dev/null 2>&1; }

ok_json() {
  # name ok detail(optional)
  local name="$1" ok="$2" detail="${3:-}"
  if [[ -n "$detail" ]]; then
    printf '{"ok":%s,"detail":%s}' "$ok" "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$detail")"
  else
    printf '{"ok":%s}' "$ok"
  fi
}

# --- probes (no secret values) ---
node_ok=false; node_v=""
if have_cmd node; then node_ok=true; node_v="$(node -v 2>/dev/null || true)"; fi

playwright_cli_ok=false; playwright_v=""
if have_cmd playwright; then
  playwright_cli_ok=true
  playwright_v="$(playwright --version 2>/dev/null | head -1 || true)"
elif [[ -x "${HOME}/.npm-global/lib/node_modules/playwright/cli.js" ]]; then
  playwright_cli_ok=true
  playwright_v="npm-global"
fi

gh_ok=false; gh_v=""
if have_cmd gh; then gh_ok=true; gh_v="$(gh --version 2>/dev/null | head -1 || true)"; fi

git_ok=false
have_cmd git && git_ok=true

pytest_ok=false
have_cmd pytest && pytest_ok=true

ruff_ok=false
have_cmd ruff && ruff_ok=true

docker_ok=false
have_cmd docker && docker_ok=true

ssh_ok=false
have_cmd ssh && ssh_ok=true

# scripts in repo
vg_ok=false
[[ -f "$ROOT/scripts/visual-gate.mjs" ]] && vg_ok=true

tip_script_ok=false
[[ -f "$ROOT/scripts/tip-pin.sh" ]] && tip_script_ok=true

rh_ok=false
[[ -f "$ROOT/scripts/remote-health.sh" ]] && rh_ok=true

catalog_ok=false
[[ -f "$ROOT/docs/TOOLING-CATALOG.md" ]] && catalog_ok=true

# demo secret presence only (not values)
demo_ok=false
demo_email_set=false
if [[ -n "${DEMO_EMAIL:-${PICO_E2E_EMAIL:-}}" ]]; then
  demo_email_set=true
fi
_pass="${DEMO_PASSWORD:-${PICO_E2E_PASSWORD:-}}"
if [[ "$demo_email_set" == true && ${#_pass} -ge 12 ]]; then
  demo_ok=true
elif [[ -f "${HOME}/.secrets/pico-r4r6-evidence.env" ]]; then
  # file exists — count as available for agents that source it; do not read values into output
  demo_ok=true
  demo_email_set=true
fi

# MCP config presence (grok + mcp.json)
pw_mcp_ok=false
pw_mcp_browser=""
if [[ -f "${HOME}/.grok/config.toml" ]] && grep -q 'mcp_servers.playwright' "${HOME}/.grok/config.toml" 2>/dev/null; then
  pw_mcp_ok=true
  if grep -q 'chromium' "${HOME}/.grok/config.toml" 2>/dev/null; then
    pw_mcp_browser="chromium"
  elif grep -q 'firefox' "${HOME}/.grok/config.toml" 2>/dev/null; then
    pw_mcp_browser="firefox"
  else
    pw_mcp_browser="configured"
  fi
elif [[ -f "${HOME}/.mcp.json" ]] && grep -q 'playwright' "${HOME}/.mcp.json" 2>/dev/null; then
  pw_mcp_ok=true
  if grep -q 'chromium' "${HOME}/.mcp.json" 2>/dev/null; then
    pw_mcp_browser="chromium"
  else
    pw_mcp_browser="other"
  fi
fi

cdt_mcp_ok=false
if [[ -f "${HOME}/.grok/config.toml" ]] && grep -q 'chrome-devtools' "${HOME}/.grok/config.toml" 2>/dev/null; then
  cdt_mcp_ok=true
elif [[ -f "${HOME}/.mcp.json" ]] && grep -q 'chrome-devtools' "${HOME}/.mcp.json" 2>/dev/null; then
  cdt_mcp_ok=true
fi

# public tip (no auth)
tip_ok=false
tip_sha=""
tip_err=""
TIP_URL="${PICO_PUBLIC_BASE:-https://pico.aivia.asia}"
TIP_URL="${TIP_URL%/}/api/pico/tip"
if tip_raw="$(python3 - "$TIP_URL" <<'PY' 2>/dev/null
import json, re, sys, urllib.request
url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=12) as r:
        data = json.loads(r.read().decode())
except Exception as e:
    print("ERR", e)
    raise SystemExit(1)
sha = data.get("git_sha") or ""
if data.get("ok") and re.fullmatch(r"[0-9a-f]{40}", sha):
    print(sha)
else:
    print("ERR bad tip")
    raise SystemExit(1)
PY
)"; then
  if [[ "$tip_raw" != ERR* && ${#tip_raw} -eq 40 ]]; then
    tip_ok=true
    tip_sha="$tip_raw"
  else
    tip_err="$tip_raw"
  fi
else
  tip_err="fetch_failed"
fi

# retired mechanisms: active paths must be gone
cool_active=false
sup_active=false
[[ -e "${HOME}/cool-blocks" ]] && cool_active=true
[[ -e "${HOME}/edu-supervisor-window" ]] && sup_active=true
# also flag if non-archive cool/keel dirs at home maxdepth 1
retired_clear=true
if [[ "$cool_active" == true || "$sup_active" == true ]]; then
  retired_clear=false
fi
archive_dir="${HOME}/archive/retired-mechanisms-20260809"
archive_present=false
[[ -d "$archive_dir" ]] && archive_present=true

# blocked for visual gate: need tip + demo secret + playwright + (visual-gate script preferred)
blocked=false
missing=()
$tip_ok || missing+=("tip_public")
$demo_ok || missing+=("demo_secret")
$playwright_cli_ok || missing+=("playwright_cli")
$vg_ok || missing+=("visual_gate_script")
$catalog_ok || missing+=("tooling_catalog_doc")
$retired_clear || missing+=("retired_mechanisms_active")

# visual gate blocked if core missing (script miss still blocked for full #384 automation)
if ! $tip_ok || ! $demo_ok || ! $playwright_cli_ok || ! $vg_ok; then
  blocked=true
fi
if ! $retired_clear; then
  blocked=true
fi

AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOST_NAME="$(hostname 2>/dev/null || echo unknown)"

if [[ "$JSON" -eq 1 ]]; then
  python3 - "$AT" "$HOST_NAME" "$ROOT" \
    "$node_ok" "$node_v" \
    "$playwright_cli_ok" "$playwright_v" \
    "$pw_mcp_ok" "$pw_mcp_browser" \
    "$cdt_mcp_ok" \
    "$gh_ok" "$git_ok" "$pytest_ok" "$ruff_ok" "$docker_ok" "$ssh_ok" \
    "$vg_ok" "$tip_script_ok" "$rh_ok" "$catalog_ok" \
    "$demo_ok" "$demo_email_set" \
    "$tip_ok" "$tip_sha" "$TIP_URL" \
    "$retired_clear" "$cool_active" "$sup_active" "$archive_present" "$archive_dir" \
    "$blocked" "${missing[*]-}" <<'PY'
import json, sys
(
    at, host, root,
    node_ok, node_v,
    pw_cli_ok, pw_v,
    pw_mcp_ok, pw_mcp_browser,
    cdt_ok,
    gh_ok, git_ok, pytest_ok, ruff_ok, docker_ok, ssh_ok,
    vg_ok, tip_script_ok, rh_ok, catalog_ok,
    demo_ok, demo_email_set,
    tip_ok, tip_sha, tip_url,
    retired_clear, cool_active, sup_active, archive_present, archive_dir,
    blocked, missing_s,
) = sys.argv[1:]

def b(s):
    return s == "true"

missing = [x for x in missing_s.split() if x]
out = {
    "at": at,
    "host": host,
    "repo_root": root,
    "catalog_ref": "docs/TOOLING-CATALOG.md",
    "binding": ["#386", "#387", "#384"],
    "claim_wb": "NO",
    "product_ready": False,
    "tools": {
        "node": {"ok": b(node_ok), "version": node_v or None},
        "playwright_cli": {"ok": b(pw_cli_ok), "version": pw_v or None},
        "playwright_mcp": {"ok": b(pw_mcp_ok), "browser": pw_mcp_browser or None},
        "chrome_devtools_mcp": {"ok": b(cdt_ok)},
        "gh": {"ok": b(gh_ok)},
        "git": {"ok": b(git_ok)},
        "pytest": {"ok": b(pytest_ok)},
        "ruff": {"ok": b(ruff_ok)},
        "docker": {"ok": b(docker_ok)},
        "ssh": {"ok": b(ssh_ok)},
        "visual_gate_script": {"ok": b(vg_ok), "path": "scripts/visual-gate.mjs"},
        "tip_pin_script": {"ok": b(tip_script_ok), "path": "scripts/tip-pin.sh"},
        "remote_health_script": {"ok": b(rh_ok), "path": "scripts/remote-health.sh"},
        "tooling_catalog_doc": {"ok": b(catalog_ok), "path": "docs/TOOLING-CATALOG.md"},
        "demo_secret": {
            "ok": b(demo_ok),
            "email_set": b(demo_email_set),
            "note": "presence only; values never printed",
        },
        "tip_public": {
            "ok": b(tip_ok),
            "git_sha": tip_sha or None,
            "url": tip_url,
        },
        "retired_mechanisms": {
            "ok": b(retired_clear),
            "clear": b(retired_clear),
            "cool_blocks_active": b(cool_active),
            "edu_supervisor_window_active": b(sup_active),
            "archive_present": b(archive_present),
            "archive_dir": archive_dir,
        },
    },
    "missing": missing,
    "blocked_for_visual_gate": b(blocked),
}
print(json.dumps(out, ensure_ascii=False, indent=2))
PY
  exit 0
fi

# human summary
echo "=== tool-status · $AT · host=$HOST_NAME ==="
echo "catalog: docs/TOOLING-CATALOG.md · CLAIM-WB=NO"
echo "tip: ok=$tip_ok sha=${tip_sha:-—}"
echo "demo_secret: ok=$demo_ok (presence only)"
echo "playwright_cli: ok=$playwright_cli_ok"
echo "playwright_mcp: ok=$pw_mcp_ok browser=${pw_mcp_browser:-—}"
echo "chrome_devtools_mcp: ok=$cdt_mcp_ok"
echo "visual_gate_script: ok=$vg_ok"
echo "tip_pin_script: ok=$tip_script_ok"
echo "remote_health: ok=$rh_ok"
echo "gh/git/pytest/ruff: $gh_ok/$git_ok/$pytest_ok/$ruff_ok"
echo "retired_mechanisms.clear: $retired_clear (cool_active=$cool_active supervisor_active=$sup_active)"
echo "archive_present: $archive_present → $archive_dir"
echo "blocked_for_visual_gate: $blocked"
echo "missing: ${missing[*]:-(none)}"
