# 执行窗任务队列（历史 · 已降级）

```
DOC: docs/EXECUTION-QUEUE.md
STATUS: SUPERSEDED for auto-dispatch · HISTORICAL queue log retained
ROLE: 曾用于 E1/E2/E3 定时认领；**2026-08-01 起不再作为现行派工权威**
CURRENT_DISPATCH: 总管标准任务卡 → 窗口 1 / 2 / 3（见 docs/STATE-NOW.md）
PAIR: docs/VALIDATION-QUEUE.md · docs/SPRINT-FAST.md · docs/ONEFLOW.md
```

## 0. 现行规则（覆盖下文自动派工叙事）

1. **不要**假设 E1/E2/E3 心跳会自动领任务。  
2. **不要**只根据本文件 `status:OPEN` 开工；以总管在 Issue/聊天下发的**标准任务卡**为准。  
3. 槽位名：**窗口 1、窗口 2、窗口 3**（与旧 E1/E2/E3 编号无自动对应义务）。  
4. 当前 P0 见 `docs/STATE-NOW.md`（#142/#143/#144 日用；KA-3 未授权）。  
5. 下文 §1–§4 保留为 **历史队列与机制说明**，防止误读旧 done_note；**新任务不要再追加进本文件当作自动队列**（应开 Issue）。

---

## 1. 历史机制（归档说明）

```text
（旧）总管改本文件 → 合 main → 三窗 git pull 认领
（新）总管写 Issue + 标准任务卡 → 窗口执行 → PR/Issue 回写
```

**上下文：** 默认 **不清理**（`context_reset: false`）。详见 [`docs/CONTEXT-POLICY.md`](./CONTEXT-POLICY.md)。

---

## 2. 历史三窗身份（勿再当现行 ID）

| 旧窗 ID | 曾用职责带 | 现行 |
|---------|------------|------|
| E1 | API / orchestrator | 改称 **窗口 n** 由任务卡指定 |
| E2 | LibreChat UI | 同上 |
| E3 | 部署 / 文档 | 同上 |

---

## 3. 认领规则（仅历史）

旧 `## CLAIM E?` 评论若出现在新 Issue，视为**噪音**；以任务卡 `window: 1|2|3` 为准。

---

## 4. 历史队列条目（只读摘录）

> 完整 YAML 条目曾用于 2026-07-31 前后手动/半自动派工。  
> **EQ-031** 等 DONE 记录中的生产 SHA（如 `768d0bd…`）为**当时**部署证据，**不是** 2026-08-01 当前生产 SHA。  
> 当前生产应用 SHA 以最新 `## TEST REPORT` / health 为准（见 STATE-NOW：`ddf269b…` 量级）。

### EQ-031 · 部署最新可靠性与清理主线（历史 DONE）

```yaml
id: EQ-031
status: DONE
done_note: "2026-08-01 historical deploy evidence at 768d0bd… — DO NOT treat as current prod SHA"
priority: P0
task_type: DEPLOY
title: （历史）部署 main 并回写生产证据
```

**现行部署意图：** 未授权前 **不要** 为 KA-2 开 flag 或宣称换核部署。日用 FIX 合入后再走 OneFlow 部署门禁。

---

## 5. 禁止

- 用本文件复活「自动三窗轮询即派工」  
- 把历史 `768d0bd…` 写成当前生产  
- 在本文件预埋 Plan B / 第二运行时  
- 写 edu-cloud  
