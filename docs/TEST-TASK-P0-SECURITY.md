# 测试任务 · P0 安全收口

```
TYPE: TEST
PAIR: docs/P0-SECURITY-HARDENING.md
EXEC: ③ 验证窗 · Codex 本地
```

## 用例（部署 production 配置后）

| ID | 步骤 | PASS |
|----|------|------|
| P0-T1 | health 正常；登录演示（若仍开 demo） | 200 / 可进工作台 |
| P0-T2 | 用默认 `Authorization: Bearer pico-dev` 调生产 API（经跳板 loopback 或错误暴露面） | **生产应 401/403** |
| P0-T3 | 未在白名单的 model 名 | 4xx |
| P0-T4 | 超大 max_tokens | 被 clamp 或 4xx |
| P0-T5 | 短时打爆 RPM（脚本） | 429 或明确限流 |
| P0-T6 | 注册入口 | 关闭或不可滥用 |
| P0-T7 | 主路径回归 | 登录+真聊+工具+S7 仍 PASS |
| P0-T8 | 端口 | 18765/8080/27017 公网关 |

## 报告

`## TEST REPORT` 贴在 P0 实现 PR。verdict PASS 后总管才认「公网可继续开的安全底线」。
