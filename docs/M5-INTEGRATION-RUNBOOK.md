# M5 Integration Runbook（Pico 侧 · 真连前必读）

```
DOC: docs/M5-INTEGRATION-RUNBOOK.md
STATUS: READY-FOR-OWNER-AUTH
REPO: juanwan99/pico ONLY
HARD: 永不写 edu-cloud 仓；M5 授权 = Pico→edu HTTP 调用权，不是 edu 仓写权
DEFAULT_PROD: PICO_EDU_MODE=fake · handoff off
```

## 0. 何时才能开跑

```text
□ 业主书面授权「允许 Pico 调用 staging edu」
□ staging base URL + service token 已进服务器 env（禁止贴进聊天/PR）
□ JWT 密钥/issuer 与 edu 约定一致（HS256 或 RS256 PEM）
□ 回滚方案：一键回到 fake（见 §5）
□ 本 runbook + M5-API-CHECKLIST 已读
```

未勾满 → **只做文档/桩，不设 live。**

## 1. 环境变量（Pico）

| 变量 | 含义 | 生产默认 |
|------|------|----------|
| `PICO_EDU_MODE` | `fake` \| `live` | **fake** |
| `PICO_EDU_BASE_URL` | edu staging 根 URL | 空 |
| `PICO_EDU_SERVICE_TOKEN` | Pico→edu 服务凭证 | 空 |
| `PICO_EDU_TIMEOUT_SECONDS` | HTTP 超时 | 10 |
| `PICO_EDU_HANDOFF_ENABLED` | confirm 后是否 POST handoff | **false** |
| `PICO_EDU_ISS` / `PICO_EDU_JWT_SECRET` / PEM | 验 edu 签发 JWT | 空则仅 test issuer |
| `PICO_ACCEPT_TEST_ISSUER` | 是否仍收 pico-test | 联调稳定后考虑 false |

## 2. 推荐阶段

### Phase R1 — 只读（第一刀）

1. staging only；生产仍 fake（或生产另令）  
2. `PICO_EDU_MODE=live` + base + token  
3. 验证：`fake_edu_list_classes` 名下工具返回 **source=edu_live** 与真数据形状  
4. 断网/4xx → **明确错误**，禁止静默假数据  
5. JWT：edu 签发 token 可过；跨校/过期拒绝  

### Phase R2 — S7 写（第二刀）

1. `PICO_EDU_HANDOFF_ENABLED=true`（仅 staging）  
2. 用户确认 Change → handoff envelope  
3. edu 返回 `edu_review_id` + `accepted_for_review`  
4. 失败写 `handoff_failed` 审计；不重试死循环  
5. **禁止** 绕过 S7 写成绩/班级  

### Phase R3 — 生产放量

1. 独立变更窗；关或收紧 test issuer  
2. 监控与回滚演练通过  
3. 文档与 CANDIDATE 证据  

## 3. 部署检查（服务器）

```bash
cd /opt/pico
grep -E 'PICO_EDU|PICO_ACCEPT' .env | sed 's/=.*/=***/'   # 勿打印密钥
curl -sS http://127.0.0.1:18765/health
# 确认容器仅 127.0.0.1 监听
ss -lntp | grep -E '18765|8080|27017'
```

## 4. 验收命令（示例）

```bash
PICO_SELFTEST_API_ONLY=1 bash scripts/agent-selftest.sh
# 另：只读工具 live 用例（授权后由实现窗补充）
```

## 5. 回滚（必须可 1 分钟完成）

```bash
# .env
PICO_EDU_MODE=fake
PICO_EDU_HANDOFF_ENABLED=false
# 重建/重启 pico-api
curl -sS http://127.0.0.1:18765/health
```

## 6. 角色

| 角色 | 做 |
|------|-----|
| 业主 | 授权 staging/生产 live |
| Pico 窗 | 只改 pico 仓与服务器 env |
| edu 窗 | 改 edu-cloud、签发、业务提交 API |

## 7. 相关

- [M5-API-CHECKLIST.md](./M5-API-CHECKLIST.md)  
- [PHASE3-INTEGRATION.md](./PHASE3-INTEGRATION.md)  
- [ADR-SKILL-CATALOG.md](./ADR-SKILL-CATALOG.md)（能力中心嵌工具，不造 edu 站）  
