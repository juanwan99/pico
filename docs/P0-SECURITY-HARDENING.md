# P0 安全收口 · 公网可继续开但必须 fail-closed

```
DOC: docs/P0-SECURITY-HARDENING.md
STATUS: OPEN · 总管派工（吸收 Codex 体检 5757b05 基线）
DATE: 2026-07-30
PRIORITY: 高于轨 C 加厚 / 高于 M5
TOTAL: Grok
EXEC: ② Codex@ECS（实现+部署）
TEST: ③ Codex 本地（真实验证）
```

## 0. 体检共识（总管采纳）

Pico 现为 **有真实垂直链路的 MVP**，**不适合**承载真实学校数据或「裸默认」开放公网。  
成员级 Artifact 隔离与 allowlist 工具方向正确；下列 **P0 必须先收口**。

来源：Codex 深审（基线 7383127→复核至 5757b05 schema 热修后结论仍成立）。

## 1. P0 必做（本切片 · 一个或两个 PR）

| ID | 项 | 验收 |
|----|-----|------|
| S0 | **生产配置 fail-closed** | `PICO_ENV=production` 时：拒绝默认 `pico-dev` JWT、拒绝空/弱 `JWT` 密钥、拒绝 `PICO_ACCEPT_TEST_ISSUER=true`（除非显式 break-glass 且打日志） |
| S1 | **启动校验** | 生产缺 `SECRET`/`JWT`/模型 key 策略时 **拒绝启动**（清晰错误） |
| S2 | **演示账号边界** | 文档+配置：公网关闭开放注册 **或** 注册必须强验证；固定密码账号仅 `PICO_DEMO_SEED=1` 且 production 默认关；README/DEPLOY 写明 |
| S3 | **聊天成本边界** | 全局限流（IP 或 membership）：RPM + 并发；`max_tokens` 上限；**禁止** 绕过全局 cap；usage 尽量如实（至少不恒 0） |
| S4 | **model 白名单** | 生产只允许配置列表内 model；未知 model → 4xx |
| S5 | **生产部署核对清单** | `docs/DEPLOY-PROD-CHECKLIST.md`：env 样例 production、禁止项；执行窗部署后勾选 |

### 明确本切片不做（记入 backlog）

- PostgreSQL 迁移、outbox、任务队列、Kimi CLI 路线二选一重构 → **P1 下一窗**  
- 依赖 CVE 全清 → P1（可先文档记录 Kimi CLI 未进运行路径）  
- LibreChat 完整 npm CI → P1  

## 2. 实现提示（路径）

- `services/api/app/settings.py` — pico_env 默认勿在 production 镜像里 development  
- `services/api/app/auth.py` / `openai_compat.py` — pico-dev 仅 non-prod  
- 限流：可用 slowapi/内存令牌桶（单实例可接受）+ 配置项  
- LibreChat：`ALLOW_REGISTRATION` 等 env 在 compose/production 文档中默认 false  

## 3. HARD

- 只 pico 仓；禁 edu-cloud；禁 PROXY=1；禁打印密钥  
- 不自 PASS 产品终局；合 main 走审查  
- 生产仍可演示，但 **默认攻击面缩小**

## 4. 给 ② 执行窗

见下文任务块（总管消息同步）。

## 5. 给 ③ 验证窗

`docs/TEST-TASK-P0-SECURITY.md`
