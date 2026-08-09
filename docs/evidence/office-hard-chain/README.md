# T-OFFICE-HARD-CHAIN · 公网 UI 证据（#369）

```text
DATE: 2026-08-09
live tip at probe: c0d5ab339461a91fc5641f8222b39f9c3f5f9898
main product code (narrative): c0d5ab… (#366) · main also has docs #368 (60ee2fe)
fix PR: #370 (revision / negated-multi) — CI green · awaiting independent review
公网: https://pico.aivia.asia
探测: Playwright 公网 UI（登录→对话→结果区下载）· 非 API 冒充
CLAIM-WB: NO · PRODUCT PASS: 未签
```

## H0 · 基线

| 项 | 值 |
|----|-----|
| `GET /api/pico/tip` | `c0d5ab339461a91fc5641f8222b39f9c3f5f9898` |
| 服务 | `pico-api` · `ok: true` |
| 与 main 关系 | 产品码 = #366 合入 SHA；main 另有 docs-only #368 在 tip 之上（未改运行时） |

## 题面

全文见 [prompts.md](./prompts.md)（当场新题 · **非** #367 visit-notes / 金秋邻里集市）。

## 会话

| 链 | URL |
|----|-----|
| H1–H2 | https://pico.aivia.asia/c/aaad2d6a-2bfe-446e-80e8-525ef7c6d1cc |
| H3 四文件 | https://pico.aivia.asia/c/cd797d52-889b-463b-a92a-da139f506404 |
| H4 停止 | https://pico.aivia.asia/c/96b6eeec-eb0c-442e-aea7-94675b56a2a4 |

## 结果（人视角 · tip `c0d5ab…`）

| ID | 结果 | 产物 / 截图 |
|----|------|-------------|
| **H1** | 终态成功 · 真文件可下 | `files/ops-weekly-brief.md` (5438B) · H1-final · H1-390 |
| **H2a** | 同会话改一版成功 | `files/ops-weekly-brief-v2.md` (5895B) · H2a-final · H2a-390 |
| **H2b** | **诚实失败**（旧 tip 误把编号改点当 min=3 多产物；本轮 0 文件） | H2b-final · H2b-390 |
| **H2bR** | 同会话补交写出 v3 文件，但 tip 仍因「不要拆成多个独立文件」误触 multi → 顶栏失败（文件实字节在） | `files/ops-weekly-brief-v3.md` (5042B) · H2bR-* |
| **H3** | 四独立文件一次成功 · 全可下打开 | partner-*.md ×4 · H3-final · H3-390 |
| **H4 停** | 点 aria「停止生成」成功中止 | H4b-running · H4b-after-stop · H4b-390 |
| **H4 找回** | 历史会话 reopen 见 v 链并可再下 | H4-revisit · 再下 v3 |
| **H5** | 无机审主气泡；过程时间线；**≥1 帧 390** | 各 *-390.png |
| **H7** | 通用根因修在 PR #370（非题词 if） | revision 短语 + 否定 multi 剥离 + 单文件名 demotion |

## 根因（H7）

1. **第二轮修改未识别 revision** → 编号改点 structure 抬 `min_artifacts=3` → 假红「需要至少 3 个独立文件」。
2. **「不要拆成多个独立文件」否定句仍命中 multi 语言** → 单文件补交仍 min≥3。

修复（通用，无题词表）：见 PR **#370** · 单测 `tests/unit/test_delivery_policy.py` 全绿。

## 合入后必做

1. 独立审查 #370 → 合 main → `prod-update`
2. 公网 tip = 新 SHA
3. **复点 H2b / H2bR**：同会话两轮改应成功可下，无假红
4. 再请求 Ready

## CLAIM-WB

**NO**
