# ACCEPT · T-CAP-GENERAL-P1

```text
仅 EXCELLENT 晋级 · 捷径一票否决 · CLAIM-WB: NO
```

## 捷径否决 X1–X4（同 P0，加重）

| ID | 否决 |
|----|------|
| X1 | 已知考题/旧回归题专名特判 |
| X2 | 测试/生产交付策略分叉偷懒 |
| X3 | 降 ACCEPT 或假成功 |
| X4 | 说不清「任意同类意图」 |
| **X5** | 隐式包装题失败，仅显式「3 个独立文件」题通过却报 H1 PASS |

## H0

| EXCELLENT |
|-----------|
| 余量表：P0 黄项 → 代码 → 本卡动作 → 不做 |

## H1 隐式多交付

| EXCELLENT |
|-----------|
| 无「N 个文件」字样的包装意图仍 `multi_deliverable` 或 min≥2 |
| 单测覆盖≥3 条中性包装句（方案包/套件/全套/从A到B材料） |
| 公网**隐式**新题 PASS |

## H2 中性化

| EXCELLENT |
|-----------|
| 过贴场景词删除或降权有 diff |
| HTML 触发不依赖单一场景名词 |
| 单测无「倒计时」作为**必要**触发 |

## H3 可运行分层

| EXCELLENT |
|-----------|
| 报告含 verification_level 或等价 |
| L0/L1/跳过/失败语义不混淆成「全完美」 |

## H4 完成信号

| EXCELLENT |
|-----------|
| 探针或脚本演示：用 summary/status 判完成，而非唯一 sleep |
| 文档一行：客户端应如何订阅 |

## H5 修订

| EXCELLENT |
|-----------|
| 软改口用例单测或公网题 PASS |
| 无业务固定句特判 |

## H6 工程环

| EXCELLENT |
|-----------|
| 工程意图 force_agent / 禁无工具假交付 有测 |

## H7 开放回归

| EXCELLENT |
|-----------|
| ≥4 新题：隐式包装、流水线软修订、中性 HTML、默认闲聊 |
| 禁 P0 N 原文 / W 原文 |
| 默认不改模型 |

## H8

| EXCELLENT |
|-----------|
| PRODUCT sha · 反捷径表 · CLAIM NO |

```text
CAP_GENERAL_P1: PASS ⇔ H0–H8 EXCELLENT 且无 X1–X5
```
