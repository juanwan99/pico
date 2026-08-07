# 阶段一任务包 · STAGE1-PUBLIC-WB（完整计划）

```text
DOC: docs/PLAN-STAGE1-PUBLIC-WB.md
STATUS: BINDING · 阶段一唯一计划真源
DATE: 2026-08-07
CARD: T-STAGE1-PUBLIC-WB
ACCEPT: docs/ACCEPT-STAGE1-PUBLIC-WB.md
TEST: docs/TEST-TASK-STAGE1-PUBLIC-WB.md
ALIGN: HANDOFF-WB-PI 六条 · PLAN-PUBLIC-WB-LOOP
MODE: 单窗 SOLO · 无人值守 · 自我驱动
```

---

## 0. 阶段目标（业主口径）

```text
从公网 https://pico.aivia.asia 登录后，
用自然语言完成多种真实任务，
行为达到 WorkBuddy 程度六条（Web）。

≠ 说「你好」有回复
≠ loopback / API 绿
≠ 工程门 P0–P2  alone
```

**阶段出口人话：** 外人只拿链接和账号，能自己把任务包干完并拿到真文件。

**阶段结束不自动签** `CLAIM-WB-DEGREE-WEB`（属阶段二）。本包只宣称 **STAGE1_PUBLIC_WB: PASS**。

---

## 1. 锁定句

```text
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO（测→修→装→验→自我验收 串行）
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派
```

---

## 2. 组织法 · 无人值守自我驱动

### 2.1 唯一执行循环（每条小任务强制）

```text
WHILE 小任务 S1.x 未 EXCELLENT:
  1. 公网复现 / 执行该小任务验收用例
  2. 若未达「优秀」→ 定根因 → 最小修复 → CI → exact tip 部署
  3. 同一用例再测
  4. 自我验收打分：EXCELLENT | PASS_WEAK | FAIL
  5. 仅 EXCELLENT 才允许进入 S1.(x+1)
  6. 回写 Issue：## S1.x SELF-ACCEPT
END
全部 S1.1–S1.11 EXCELLENT → ## STAGE1 VERDICT + close 工程门
```

### 2.2 铁律

| 律 | 内容 |
|----|------|
| **优秀门槛** | 见 ACCEPT 文档；**PASS_WEAK 不算完成，禁止跳题** |
| **公网优先** | 主证据必须来自浏览器公网路径；loopback 仅辅助 |
| **一题一闭环** | 未 EXCELLENT 不开下一题 |
| **无人值守** | 不等人催；BLOCKED 仅当缺 DNS/账号/SSH/密钥等外部输入 |
| **不自签产品终局** | 禁止 CLAIM-WB-DEGREE-WEB=YES |
| **假绿禁止** | 禁止用短聊代替交件任务 |

### 2.3 BLOCKED 白名单（仅这些可停）

```text
- 无 pico-prod / edge SSH
- 无演示账号（密码器）
- DNS/证书需业主控制台且执行窗无权限
- 上游 DeepSeek 全区域故障（需书面）
其他：自行修，不得停等聊天
```

---

## 3. 小任务拆解（S1.1 → S1.11 严格顺序）

| ID | 名称 | 对齐六条 | 开发焦点 | 依赖 |
|----|------|----------|----------|------|
| **S1.1** | 公网 TLS+入口 | 底座 | edge 证书含 pico.aivia.asia；无警告打开 /login | — |
| **S1.2** | 登录进壳 | 底座 | 公网登录 → 工作台可输入 | S1.1 |
| **S1.3** | 开放派活 | **1** | 当场交件题自然语言开干 | S1.2 |
| **S1.4** | 多步+真产物 | **3+4** | 工具环可见；docx/html 等可下非空 | S1.3 |
| **S1.5** | 同会话改 | **5** | 第二轮改时间/条款有差异 | S1.4 |
| **S1.6** | 短答纪律 | **4** | 纯数字题不硬塞文件 | S1.2 |
| **S1.7** | Skill 前台 | **2** | ≥3 可见；点选绑定 run | S1.2 |
| **S1.8** | 过程+停止 | **6** | 进行中可见；cancel 成功 | S1.3 |
| **S1.9** | 历史找回 | **5+6** | 历史/任务点回 | S1.5 |
| **S1.10** | 失败诚实 | 诚实 | 中文失败/未命中不装成功 | S1.2 |
| **S1.11** | 方案钉死回归 | 方案 | 仍 pi-agent+DeepSeek；tip 记录 | S1.1–S1.10 |

**允许并行开发准备，禁止并行「宣称完成」：** 完成标记必须按序 EXCELLENT。

S1.6 / S1.7 / S1.10 在 S1.2 后可插空修，但 **正式 SELF-ACCEPT 顺序** 仍建议表序；若 S1.3 阻塞，可先 EXCELLENT S1.6/S1.7/S1.10 再回 S1.3（在 Issue 声明）。

---

## 4. 每小任务工作流模板

```text
## S1.x START
tip_before:
plan:（一行）

## S1.x WORK
（修复摘要 / PR / 部署 SHA）

## S1.x SELF-ACCEPT
grade: EXCELLENT | PASS_WEAK | FAIL
public: yes/no
evidence: run_id / 截图说明 / 文件 hash 前缀
gap:（若非 EXCELLENT 写缺口 → 继续修）
next: S1.(x+1) | retry S1.x
```

---

## 5. 阶段总验收

见 [ACCEPT-STAGE1-PUBLIC-WB.md](./ACCEPT-STAGE1-PUBLIC-WB.md)。

```text
STAGE1_PUBLIC_WB: PASS
  当且仅当 S1.1–S1.11 均为 EXCELLENT
  且 六条对照表全 YES（公网证据）
CLAIM-WB-DEGREE-WEB: NO（本包）
下一阶段: 阶段二打磨 + 业主签章
```

---

## 6. 与旧卡关系

| 旧 | 关系 |
|----|------|
| #318 T-PUBLIC-ENTRY-HOTFIX | **并入 S1.1–S1.2**；#318 可在 S1.2 EXCELLENT 后 close |
| #316 CLAIM | 本包 **不** 签 YES |
| P0–P2 工程门 | 能力底座；**不**替代本包公网任务验收 |

---

## 7. 风险与回滚

| 风险 | 处理 |
|------|------|
| 阿里云 SNI/备案 | 维持 edge；证书必须含域名 |
| 修 UI 破坏 Pi | S1.11 强制回归 |
| 假绿诱惑 | ACCEPT 优秀条否决「仅 API」 |

```
════════════════════════════════════════════════════════
BINDING · STAGE1-PUBLIC-WB PLAN
公网六条 · 小任务串行 · 仅 EXCELLENT 晋级 · 无人值守
════════════════════════════════════════════════════════
```
