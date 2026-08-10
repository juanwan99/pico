# P2 回归矩阵 · T-PACK-PI-TRUE-KERNEL-P2

```text
DATE: 2026-08-10
Issue: #433
LIVE: PASS (docs/evidence/pi-true-kernel-p2/live-smoke/)
CLAIM-WB: NO
```

| ID | 场景 | 结果 | 证据 |
|----|------|------|------|
| R1 | 多文件 ≥3 | PASS | `test_true_pi_p2.py::test_r1_multi_file_scripted` |
| R2 | 单 HTML | PASS | LIVE L2 + p1 T2 |
| R3 | 恢复/徽章 | N/A | 本卡未改徽章语义；诚实注明 · 不宣称绿 |
| R4 | 闲聊无假成品 | PASS | min_artifacts=0 路径 + hosted 单测 |
| R5 | 假绿多文件 | PASS | `test_r5_false_green_still_blocked` + LIVE L4 |
| R6 | 取消/超时 | PASS | LIVE L3 + p1 T3 |
| R7 | hosted 回滚 | PASS | `test_r7_hosted_rollback_dispatch` · `PICO_HOSTED_LOOP=1` |

## 切主开关（部署层）

```text
PICO_TRUE_PI_DEFAULT=1   # 默认真核
PICO_HOSTED_LOOP=1       # 一键回 hosted
```

公网 tip 在部署含本 tip 的镜像 **且** 设置 DEFAULT 前仍为 hosted。
