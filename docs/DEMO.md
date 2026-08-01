# Pico 演示路径（当前壳 · 2026-07-30）

```
DOC: docs/DEMO.md
SHELL: apps/librechat @ :8080
API: 127.0.0.1:18765
PLAN: MVP v1.2 FIXED
NOT: 网盘 · 教务 SaaS · edu 联调 · 自 PASS
STATUS: 演示说明（非 PASS 证书）
```

> 过时句（NextChat / make product :8000）已废。启动以 `scripts/run-product.sh` / `startup.sh` 为准。  
> 全景：`docs/archive/CALIBRATION-NOW.md` · 总控：`docs/archive/ORCHESTRATION-PLAN.md`

---

## 生产入口（业主）

- **https://pico.aivia.asia/login**（HTTPS only）
- 演示凭据由管理员临时创建并通过安全渠道提供；仓库不保存固定密码。
- 模型 key 在服务器 `/opt/pico/.env` 的 `KIMI_API_KEY`（不进 Git）

## 30 秒启动（沙箱 / 本机 agent）

```bash
# 仓库根；.env 含 KIMI_API_KEY
bash scripts/run-product.sh
# 产品 UI
curl -sf http://127.0.0.1:8080/ | head -c 200
# API
curl -sf http://127.0.0.1:18765/health
```

| 面 | 地址 |
|----|------|
| 产品 UI | **http://127.0.0.1:8080**（预览须 pin 8080） |
| LibreChat | :3080 |
| Pico API | **仅** 127.0.0.1:18765 |
| 演示登录 | 设置 `PICO_DEMO_SEED=1`、临时邮箱和 12 位以上随机密码；演示后关闭 |

**Live Preview：** 若经 :6014 且无鉴权，常见 403 空 body = 纯白；**不等于**产品挂。详见 `PREVIEW-WHITE-SCREEN.md`。

---

## 模型路径（S2 叙事 · 必读）

| 模型选择 | 行为 | 对应 |
|----------|------|------|
| **kimi-k2.6 / Kimi-K3 / moonshot-***（默认聊天） | **直连 Kimi HTTPS**，流式对话；账本仍记 Task/Run | **S1 主路径** |
| **pico-agent** | **钉版本 Kimi Agent 多步工具环**（allowlist：echo / FakeEdu 班级 / 提案） | **S2 编排路径** |

- 编排 runtime 钉死：`kimi-agent-sdk==0.0.5`、`kimi-cli==1.12.0`（`pico_orchestrator.pins`）  
- Shell / 主机 File / 开放 Web / MCP：**默认关**  
- **不要**把「默认能聊」说成「默认多步 Agent」——二者模型入口不同  

---

## 现场路径（产品 UI · ~3 分钟）

| 步 | 操作 | 期望 |
|----|------|------|
| 1 | 打开 8080 → 登录演示账号 | 中文登录 / 任务台首页 |
| 2 | 首页发「只回：演示OK」 | 流式或完整回复；结果区可有摘要 |
| 3 | 发「创建 hello.txt，内容为 hi」 | 结果区出现 **hello.txt** |
| 4 | （可选）模型选 **pico-agent** 再发简单任务 | 工具环/Agent 路径（若环境允许） |
| 5 | 侧栏打开项目 / 自动化 | 可导航；自动化需登录态 JWT |
| 6 | 任务页「新建演示提案」→ 确认/拒绝 | S7：状态 confirmed/rejected；无业务写库 |

### API 快速证据

```bash
# S1
curl -sS -H 'Authorization: Bearer sk-pico-dev' -H 'X-Pico-Membership-Id: demo' \
  -H 'Content-Type: application/json' \
  -d '{"model":"kimi-k2.6","stream":false,"messages":[{"role":"user","content":"【Pico-User:demo】只回：演示OK"}]}' \
  http://127.0.0.1:18765/v1/chat/completions

# 未登录账本代理须 401
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3080/api/pico/v1/tasks
```

主路径勾选清单：`docs/archive/REGRESSION-MAINPATH.md` · 最近实跑：`docs/archive/REGRESSION-MAINPATH-RUN.md`

---

## 门禁状态（诚实）

| ID | 演示？ |
|----|--------|
| S1 真模型 | 是（默认 Kimi） |
| S2 Agent 多步 | **显式选 pico-agent**；非默认 |
| S3 账本 | 是 |
| S5 UI | 是（LibreChat 任务台） |
| S7 人确认 | **最小闭环**：任务页横幅「新建演示提案」→ 确认/拒绝；仅审计不写学校库 |
| S8 合 main | 分支 CANDIDATE 流程，**不自 PASS** |

---

## 一句话对外

> Pico 是独立 AI 工作台：LibreChat 壳 + 服务端账本 + Kimi 真模型；默认直连对话，编排走 `pico-agent`；今天不连 edu，不宣称 Live Preview 在无鉴权代理下必通。
