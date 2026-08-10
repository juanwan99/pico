# 验证矩阵 · T-TRUE-PI-WB-LONGHAUL

```text
DATE: 2026-08-10
Issue: #438
执行: DS
tip（开工 A0）: add0ad8625b961eed56a040d992b6b1a836ec255
tip（部署后）: 62e1454cf961eb98f0d75734fedb6555c4d93a7c（PR #439 合入后）
default_runtime: pi-true
true_pi_binary_available: true
true_pi_hosted_loop_forced: false
CLAIM-WB: NO
```

## 总览（执行中逐项填充）

| ID | 场景 | 结果 | 证据路径 | EXCELLENT 锚 |
|----|------|------|----------|--------------|
| A0 | tip/运行时/二进制实查 | PASS | 开工 add0ad8 → 部署后 62e1454 · pi-true · binary=true · HOSTED_LOOP=off | |
| A1 | 部署不丢 pi | PASS | prod-update 全链跑通 · health true_pi_binary_available=true · PR #439 DEPLOYED | |
| A2 | 健康字段一致 | PASS | default_runtime=pi-true · true_pi_default_enabled=true · phase=p2-default | |
| B1 | 裸多文件 ×2 | | | |
| B2 | min 冲突 | | | |
| B3 | 禁落盘诱导 | | | |
| C-W1a | 习惯打卡小工具 | | | W1.1–W1.6 |
| C-W1b | 另一小工具（加码） | | | 同左 |
| C-W1-fix | 报错同会话修 | | | W1.4+五项 |
| C-W2a | 小说流水线 | | | W2.1–W2.5 |
| C-W2-续 | 继续写第四章 | | | W2.6 |
| C-W2b | 另一题材（加码） | | | |
| C-W3a | Skill 规格+实测 | | | W3.1–W3.4 |
| C-W3b | 另一 Skill（加码） | | | |
| C-W4a | 作品包+未渲染 | | | W4.1–W4.4 |
| C-W4b | 另一主题（加码） | | | |
| C-W5a | 脏活四件套 | | | W5.1–W5.2·W5.4 |
| C-W5-联动 | 改①同步 | | | W5.3 |
| C-W5b | 另一决策链（加码） | | | |
| D1 | HTML 人页非源码墙 | | | A1–A4 |
| D2 | 多文件芯片无 ID | | | A1–A2 |
| D3 | 闲聊无假条 | | | A3 |
| D4 | 390 宽抽 3 帧 | | | |
| E1 | 恢复链+徽章 | | | |
| E2 | 终态=账本 | | | |
| E3 | cancel/停止 | | | |
| F1 | ≥8 工具大包 | | | |
| F2 | max_steps 逼近 | | | |
| F3 | 超长正文 token | | | |
| F4 | 连续 3 题不重登 | | | |
| G1 | 开放域可玩 ×3 | | | |
| G2 | 一周启动包 ≥4 文件 | | | |
| G3 | 改一版 ×2 | | | |
| H1 | 轻回归 B1+D1+C-W5 | | | |
| H2 | 开关仍真核 | | | |
| H3 | 证据索引 | | | |
| H4 | #436 D 顺手灭 | | | |

## 结语（回执时填充）

```text
EXCELLENT: W1..W5 =
BLOCKED:
请求: PACKAGE READY · TRUE-PI-WB-LONGHAUL / REVISE
CLAIM-WB: NO
```
