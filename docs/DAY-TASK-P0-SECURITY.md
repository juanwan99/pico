# 日间任务书 · P0 安全收口（执行）

```
TYPE: DAY
TRACK: P0-SEC
PLAN: docs/P0-SECURITY-HARDENING.md
```

## 【给：② 执行窗 · Codex@ECS】

```text
读 docs/P0-SECURITY-HARDENING.md 全文。
实现 S0–S5（生产 fail-closed、启动校验、demo/注册边界、限流+max_tokens+model 白名单、部署清单）。
单测覆盖：production 拒 pico-dev；model 拒绝；tokens clamp。
PR → CANDIDATE → CI → 等总管审合 → 跳板部署 production env → 等验证窗。
可先合代码再改服务器 .env（PICO_ENV=production 等），部署清单写进 PR。
禁 edu-cloud / PROXY=1 / 打印 key。
P1 项（PG/队列/outbox）不要塞进本 PR。
```

## 【给：③ 验证窗 · 本地】

部署后执行 docs/TEST-TASK-P0-SECURITY.md → ## TEST REPORT。
