# Pico 执行工作流（绑定）

```text
DOC: docs/WORKFLOW.md
STATUS: BINDING v0.4 — 2026-08-22
OS: docs/ONEFLOW.md v2
REPO: juanwan99/pico ONLY
```

操作系统认 [`ONEFLOW.md`](./ONEFLOW.md) v2。本文只留 **pico 边界** 和 **风险档**。

禁止再造：调度器、mailbox、进度账本、315 填表。

## 1. 硬范围

| 允许 | 禁止 |
|------|------|
| 读写 **pico** | 把 edu 业务写进 pico 当第二套 SaaS |
| 只读参考 edu 文档 | 无说明直推 main |

## 2. 路径

```text
目标 → 四行卡或直接 PR → CI 绿 → 合 main → prod-update.sh → tip SHA 对齐
```

CANDIDATE 三行即可：SHA · 过门映射 · BLOCKED。
写入 `VERDICT_AUTHORITY: NONE`。黄/红要独立审查同一完整 SHA。

## 3. 风险档

| 档 | 门禁 |
|----|------|
| 绿 | CI + 自检 |
| 黄 | CI + 独立 SHA 审查 |
| 红 | 同上 + 任务授权 |

红路径：`auth.py` / membership 隔离 / 危险工具开关 / 密钥 / `AGENTS.md` 与本文件 / `.github/workflows/**` / 破坏性账本模型。

## 4. 环境

| 用途 | 约定 |
|------|------|
| 预览 | 产品 UI `0.0.0.0:8080`；API loopback |
| 生产 | `https://pico.aivia.asia` · `/opt/pico` |
| 已部署 | 仅 tip `git_sha` |

## 5. 修订

工作流变更须替换旧句，禁止只追加冲突层。
