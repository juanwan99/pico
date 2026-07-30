# M1 dead-code and stale-narrative sweep

```
DOC: docs/DEAD-CODE-SWEEP.md
STATUS: AUDIT ONLY / CANDIDATE EVIDENCE / NOT A PASS VERDICT
AUDITED_AT: 2026-07-30
BRANCH: grok/pico-preview-librechat-p0
BASE_SHA: 3eb03d8154f3bd0743c7ae97001abd38f4734ff6
PLAN_LAW: docs/MVP-3DAY.md v1.2 FIXED
```

## 1. Scope and method

This audit covers:

- forbidden shells: `apps/web`, `apps/nextchat`, `apps/workbench`;
- obsolete tunnel URLs and port/topology descriptions;
- language that could make Mongo a product/AI source of truth or permit a duplicate AI ledger;
- scripts and Pico-touched components with no textual references;
- stale handoffs that conflict with `MASTER-PLAN.md` and `CORRECTED-GOALS.md`.

No code was deleted. No file other than this report was authored by this audit.

The worktree changed concurrently during the scan. At the final snapshot, `Makefile`,
`docker-compose.yml`, `scripts/assert-product-identity.sh`, and an integration test had
changes from another writer. In committed `3eb03d8`, the first two still contain the
NextChat/web topology; the concurrent worktree already contains LibreChat/18765 repairs.
They are therefore recorded below as **repair at the branch tip / pending in the
worktree**, not as changes made by this audit.

## 2. Executive result

| Area | Finding | Classification |
|---|---|---|
| Forbidden app directories | No tracked file exists under any of the three paths | Clean; guardrails retained |
| Runtime shell references | Final worktree has only negative README/CI assertions; committed tip still has stale `Makefile` and root compose entries | Repair-now at tip; pending elsewhere |
| Tunnel | No pinned live tunnel URL; one executable quick-tunnel publisher remains | Delete-now candidate |
| Topology | Production compose uses LibreChat and loopback publication; sandbox preview compatibility still uses 6014/8000/27017 shields | Retain with explicit sandbox scope |
| Mongo / duplicate AI source | Matches are prohibitions or boundary explanations; no affirmative Mongo-as-product/AI-ledger statement found | False positives / retain |
| Scripts | Five files have no textual caller; only two are demonstrably obsolete | Mixed; see classification |
| Components | Three files in the audited Pico-touched component roots have no import/name reference | Delete-now candidates after build |
| Handoffs | Seven exact NextChat/web shell statements conflict with the current LibreChat shell | Two delete candidates; five update/history candidates |

This is an evidence report, not a self-issued M1 PASS.

## 2.1 Applied conservative cleanup

After the audit, the main execution window applied only the zero-reference,
shell-level removals that did not require a LibreChat rebuild:

- deleted `scripts/preview-gateway.py`, `scripts/publish-tunnel.sh`, and
  `scripts/proto.sh`;
- deleted the wholly obsolete `docs/PRODUCT-UI.md` and `docs/DEBRAND.md`;
- removed their remaining documentation links;
- repaired the active root compose, Makefile, and product-identity guard.

The three unreferenced LibreChat components remain until a complete frontend
build can accompany their deletion. This report still does not issue a PASS
verdict.

## 3. Exact command evidence

All commands were run from the repository root.

### 3.1 Forbidden directories

```powershell
git ls-files apps/web apps/nextchat apps/workbench
```

Result:

```text
(no matches)
```

Final-worktree runtime/config scan:

```powershell
rg -n -i "apps[\\/](web|nextchat|workbench)" README.md Makefile docker-compose.yml docker-compose.product.yml docker-compose.host.yml .github scripts --glob "!.git/**"
```

Result:

```text
README.md:35:- 恢复 `apps/web` 自研三栏
scripts\assert-product-identity.sh:6:if [ -d apps/web ]; then echo "FAIL: apps/web"; err=1; fi
scripts\assert-product-identity.sh:7:if [ -d apps/workbench ]; then echo "FAIL: apps/workbench should be deleted"; err=1; fi
scripts\assert-product-identity.sh:8:if [ -d apps/nextchat ]; then echo "FAIL: apps/nextchat should be deleted"; err=1; fi
```

These final-worktree hits are all negative guardrails. At `BASE_SHA`, however,
`Makefile` invokes `apps/nextchat` and `docker-compose.yml` defines `apps/web`.
The concurrent diff repairs both; those files must be committed and reviewed by their
own writer before the branch tip can be considered clean.

### 3.2 Tunnel and preview remnants

```powershell
rg -n -i "trycloudflare|cloudflared|ngrok|localtunnel|loca\.lt|:6014" scripts docs --glob "!docs/DEAD-CODE-SWEEP.md"
```

Material result, with repeated 6014 diagnostic prose condensed only in this table:

```text
docs\DEPLOY-PUBLIC.md:97:bash scripts/publish-tunnel.sh   # → https://….trycloudflare.com
docs\DEPLOY-PUBLIC.md:100:- 沙箱休眠 URL 即废；**不要**把 `pico.aivia.asia` CNAME 到 trycloudflare
docs\DEPLOY-PUBLIC.md:137:| trycloudflare 临时链 | 仅沙箱演示 |
scripts\preview-diagnose.mjs:66:  ['http://127.0.0.1:6014/login', '6014'],
scripts\preview-diagnose.mjs:79:  ['http://127.0.0.1:6014/login', '6014'],
scripts\publish-tunnel.sh:7:LOG="${PICO_TUNNEL_LOG:-/tmp/cloudflared-8080.log}"
scripts\publish-tunnel.sh:8:BIN="${CLOUDFLARED_BIN:-/tmp/cloudflared}"
scripts\publish-tunnel.sh:17:  curl -sL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" -o "$BIN"
scripts\publish-tunnel.sh:32:  URL=$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$LOG" | head -1 || true)
```

Other matches are historical 6014 empty-body diagnostics in
`CALIBRATION-NOW.md`, `CORRECTED-GOALS.md`, `PREVIEW-WHITE-SCREEN.md`,
`REGRESSION-MAINPATH*.md`, `DEMO.md`, and `CANDIDATE-PR.md`. They do not
advertise a production URL.

Specific live-URL scan:

```powershell
rg -n -i "pico[^\s)]*\.(trycloudflare\.com|ngrok[^\s]*|loca\.lt)|https://[^\s)]*\.trycloudflare\.com|https://[^\s)]*(ngrok|loca\.lt)" --glob "!.git/**" --glob "!docs/DEAD-CODE-SWEEP.md"
```

Result:

```text
docs\DEPLOY-PUBLIC.md:97:bash scripts/publish-tunnel.sh   # → https://….trycloudflare.com
```

There is no committed concrete tunnel hostname.

### 3.3 Mongo and duplicate-ledger language

```powershell
rg -n -i "mongo(db)?.{0,80}(产品|首页|真源|账本|source of truth)|(?:产品|首页|真源|账本|source of truth).{0,80}mongo(db)?" README.md docs services scripts --glob "!docs/DEAD-CODE-SWEEP.md"
```

Result:

```text
docs\CALIBRATION-NOW.md:87:| LibreChat Mongo | 会话气泡、用户、UI 状态 | **会话呈现**；不得当成第二套 AI 业务账本长期双写业务真相 |
docs\CALIBRATION-NOW.md:208:7. LibreChat Mongo ≠ 第二 AI 业务真源；业务 AI 真相在 Pico 账本。
docs\ORCHESTRATION-PLAN.md:165:| 双存储误解 | 对外叙事：Mongo=会话；Pico DB=AI 账本 |
docs\MASTER-PLAN.md:106:2. **壳 vs 核：** LibreChat Mongo 会话 ≠ 业务/AI 真源；必须持续 rebind 到 Pico Task。
docs\CORRECTED-GOALS.md:96:禁止：LibreChat Mongo 会话变成「第二套 AI 业务真源」长期双账本
docs\PREVIEW-WHITE-SCREEN.md:44:| `GET :27017/` | **200** 产品 HTML（**27017 盾** → 8080；非 Mongo 英文句） |
docs\PREVIEW-WHITE-SCREEN.md:124:| 对照 | `curl 127.0.0.1:8080` / `curl 127.0.0.1:27017` 均应见产品 HTML；Mongo 英文句不应再出现 |
docs\WORKBENCH-IA-PLAN.md:21:| 映射到 Pico API 账本（Task/Run/Event/Artifact） | 让 LibreChat Mongo 成为第二 AI 真源 |
docs\WORKBENCH-IA-PLAN.md:148:| **G9 账本双写** | LibreChat Mongo vs Pico SQLite | 架构债：事件以 Pico 为准 |
```

Non-boundary matches in `CANDIDATE-PR.md`, `OSS-SHELL.md`, and
`MASTER-PLAN.md` merely state that Mongo is required or must not be public.
No result assigns AI-ledger authority to Mongo or endorses a parallel edu AI ledger.

### 3.4 Unreferenced scripts

```powershell
$files = Get-ChildItem scripts -File
foreach ($f in $files) {
  $rel = "scripts/$($f.Name)"
  $hits = @(rg -l --hidden -F $f.Name --glob "!.git/**" --glob "!$rel" . 2>$null)
  if ($hits.Count -eq 0) { $rel }
}
```

Result:

```text
scripts/cert-renew-dns01-notes.sh
scripts/git-auth-github.sh
scripts/preview-diagnose.mjs
scripts/preview-gateway.py
scripts/proto.sh
```

The scan uses `--hidden` so `.github/workflows/ci.yml` correctly counts as a
caller of `scripts/assert-product-identity.sh`.

### 3.5 Unreferenced Pico-touched components

The 954-file LibreChat upstream component tree is not treated as Pico-owned dead code.
The scan is restricted to `Chat`, `UnifiedSidebar`, `Workbench`, and `Projects`.

```powershell
$roots = @(
  "apps/librechat/client/src/components/Chat",
  "apps/librechat/client/src/components/UnifiedSidebar",
  "apps/librechat/client/src/components/Workbench",
  "apps/librechat/client/src/components/Projects"
)
$files = Get-ChildItem $roots -Recurse -File -Include *.ts,*.tsx |
  Where-Object { $_.BaseName -notin @("index","types") -and $_.Name -notmatch "\.(spec|test)\." }
foreach ($f in $files) {
  $rel = $f.FullName.Replace((Get-Location).Path + "\", "").Replace("\", "/")
  $hits = @(rg -l -w -F $f.BaseName apps/librechat/client/src --glob "!$rel" 2>$null)
  if ($hits.Count -eq 0) { $rel }
}
```

Result:

```text
apps/librechat/client/src/components/Chat/Input/ActiveSetting.tsx
apps/librechat/client/src/components/Chat/Input/HeaderOptions.tsx
apps/librechat/client/src/components/Chat/Menus/Bookmarks/BookmarkMenuItems.tsx
```

`ActiveSetting.tsx` also contains hard-coded upstream demo text:
`[latest] Tailwind CSS GPT`.

### 3.6 Conflicting shell/handoff statements

```powershell
rg -n "Product UI = NextChat|UI: apps/nextchat|Frontend.*NextChat|apps/nextchat.*Product UI|产品壳.*apps/nextchat|NextChat（Vue/Next|如 NextChat / web" docs --glob "!docs/DEAD-CODE-SWEEP.md"
```

Result:

```text
docs\D1-FREEZE.md:17:| Frontend | **NextChat (product shell)** | `apps/nextchat` — `apps/web` removed |
docs\DEBRAND.md:5:UI: apps/nextchat
docs\HANDOFF.md:130:  apps/nextchat/        # Product UI (NextChat) — apps/web REMOVED
docs\OVERALL-ARCHITECTURE.md:357:| UI | NextChat（Vue/Next 产品壳）+ 中文 |
docs\PRODUCT-UI.md:2:# Product UI = NextChat (OSS) + Pico backend
docs\VERSIONING.md:34:产品壳     = apps/nextchat（禁止 apps/web 回归）
docs\WORKFLOW.md:158:| 产品预览 UI | `0.0.0.0:8080`（如 NextChat / web） |
```

## 4. Classification

### 4.1 Delete-now candidates

These are proposed for a later code-changing M1 slice, not deleted here.

| Path | Evidence | Required check with deletion |
|---|---|---|
| `scripts/preview-gateway.py` | Zero references; explicitly routes legacy NextChat `:3000` and API `:8000` | `rg` zero-reference repeat |
| `scripts/publish-tunnel.sh` | Downloads latest `cloudflared` and publishes a disposable URL despite stable production HTTPS | Remove its two documentation call sites |
| `scripts/proto.sh` | Zero references; deprecated alias whose comment still says NextChat | `scripts/run-product.sh` remains canonical |
| `apps/librechat/client/src/components/Chat/Input/ActiveSetting.tsx` | Zero component-name references; hard-coded upstream GPT text | LibreChat typecheck/build |
| `apps/librechat/client/src/components/Chat/Input/HeaderOptions.tsx` | Zero component-name references | LibreChat typecheck/build |
| `apps/librechat/client/src/components/Chat/Menus/Bookmarks/BookmarkMenuItems.tsx` | Zero component-name references | LibreChat typecheck/build and bookmark smoke |
| `docs/PRODUCT-UI.md` | Entire document declares NextChat as the product UI | Replace inbound references, if any |
| `docs/DEBRAND.md` | Binding practice points exclusively at deleted `apps/nextchat` | Replace with LibreChat debrand guidance only if still needed |

### 4.2 Retain as current operation or history

| Path/item | Why retain | Follow-up |
|---|---|---|
| `scripts/run-product.sh`, `preview-mirror-8000.py`, `mongo-port-http-shield.py`, `pin-preview-8080.sh` | Referenced sandbox startup chain; 8000/27017 are preview mis-pin compatibility surfaces, not production API/Mongo publication | Keep sandbox-only wording; reassess when Grok preview compatibility is retired |
| `scripts/preview-diagnose.mjs` | Manual 8080-vs-6014 diagnostic and evidence generator | Add a documented manual invocation instead of deleting |
| `scripts/cert-renew-dns01-notes.sh` | Manual production certificate status/renewal helper | No action |
| `scripts/git-auth-github.sh` | Manual private-repository auth helper | No action; never print token |
| `scripts/security_proof.py` | Safety evidence utility even without basename references | Retain; optionally link from security docs |
| `scripts/assert-product-identity.sh` | Called by hidden `.github/workflows/ci.yml` | Retain as mandatory shell guard |
| `docs/D1-FREEZE.md` | Referenced by dependency pins and orchestrator code | Mark historical and correct only the obsolete shell row |
| `docs/HANDOFF.md` | Already has a stale warning and contains historical decisions | Prefer a short tombstone/redirect to `MASTER-PLAN.md`, not silent deletion |
| `docs/OVERALL-ARCHITECTURE.md` | Referenced architecture/pricing draft with useful non-shell content | Correct NextChat lines; keep DRAFT status |
| `docs/VERSIONING.md`, `docs/WORKFLOW.md` | Binding and linked by `AGENTS.md` | Correct shell/topology examples in place |
| `screenshots/**`, `screenshots/preview-diagnose.json` | Tracked visual/diagnostic evidence, not runtime inputs | Retain until a separate evidence-retention policy exists |

### 4.3 False positives

| Match | Reason |
|---|---|
| Forbidden paths in `README.md`, `apps/README.md`, `CORRECTED-GOALS.md`, and `assert-product-identity.sh` | They forbid reintroduction; deleting the terms would weaken the guardrail |
| Mongo/ledger matches listed in section 3.3 | They explicitly deny Mongo authority and assign the AI ledger to Pico |
| `0.0.0.0:18765` inside the local compose container | No host port is published for `pico-api`; only LibreChat publishes `127.0.0.1:8080` |
| `:27017` returning HTML in sandbox docs | This describes an HTTP mis-pin shield while Mongo wire runs elsewhere; it is not the production Mongo topology |
| `:6014` diagnostics | Historical Grok preview-proxy evidence, not a product endpoint or public deployment recommendation |
| Zero basename references for certificate/auth/diagnostic scripts | These are intentionally manual operational tools |

## 5. Conservative proposed deletion set

The smallest supported deletion batch is:

```text
scripts/preview-gateway.py
scripts/publish-tunnel.sh
scripts/proto.sh
apps/librechat/client/src/components/Chat/Input/ActiveSetting.tsx
apps/librechat/client/src/components/Chat/Input/HeaderOptions.tsx
apps/librechat/client/src/components/Chat/Menus/Bookmarks/BookmarkMenuItems.tsx
docs/PRODUCT-UI.md
docs/DEBRAND.md
```

Accompanying edits, not deletions:

1. Remove quick-tunnel instructions from `docs/DEPLOY-PUBLIC.md` and
   `docs/PREVIEW-WHITE-SCREEN.md`.
2. Commit/review the pending LibreChat repairs for `Makefile`,
   `docker-compose.yml`, and `scripts/assert-product-identity.sh`.
3. Correct shell rows in `D1-FREEZE.md`, `HANDOFF.md`,
   `OVERALL-ARCHITECTURE.md`, `VERSIONING.md`, and `WORKFLOW.md`.
4. Repeat the exact reference scans, run `scripts/agent-selftest.sh`, relevant
   unit tests, and a LibreChat production build before accepting deletion.

## 6. Explicit non-actions

- No code or documentation other than this report was deleted or edited.
- No edu-cloud file was read or written by this audit.
- No main merge was attempted.
- No PASS verdict is asserted.
- MVP-3DAY remains v1.2 FIXED.
