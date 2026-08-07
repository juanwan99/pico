# 阶段二验收方案 · STAGE2-WB-POLISH（优秀门槛）

```text
DOC: docs/ACCEPT-STAGE2-WB-POLISH.md
STATUS: BINDING
PAIR: PLAN-STAGE2 · T-STAGE2-WB-POLISH
RULE: 未达 EXCELLENT = 未完成 = 禁止下一小任务
```

---

## 0. 三级评分

| 等级 | 晋级 |
|------|------|
| **EXCELLENT** | 是 |
| PASS_WEAK / FAIL | 否 · 继续修 |

### 一票否决

```text
- 仅 loopback/API 无公网
- 六条回归失败仍宣称打磨完成
- 执行窗自签 CLAIM-WB=YES
- 像素/workDir/真 MCP 协议完备等夸大
- 密钥进 Issue
```

---

## 1. 小任务优秀标准

### S2.0 阶段一回归

| EXCELLENT |
|-----------|
| 公网登录成功 |
| 一题交件：非空可下文件 + UI 找得到 |
| 短答 17+25→42 无硬塞文件 |
| runtime 仍 pi-agent |

### S2.1 差距清单

| EXCELLENT |
|-----------|
| Issue 内表格：阻断 / 体验 / 后置 ≥5 行 |
| 每行有「是否本包修」标记 |
| 与 HANDOFF 六条对齐，无桌面顶格项当阻断 |

### S2.2 交件纪律默认硬

| EXCELLENT |
|-----------|
| 交件题**不**强制手写工具名也能出真文件（或系统自动走工具） |
| 复现 S1.5 类「裸模型假成功」路径 → **不再**假成功 |
| 公网证据 run + 文件 |

### S2.3 长任务手感

| EXCELLENT |
|-----------|
| 长任务过程中用户可见进行中（文案/步骤/心跳） |
| ≥30s 任务不「假死无反馈」 |
| 公网截图或录屏说明 |

### S2.4 产物露出

| EXCELLENT |
|-----------|
| 完成后产物在固定区域 |
| 下载/打开 ≤2 次点击主路径 |
| 新用户无需翻日志 |

### S2.5 失败+重试

| EXCELLENT |
|-----------|
| 失败中文可读 |
| 存在「再试/重发」用户路径 |
| 不空白崩溃 |

### S2.6 难任务抽检

| EXCELLENT |
|-----------|
| **≥3** 当场新题（非阶段一原题原文） |
| 类型覆盖至少两类：公文/说明 · 表格或结构化 · 分析或总结 |
| **≥2/3** 可交差（真产物或合格短交付） |
| 每题 run_id + 结果记录 |

### S2.7 材料再问

| EXCELLENT |
|-----------|
| 有材料：回答能引用/依据材料 |
| 无材料：诚实未命中/请上传，不编造库完备 |
| 公网各 1 例 |

### S2.8 移动端

| EXCELLENT |
|-----------|
| 视口 ~390×844 |
| 能登录或保持登录、发一任务、看到结果 |
| 无致命挡操作横向溢出 |

### S2.9 诚实边界

| EXCELLENT |
|-----------|
| STATE-NOW 或 HANDOFF 或本 Issue 固定段写明：Web≠workDir · MCP=桥 · KB=试点 · 非像素 |
| 对外演示话术不与文档冲突 |

### S2.10 公网证据包

| EXCELLENT |
|-----------|
| Issue 内完整：六条表 + S2.6 难任务 + tip SHA + 关键 run/文件 |
| 声明 STAGE2_WB_POLISH 建议 + CLAIM 建议 YES/NO（**非签章**） |
| 请业主 OWNER DECISION 模板已贴 |

### S2.11 真源回写

| EXCELLENT（仅业主 YES 后） |
|---------------------------|
| STATE-NOW：CLAIM-WB-DEGREE-WEB=YES @ tip |
| HANDOFF §9 或等价回写 |
| tip 与生产一致 |
| 业主 NO：本条 **SKIP** + 缺口进下卡，不算 FAIL 整包 |

---

## 2. 阶段末

```text
STAGE2_WB_POLISH: PASS  ⇔ S2.0–S2.10 全 EXCELLENT
CLAIM-WB-DEGREE-WEB: 仅 ## OWNER DECISION
```

### SELF-ACCEPT 模板

```text
## S2.x SELF-ACCEPT
DATE:
TIP:
grade: EXCELLENT|PASS_WEAK|FAIL
public: yes
evidence:
gap:
next:
CLAIM-WB-DEGREE-WEB: NO|PENDING|（勿写 YES）
```

```
════════════════════════════════════════════════════════
BINDING · ACCEPT-STAGE2 · 仅 EXCELLENT · 业主独签 CLAIM
════════════════════════════════════════════════════════
```
