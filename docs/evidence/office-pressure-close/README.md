# T-OFFICE-PRESSURE-CLOSE · 公网 UI 证据

```text
DATE: 2026-08-09
merge #366: c0d5ab339461a91fc5641f8222b39f9c3f5f9898
live tip / main / health: c0d5ab339461a91fc5641f8222b39f9c3f5f9898
公网: https://pico.aivia.asia
CLAIM-WB: NO · PRODUCT PASS: 未签
探测: Playwright 公网 UI（登录→对话→结果区）· 非 API 冒充
```

## C0–C1

| 项 | 值 |
|----|-----|
| Merge | PR #366 → main `c0d5ab33…` |
| Deploy | `prod-update` · health.git_sha exact match |
| Public tip | `GET https://pico.aivia.asia/api/pico/tip` → same 40-char |

## O 题面

全文见 [prompts.md](./prompts.md)（当场新题 · 非 #360 F4b）。

## 结果

| ID | UI | 产物 | 截图 |
|----|----|------|------|
| O1 | 终态成功 · 1 文件 | `files/visit-notes.md` (2655B) | O1-final.png · O1-390.png |
| O2 | 同会话改版成功 | `files/visit-notes-v2.md` (3300B · 含 4→6 工作日 + 法务条款) | O2-final.png · O2-390.png |
| O3 | 终态成功 · 3 文件 | 规则/排班/短讯 三份 | O3-final.png · O3-390.png |

Ledger（生产，成功 run）：
- `2ef074ff…` visit-notes.md succeeded
- `aaf938cf…` visit-notes-v2.md succeeded  
- `204f6b16…` 三文件 succeeded

会话 URL（公网）：
- O1/O2: `/c/7ce249de-6b8f-4dbf-bf4a-2d56bb3cf076`
- O3: `/c/7cc279e7-1b3c-4cb2-a0f5-590a58fbbd20`

## O4 交互

- 主气泡：人包（文件名、结构、如何下载），非机审字段墙
- 过程：右侧时间线可见步骤（非主气泡工具刷屏）
- 顶栏：已完成 · N 个可下载文件 · 终态成功
- 390：O1/O2/O3-390.png

## CLAIM-WB

**NO**
