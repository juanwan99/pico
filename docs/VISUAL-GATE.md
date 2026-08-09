# 视觉门 · 执行说明（#384）

```text
STATUS: BINDING 操作说明 · 审核真源仍为 GitHub Issue #384
CLAIM-WB: NO · 本文件不签 Ready
```

## 硬规则（抄自 #384）

```text
【视觉门 · BINDING #384】
- 公网浏览器 · 像人点完
- 帧：V0 题面 · V1 过程主气泡 · V2 终态 · V3 产物打开
- 主气泡禁工具/机审独白
- 无图 = 不得请求 Ready
- 审查必须读图；只读表 = 审查无效
```

**工程可合 ≠ 产品过关**（必须同句写清）。  
**CLAIM-WB 只有业主能签。**

## 唯一脚本（禁止各窗另写一套）

| 路径 | 作用 |
|------|------|
| `scripts/visual-gate.mjs` | 登录公网 → 发题 → 强制 V0–V3 PNG + `manifest.json` |
| `scripts/visual-gate-env.sh` | 加载 `~/.secrets/pico-r4r6-evidence.env` + NODE_PATH |
| `scripts/tip-pin.sh` | 单独钉 40 位 tip（脚本内也会钉） |

### 帧命名（死锁）

```text
docs/evidence/<card>/<scene>/
  V0-send.png
  V1-process-main.png
  V2-final.png
  V2-final-390.png
  V3-open-product.png
  manifest.json
  README.md
```

## 运行

```bash
cd /path/to/pico
source scripts/visual-gate-env.sh
node scripts/visual-gate.mjs \
  --card T-EXAMPLE \
  --scene smoke \
  --prompt '只回一句：视觉门OK，不要调用工具'
```

可选环境变量：`PICO_PUBLIC_BASE`、`PICO_VISUAL_TIMEOUT_MS`、`PICO_VISUAL_HEADED=1`、`PICO_VISUAL_SKIP_V3=1`。

## Agent 工具分工（ECS）

| 工具 | 用途 |
|------|------|
| **visual-gate.mjs** | #384 证据真源（进仓 PNG） |
| **Playwright MCP** | 对话里手控浏览器 / 复点 1 题（**不**替代 visual-gate） |
| **Chrome DevTools MCP** | 修主气泡独白时看 Console / Network / SSE |
| tip + 账本 / docker logs | 防「有图假成功」 |

**不必上：** Stagehand / Browser Use / Percy 主路径 / 第二套 E2E 框架（见调研结论）。

## 结论用语

| 可以说 | 不可以说 |
|--------|----------|
| 产品未过 | 单测绿故 Ready |
| 工程可合 · **产品未过** | 全优 Ready（无图） |
| 场景视觉过（帧齐且无否决） | 账本 succeeded = 体验过 |

`manifest.scene_visual_pass_eligible=true` 仅表示脚本启发式通过，**审查仍须读图**；整卡 Ready 须合同内每一场景视觉过 + tip 对齐。
