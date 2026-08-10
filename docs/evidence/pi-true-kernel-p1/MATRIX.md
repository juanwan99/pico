# P1 验证矩阵 · T-PACK-PI-TRUE-KERNEL-P1

```text
DATE: 2026-08-10
Issue: #431
基线 tip: 27954b2a59a5dcf8f5c57c1d51b176d205ff9e50
执行: Grok
CLAIM-WB: NO · 未切主: YES
```

| ID | 场景 | 过线 | 证据 |
|----|------|------|------|
| P1-T1 | 开放域 ≥1 真文件 | art≥1 · tool 事件 · 门闩 ok | `tests/unit/test_true_pi_p1.py::test_p1_t1_*` |
| P1-T2 | HTML 人页 | generate_html + verify 事件 | `test_p1_t2_*` |
| P1-T3 | cancel / timeout | 可证 · 不污染默认 | `test_p1_t3_cancel` · `test_p1_t3_timeout` |
| P1-T4 | 假绿防护 | min≥2 且 0 写 → failed | `test_p1_t4_*` |
| P1-T5 | 默认路径 | shadow off 时仍 hosted pi-agent | `test_p1_t5_*` · health `default_runtime=pi-agent` |

实现路径：

- ADR: `docs/ADR-PI-TRUE-KERNEL-RPC.md`
- 桥职责: `docs/TRUE-PI-BRIDGE-DUTIES.md`
- 代码: `services/orchestrator/pico_orchestrator/true_pi/*`
- Extension: `services/true_pi_bridge/pico-gateway-tools.ts`
