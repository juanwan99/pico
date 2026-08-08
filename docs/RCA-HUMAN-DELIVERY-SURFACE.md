# RCA · 用户窗机器向 / 无可用交付

```text
STATUS: BINDING 分析
DATE: 2026-08-08
TRIGGER: 业主 — 无可用成果却审查 PASS；机审标准进用户窗；对比 Grok 人包 vs 源码墙
CLAIM-WB: NO
```

## 0. 业主成功标准（唯一）

```text
提示完成 → 公网 UI 可见可下载/可预览文件（文件名优先）
         → 本机打开人能用
缺任一环 = 交付失败
Artifact ID / L0 / run id / 源码墙  ≠ 交付
```

---

## 1. 现象（已确认）

| ID | 现象 |
|----|------|
| P1 | 用户窗出现 Artifact ID、L0/L1、encoding、账本、not_run 等 **机审话术** |
| P2 | 用户 **拿不到** 可点下载的可用成果（或主路径不清晰） |
| P3 | 有时整页 HTML **源码进聊天**（DeepSeek 式）而非文件 |
| P4 | 工程/部署审查曾 **PASS**，与业主「手里没有文件」冲突 |

---

## 2. 因果链（端到端）

```text
用户要课件
  → delivery_policy 判 runnable/engineering
  → system + 【工程交付纪律】注入 Pi
  → 工具: generate_* → Artifact 账本 (有 artifact_id)
  → verify_html → 返回 verification_level / interaction_status
  → 模型把工具 JSON + 纪律话术 写成 final_text
  → LibreChat 只渲染 final_text（及有限附件桥）
  → 用户看见：体检报告 / ID / 或源码墙
  → 用户看不见：一等公民「下载按钮 + 文件名」
```

**断点 A（话术）：** 对内诚实指标 **没有独立通道**，挤进 `final_text`。  
**断点 B（交付）：** 账本有字节 **≠** 门脸 UI 有下载。  
**断点 C（审查）：** 验收采信 API/执行窗打开，**未一票否决「业主 UI 不可得」**。

---

## 3. 根因分层（禁止表面归咎）

### R1 · 成功标准被「机读验收」替换（战略）

| | |
|--|--|
| **错** | 绿 = min_artifacts + L0 + run.succeeded + 执行窗本机打开 |
| **对** | 绿 = **业主（或公网登录 UI）拿得到并打开能用** |
| **证据** | CAP/部署卡允许 API 冒烟；「人类打开:Y」常为测试员路径 |
| **不是** | 「用户不懂 Artifact」——是产品把内部概念当交付 |

### R2 · 单通道输出：聊天 = 唯一用户面（架构）

| | |
|--|--|
| **事实** | `delivery.summary` / verify 字段进 **事件与工具结果**；模型被要求「如实汇报」→ 写入 **用户可见 final_text** |
| **代码倾向** | `system.md`: verify 后 *report* pass/fail；`delivery_policy` 指令含 L0/not_run/**Artifact 账本** 措辞 |
| **缺失** | 无 `user_facing_summary` vs `engineer_trace` 分流；无 final_text 机审字段剥离 |

### R3 · 提示词把「防假绿」写成「对用户念经」（实现）

```text
防假绿目标正确
实现错误：把 L0/L1/账本 写进面向用户的 system/skill 指令
模型最优策略：复读指令语言 → 用户窗变审查报告
```

涉及（概念位置，合入后以 main 为准）：

- `agent_assets/system.md` · Runnable HTML → report honestly  
- `delivery_policy._build_instruction` · 【工程交付纪律】含 L0/账本/not_run  
- `verify_html_document` 工具描述与返回值充满机读字段  

### R4 · 账本优先、门脸下载未一等公民（产品缺口）

```text
LedgerArtifactStore 写入成功
  ≠ LibreChat 消息附件 / 下载链 / 预览
工具回传 artifact_id 给模型
  ≠ 用户气泡里的「下载：xxx.html」组件
```

若桥接弱或仅 API 可 read artifact → **工程有文件、用户无文件**。  
这是 P2 的根，不是「再强调一次必须写入账本」能单独修好的。

### R5 · 源码墙双形态（生成 + 展示）

| 形态 | 根因 |
|------|------|
| 下载后打开是转义散文 | #342 已修生成器（须保持） |
| **聊天里贴全量 HTML** | 模型把「交付」理解成「输出代码」；缺 **禁止主气泡贴全量源码** 的硬约束与后处理 |

### R6 · 审查共谋（流程）

总管/部署卡在无公网演示登录时放行 API 路径 → **强化了「后端绿=产品绿」**。  
相对业主标准，属 **验收设计错误**，不是业主苛刻。

---

## 4. 非根因（避免打错地方）

| 不要当成主因 | 为什么 |
|--------------|--------|
| 用户不会看 ID | 用户不该需要看 |
| 再加更长 L0 表格 | 加重 P1 |
| 只改文案润色 | 不修断点 B |
| 回退 #342 / 取消 verify | 防假绿仍需要，但应 **对内** |
| 再堆 delivery_policy 业务词 | 与人本交付无关 |

---

## 5. 修复原则

```text
1. 对系统诚实 ≠ 对用户宣读体检单
2. 账本是存储；下载组件是交付
3. final_text 默认「人包」；机审只进日志/事件
4. 公网 UI 不可得 = 产品 FAIL（一票否决）
5. 禁止主气泡全量源码当交付
```

详见 `docs/PLAN-HUMAN-DELIVERY-SURFACE.md`。
