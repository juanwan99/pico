# 标准任务卡 · T-E2E-DEFAULT-CHAT

```
ID: T-E2E-DEFAULT-CHAT
PRIOR: #322 业主红 · 默认 kimi 闲聊失败
PLAN: docs/PLAN-E2E-DEFAULT-CHAT.md
ACCEPT: docs/ACCEPT-E2E-DEFAULT-CHAT.md
TEST: docs/TEST-TASK-E2E-DEFAULT-CHAT.md
```

```text
════════════════════════════════════
标准任务卡 · T-E2E-DEFAULT-CHAT
════════════════════════════════════
执行窗：SOLO（唯一）
上下文：KEEP
角色：端到端热修+验收 · 无人值守 · 总管核真源
RISK: 红（默认模型/鉴权/门脸）
FAST: YES
仓：https://github.com/juanwan99/pico
载体回写：（Issue）
BASE：  55f861db70a1096cb24847eb40f14286dc5e8e6d
PRODUCT：55f861db70a1096cb24847eb40f14286dc5e8e6d
关联：#322 业主红 · #316 CLAIM 冻结 · PLAN/ACCEPT/TEST-E2E

【锁定句】
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO · 公网端到端默认路径
不做：Dify 门脸 · 场景卷对标 · 双核真源 · 多窗碎派

【你是谁】
SOLO：修默认闲聊+品牌+密钥路由 → 强制 E2E-DEFAULT →
默认路径交件/短答/失败 → 证据 → 请业主同路径复测。
禁止用「交件管线绿」冒充默认闲聊绿。
禁止自签 CLAIM-WB=YES。

【真源】
PLAN-E2E-DEFAULT-CHAT → ACCEPT → 业主截图红 → 本卡 → GitHub

【目标】
公网默认路径端到端可用：不改模型也能问、能答、能交件。
人话：业主「你是什么模型」不再报错；顶栏不是坏 Kimi。

【IN】
0 读 PLAN+ACCEPT；校准 tip
E0 复现业主红 + 根因（日志无密钥）
E1 默认模型/endpoint → DeepSeek（或声明可用默认）；禁坏 kimi 默认
E2 修密钥/路由使默认流式通
E3 UI 品牌/模型名与真实一致
E4 **E2E-DEFAULT D1–D8 全绿**（一票否决 · 无痕/不改模型）
E5 默认路径交件真文件
E6 默认路径短答 42
E7 默认路径失败诚实+再试
E8 pi-agent + 交件纪律回归
E9 证据包 + 请业主同路径复测
每条 ## Ex SELF-ACCEPT 仅 EXCELLENT 晋级

【OUT】
- 只测 Agent 交件、不测默认顶栏
- 手动改成 DeepSeek 再测冒充默认
- PASS_WEAK 晋级 / 自签 CLAIM
- 密钥进 Issue

【验收】
1. E0–E9 全 EXCELLENT
2. E2E-DEFAULT D1–D8 全 PASS（证据在 Issue）
3. 业主「你是什么模型」路径可复现绿
4. CLAIM-WB-DEGREE-WEB: NO（本卡）
5. #322 建议 YES 保持冻结直至业主复测

【禁止】
仅 pico · 假绿 · 多窗 · 打印 key

【CLAIM】
CLAIM T-E2E-DEFAULT-CHAT（SOLO）
BASE 55f861db70a1096cb24847eb40f14286dc5e8e6d
PRODUCT 55f861db70a1096cb24847eb40f14286dc5e8e6d
默认路径端到端·E2E-DEFAULT一票否决·禁交件冒充闲聊

【回写】
## Ex SELF-ACCEPT
## E2E-DEFAULT CHECKLIST（D1–D8）
## MERGED / ## DEPLOYED
## 请业主复测
CLAIM-WB-DEGREE-WEB: NO

【合入】
红档：模型默认/鉴权 · 总管可审 · 执行窗不自签产品终局
════════════════════════════════════
```
