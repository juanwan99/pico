# PLAN · T-WB-STYLE-W1-W5

```text
STATUS: BINDING
DATE: 2026-08-08
GOAL: 公网 Pico 上用「做出有意思的东西」对标 WorkBuddy 程度（非办公填空）
MODE: SOLO · 仅 EXCELLENT 晋级 · Grok 浏览器/脚本主测优先
CLAIM-WB: NO（本包不签；只交工程+E2E 证据）
BASE: 46b90c348ab019f1084365481c2bb3aeb991b5eb
```

## 0. 业主口径（铁）

```text
复杂任务 = X 上 WorkBuddy 教程那种：
  做出可运行/可续跑/可交付的东西
≠ 纪要 / 评标作文 / 单次 generate_docx 填空
验收标准 = 各题锚定的公开教程成功路径（见 §2）
```

## 1. 锁定句

```text
目标：Web 上 WorkBuddy 程度（六条）
方案：Pico 整车 + Pi + DeepSeek
执行：单窗 SOLO · 公网端到端 · Agent 测优先
不做：Dify 门脸 · 场景卷对标 · 双核 · 假绿 CLAIM
```

## 2. 教程锚点（验收真源）

| 题 | 锚点教程 | 成功长什么样 |
|----|----------|--------------|
| **W1** | 宋宋 @songsong：WorkBuddy 做微信小程序（习惯打卡）· [Article](https://x.com/i/article/2085678280301293568) / [帖](https://x.com/songsong/status/2085700722197438652) | 专家/技能召出 → 需求澄清 → 出代码目录 → 导入工具能跑 → 红字丢回修 → 真机/预览 → 五项自测 → 可给他人体验的说明 |
| **W2** | Yunn @Yunn260414：扫榜→选题→自动写小说 · [教程](https://x.com/Yunn260414/status/2085721376162545935) | Skill/流水线串起来；拆标杆前三章；出设定+正文；去 AI 味过检；「继续写」接进度 |
| **W3** | 陆羽 Skill-Bible + WorkBuddy Skills 生态 · [帖](https://x.com/LuyuHenry/status/2085762041139315140) | 可安装/可粘贴的 Skill 规格 + 触发一次真产物 |
| **W4** | 麦麦提：WorkBuddy+Remotion+音乐作品 · [帖](https://x.com/shengtang135754/status/2085735462287642651) | 完整歌词/脚本 + 结构时间轴 + 可发布资产；不能渲视频须诚实边界 |
| **W5** | Rion：Skills/Connectors/Automation 脏活链 · [帖](https://x.com/rionaifantasy/status/2085347251795398841) | 问完以后继续干完：摘要→文档→待办→消息，一条链 |

## 3. Pico 环境诚实边界（写入验收）

| 能力 | 处理 |
|------|------|
| 无微信开发者工具 / 无真机微信 | **W1** 允许交付 **同等功能 Web 单页或可下载前端包** +「与小程序差异说明」；**不得**用差异当借口只交设计稿 |
| 无七猫登录/爬虫 | **W2** 允许用**模拟榜单 JSON/表格**（题干内嵌）代替真扫站；流水线步骤不得省略 |
| 无 Remotion 渲染 | **W4** 必须交齐可拍文案资产；写明「本环境未渲染成片」 |
| 默认路径 | 全程 **不手改模型**；须 deepseek/可用默认 |

## 4. 执行序（无人值守）

```text
前置: E2E-DEFAULT 仍绿（#329）· tip 声明
W1 → 仅 EXCELLENT 晋级 W2 → … → W5
每题: 公网派活 → 多步过程可见 → 产物 → 同会话修补（若教程要求）→ SELF-ACCEPT
包末: 证据包 + CLAIM-WB:NO
```

## 5. 防假绿

- 打不开 / 无文件 / 仅长文无流水线 = FAIL  
- 「已修复」但复测仍挂 = FAIL（W1 对齐教程与 Walay 反例）  
- 只用 Agent 管线绿冒充默认闲聊 = 不计入本包  
- 禁止自签 CLAIM-WB=YES  

```
════════════════════════════════════
BINDING · WB-STYLE W1–W5
做出东西 · 教程级验收 · 非办公填空
════════════════════════════════════
```
