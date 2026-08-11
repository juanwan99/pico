# MATRIX · T-PACK-UX-HARDEN (#447)

```text
DATE: 2026-08-11
执行: Grok
公网 tip: 502e1f6fd5d3f5999b43303de91b16de1375f26a
PR-1.1: SKIP（Phase1 无需改码）
PR-1.2: #450 → merge b6e8eb815b27c091cdd926c7c6d64fb8f8dcc332
CLAIM-WB: NO
```

| ID | 结果 | 路径 | tip | 自读图要点 |
|----|------|------|-----|------------|
| **U1** | **PASS** | [u1-fail-human/](./u1-fail-human/) | 502e1f6… | 侧栏 fail-hint 中文「服务维护或重启…重新运行」· 无 owner was lost |
| **U2** | **PASS** | [u2-dual-stop/](./u2-dual-stop/) | 502e1f6… | 停止任务可见 · 停止生成 aria「仅停屏幕输出…」 |
| **U3** | **PASS** | 同 U1 列表 | 502e1f6… | 失败列表人话覆盖 · 见 teacher-task-fail-hint |
| **U4** | **PASS** | [docs/RUN-DRAIN-AND-STOP.md](../../RUN-DRAIN-AND-STOP.md) | docs@b6e8eb8 | drain 45s · grace 60s · 双停止 · 诚实维护 |
| **U5 HTML** | **PASS** | [u5-mendel/](./u5-mendel/) | 502e1f6… | human_page=true · 孟德尔 HTML 可打开 |
| **U5 多文件** | **PASS** | [u5-multifile/](./u5-multifile/) | 502e1f6… | 4 文件芯片 ≥3 |
| **U5 闲聊** | **PASS** | [u5-chat/](./u5-chat/) | 502e1f6… | 右栏暂无产物 · 无假交付条 |

## 出口自检

- [x] U1–U2 专用帧
- [x] U5 三回归
- [x] PR-1.1 SKIP · PR-1.2 合 · PR-1.3 本目录
- [x] CLAIM-WB: NO

审查必须 **读图**；只读本表 = 审查无效。
