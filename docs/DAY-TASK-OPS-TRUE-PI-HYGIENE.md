# 日卡 · T-OPS-TRUE-PI-HYGIENE

仓内锚点 · 正文以 [#436](https://github.com/juanwan99/pico/issues/436) 为准。

```text
ID: T-OPS-TRUE-PI-HYGIENE
DATE: 2026-08-10
TYPE: 清债清卫生 · 非加功能
CLAIM-WB: NO
```

## 一句话

换核后去掉过渡态：部署不丢 pi · 默认真核 · 唯一回滚 HOSTED_LOOP。

## 债表

| ID | 处置 |
|----|------|
| D1 部署丢 pi | FIX · compose true-pi + prod-update 校验 |
| D2 开关过渡 | FIX · DEFAULT=1 · 关 CANARY/BYPASS/SHADOW |
| D3 phase 名实 | FIX · hosted-rollback / p2-default / … |
| D4 文档 | FIX · ADR Accepted · OPS 正名 |
| D5 代码卫生 | FIX · 单测 · 7 工具 |
| D6 仓证据 | FIX · 本卡 + 回执 |
| D7 可选 | 延后另卡 |

## 回执

`PACKAGE READY · TRUE-PI-HYGIENE` · 见 Issue #436。
