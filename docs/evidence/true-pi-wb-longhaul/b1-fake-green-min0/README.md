# B1 · 裸多文件交付 假绿（P0 已复现 → 修复）

```text
DATE: 2026-08-10
tip: 62e1454cf961eb98f0d75734fedb6555c4d93a7c
场景: B1 裸「多文件交付」类题面 · 3 个独立可下载的 Markdown 文件
结果: 复现假绿（min_required=0 且只落 1 文件仍 succeeded）→ 修复 PR 待审
CLONE: 修复前
CLAIM-WB: NO
```

## 题面（开放域新表述）

> 请一次交付 3 个独立可下载的 Markdown 文件：关于「新员工入职培训」的三份材料——①培训日程表 ②培训内容大纲 ③考核清单。每份内容充实、可独立使用，逐份用工具落盘，缺一不可。

## 复现现象（UI）

- 任务历史/终态：**已完成 18s · 1 个可下载文件**（用户要求 3 个）
- 主气泡：模型把 3 份内容**直接贴在聊天代码块**里（"你可以直接复制保存为 .md 文件"），未逐份调写盘工具
- 结果区：只有 **1 个**下载芯片 `新员工入职培训日程表.md`

## 账本（L2 · delivery.summary）

```json
{
  "status": "succeeded",
  "artifact_count": 1,
  "min_required": 0,
  "titles": ["新员工入职培训日程表.md"],
  "multi_deliverable": false,
  "pipeline": false,
  "revision": false,
  "runnable_html": false,
  "implicit_package": false,
  "structure_item_count": 0,
  "prior_artifact_count": 31,
  "ok": true
}
```

run: `dd83e775-dda9-48a1-a449-7e42d635ba1a` · task: `3eab95bd-23f8-4a8f-8d46-3d6ffd8a14a2`
conv: `22679395-13cd-40cc-878d-b70dea52d964`
events: `artifact.created`(日程表) → `artifact.created`(回复摘要) → `delivery.summary`

## 根因

`pico_orchestrator/delivery_policy.py` 的 `_count_explicit_n_files` / `_MULTI_PHRASE` /
`_EXPLICIT_MULTI_FILE` 只接受「N 个[独立][真][可下载]文件」，但自然表述里
「3 个独立可下载**的 Markdown** 文件」在「可下载」与「文件」之间夹了「的 Markdown」
（格式词），导致 `explicit_n=0` → `multi=false` → `min_artifacts=0` →
交付门对"只有 1 文件"放行（假绿）。

```text
修复前: "3 个独立可下载的 Markdown 文件" -> explicit_n=0 min=0 (假绿)
修复后: "3 个独立可下载的 Markdown 文件" -> explicit_n=3 multi=true min=3
```

同类缺口（一起覆盖）：
- 「3 个可下载的 PDF 文件」「3 个 Markdown 文件」「3 份独立的 Markdown 文件」
- 英文「3 separate Markdown files」

## 修复

- 文件: `services/orchestrator/pico_orchestrator/delivery_policy.py`
- 改动: `_count_explicit_n_files` 允许 `个|份` + `(独立|真|可下载){0,3}` + 格式词；`_MULTI_PHRASE` / `_EXPLICIT_MULTI_FILE` 同样放开格式词；英文分支放行 `N separate <format> files`
- 测试: `tests/unit/test_delivery_policy.py::test_multi_deliverable_n_files_with_format_qualifier` (+EN)
- 本地: 44 delivery tests pass · 全量 285 passed · ruff clean
- SHA: `6049351ea67d341c14d5d91dde97e71f51b670a1`（PR 待开）

## 复测（修复后）

待 PR 合入 + 部署后同题新表述复测：应 failed（无 3 文件）或成功（3 文件）。

## 帧

| 帧 | 文件 |
|----|------|
| V2 终态 | [V2-final.png](./V2-final.png) |
| V2 390 | [V2-final-390.png](./V2-final-390.png) |

## 复现 #2（同根因 · ×2 题面）

> 请交付 4 个独立可下载的 Markdown 文件，关于「公司年会筹备」：①年会方案 ②节目单 ③人员分工 ④物料清单。每份内容完整、可独立使用，逐份用工具落盘，缺一不可。

- 结果：**已完成 17s · 2 个可下载文件**（用户要求 4）
- run `a7069fcd-8f95-47df-bce1-7a14e4bbe0b4` · task `f4cb3aad-4419-4153-8c90-d7598ccc7fa5` · conv `fcd9cbb3-aefe-4e46-a7ec-0ef2a7aeb7e3`
- delivery.summary: `artifact_count=2` · `min_required=0` · `multi_deliverable=false` · `ok=true`
- 帧: [V2-final-case2.png](./V2-final-case2.png)
