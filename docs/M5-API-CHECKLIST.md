# M5 API / 合同检查清单（Pico 视角）

```
DOC: docs/M5-API-CHECKLIST.md
STATUS: CHECKLIST
PAIR: docs/M5-INTEGRATION-RUNBOOK.md
```

## JWT / principal

| # | 检查 | 状态 |
|---|------|------|
| J1 | claims 含 school_id、membership_id、scopes 数组 | □ |
| J2 | scopes ⊆ {ai:read, ai:run, ai:confirm, ai:admin} | □ |
| J3 | iss 匹配 edu issuer；aud 匹配 Pico | □ |
| J4 | 过期 → 401 | □ |
| J5 | 跨校 membership 头与 token 不一致 → 拒 | □ |
| J6 | test issuer 在 edu_only 模式关闭 | □ |

## 只读工具

| # | 检查 | 状态 |
|---|------|------|
| R1 | live 缺 BASE_URL/token → fail-closed | □ |
| R2 | 成功响应可映射 list_classes 形状 | □ |
| R3 | 上游 5xx → tool.upstream_error 类错误 | □ |
| R4 | fake 模式零出站 | □ |
| R5 | 至少 2 个只读工具合同一致 | □ |

## Change handoff

| # | 检查 | 状态 |
|---|------|------|
| H1 | envelope 过 change-handoff schema | □ |
| H2 | 仅 confirm 后推送 | □ |
| H3 | 跨校 body 拒绝 | □ |
| H4 | 响应 edu_review_id + accepted_for_review | □ |
| H5 | 失败可审计 handoff_failed | □ |
| H6 | 幂等键/重试策略与 edu 约定 | □ |

## 安全与拓扑

| # | 检查 | 状态 |
|---|------|------|
| S1 | API/Mongo/LibreChat 仅 loopback | □ |
| S2 | 密钥不在 git | □ |
| S3 | 未写 edu-cloud | □ |
| S4 | 生产默认 fake 直至放量令 | □ |

## 嵌入工作台（非新壳）

| # | 检查 | 状态 |
|---|------|------|
| U1 | 只读结果进任务区/右栏 | □ |
| U2 | S7 横幅同 change id | □ |
| U3 | 能力中心展示 edu 工具为连接器/技能而非独立站 | □ |
