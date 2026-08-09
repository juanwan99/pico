# T-LANDING-CLOSE · 公网证据（#376 / #374 · 入库 #377）

```text
DATE: 2026-08-09
merge #375: 20f1712cea0ff9bc0f7732d15cb182a676c31bc2
live tip (probe): 20f1712cea0ff9bc0f7732d15cb182a676c31bc2
remote-health: ok=true · same 40-char
公网: https://pico.aivia.asia
探测: Playwright 公网 UI（登录→当场新题→结果区）+ 账本 artifact 正文
本卡 #377: 纯 docs 证据入库 · 不改产品码
CLAIM-WB: NO · PRODUCT PASS: 未签 · 本窗不自签 Ready
```

## E0 · tip 标注（完整 40 位）

| 项 | 值 |
|----|-----|
| `GET https://pico.aivia.asia/api/pico/tip` | `20f1712cea0ff9bc0f7732d15cb182a676c31bc2` |
| remote-health `git_sha` | `20f1712cea0ff9bc0f7732d15cb182a676c31bc2` |
| 产品码来源 | PR **#375** squash merge（落盘门闩） |
| 三行对齐 | **是** |

## C0–C1（#376）

| 项 | 值 |
|----|-----|
| Merge | #375 → `20f1712cea0ff9bc0f7732d15cb182a676c31bc2` |
| CI | success · [run 31298531722](https://github.com/juanwan99/pico/actions/runs/31298531722) |
| Deploy | prod-update · health.git_sha exact match |

## 会话

| 链 | URL |
|----|-----|
| L4 + L5a + L5b | https://pico.aivia.asia/c/055904fb-3774-49b6-8361-68d5a8889209 |

## 题面（E2）

全文见 [prompts.md](./prompts.md)（当场新题 · 非 visit-notes / 邻里集市）。

## 结果

| ID | UI / 账本 | 产物 / 截图（本目录） |
|----|-----------|----------------------|
| **L4** | 顶栏「已完成 · 1 个可下载文件 · 终态成功」· `workspace_write_file` | [files/property-weekly-outline.md](./files/property-weekly-outline.md) (1558B) · [L4-final.png](./L4-final.png) · [L4-390.png](./L4-390.png) |
| **L5a** | 同会话改版 · 1 个可下载文件 · write v2 | [files/property-weekly-outline-v2.md](./files/property-weekly-outline-v2.md) (1363B · 「设备维保与能耗」+「能耗优化」) · [L5a-final.png](./L5a-final.png) · [L5a-390.png](./L5a-390.png) |
| **L5b** | 诱导只总结 · 右侧「暂无产物」· **不假成功交件** | [L5b-final.png](./L5b-final.png) · [L5b-390.png](./L5b-390.png) · 账本仅 `回复摘要` |

### 账本 run（conversation `055904fb…`）

| run | status | 产物 |
|-----|--------|------|
| `90d9a51c…` | succeeded | `property-weekly-outline.md` |
| `98de457a…` | succeeded | `property-weekly-outline-v2.md` |
| `cf802b36…` | succeeded | 仅 `回复摘要`（无 file 落盘） |

## 截图索引（E3 · 第三人 raw 可读）

| 文件 | 说明 |
|------|------|
| [L4-final.png](./L4-final.png) | 1440×900 · 顶栏可下 + 终态成功 |
| [L4-390.png](./L4-390.png) | 390 宽 |
| [L5a-final.png](./L5a-final.png) | 同会话 v2 |
| [L5a-390.png](./L5a-390.png) | 390 宽 |
| [L5b-final.png](./L5b-final.png) | 只总结 · 暂无产物 |
| [L5b-390.png](./L5b-390.png) | 390 宽 |
| L4/L5a/L5b-sent.png | 发送瞬间（可选） |

合 main 后 raw 示例：

`https://github.com/juanwan99/pico/blob/main/docs/evidence/landing-close/L4-final.png`

## 文件样本（E4）

- [files/property-weekly-outline.md](./files/property-weekly-outline.md)
- [files/property-weekly-outline-v2.md](./files/property-weekly-outline-v2.md)

机器可读摘要：[result.json](./result.json)

## CLAIM-WB

**NO**
