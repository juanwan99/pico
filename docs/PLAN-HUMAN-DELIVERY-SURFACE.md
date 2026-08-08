# PLAN · T-HUMAN-DELIVERY-SURFACE

```text
STATUS: BINDING 修复方案
PARENT: docs/RCA-HUMAN-DELIVERY-SURFACE.md
GOAL: 用户窗只见人包与可下载成果；机审退后台；UI 交付一票否决
MODE: 根因修复 · 禁表面话术补丁
CLAIM-WB: NO
```

## 0. 锁定句

```text
目标：Web 上 WorkBuddy 程度（六条）· 以人为本
方案：Pico 整车 + Pi + DeepSeek
执行：用户面/机审面分流 · 下载一等公民 · 审查改尺子
不做：把 L0 表美化后继续塞用户窗 · 无下载却 PASS
```

## 1. 目标体验（验收图像）

用户说「做孟德尔互动课件」后，**主回复仅类似**：

```text
课件已做好：孟德尔遗传定律课件.html
[下载]  （或预览）

里面有：简介 / 分离定律 / 自由组合 / 互动测验
用法：下载后用浏览器打开，可离线使用。
要改题量或配色直接说。
```

**禁止出现在主回复（默认）：** Artifact ID、L0/L1 表、encoding、run uuid、source_wall、完整 HTML 源码、账本登记术语。

可选：用户问「技术自检」再展开机审详情。

## 2. 工作包（按依赖）

### W1 · 双轨话术（提示词 / 指令）— 根因 R2/R3

| 做 | 不做 |
|----|------|
| system：用户回复 = 人包模板（文件名、用途、打开方式、下一步） | 要求模型向用户 report L0 字段名 |
| 工程纪律改为 **对工具/对系统**：必须 write 账本、必须 verify | 纪律正文禁止「向用户输出 verification_level」 |
| verify：工具仍返回机读 JSON | 工具 description 写明：结果供系统；**勿向用户复读字段名** |

**验收：** 同提示词回归，主 final_text 机审关键词命中率 → 0（允许「请本机打开确认按钮」一句人话）。

### W2 · final_text 人包硬门（服务端）— 根因 R2/R5

在 run finalize / stream 末包：

1. **检测** 全量 HTML 文档贴在聊天（`<!DOCTYPE`/`<html` 超长）→ 若账本已有 html artifact，**剥离源码**，改为下载引导 + 保留短说明  
2. **剥离/降噪** 默认对外字段：`artifact_id`、`verification_level`、`L0_structure`、`interaction_status=not_run` 机器表等（可配置 allowlist）  
3. **若有产物却无文件名卡片**：自动补一行人读文件名列表（来自 artifact titles）  

**验收：** 单测 + 一次 API 回归：有 html artifact 时 final_text 不含完整 doctype 文档。

### W3 · 账本 → 门脸下载一等公民 — 根因 R4（最硬）

| 项 | 要求 |
|----|------|
| API | 明确「按 artifact 下载」端点（鉴权 + content-disposition 文件名） |
| 事件 | `artifact.created` 对 UI 可消费（title、mime、download_url 或 file ref） |
| LibreChat / 门脸 | 消息区 **文件芯片**：文件名可点下载/预览；**不**以 UUID 为主标签 |
| Agent | 工具成功回传可含 `user_label=文件名`；模型被引导「指引用户点下载」 |

**验收（一票否决）：** 公网登录 UI 走完生成 → **不靠 API 工具** → 用户能点下载 → 打开能用。  
无演示号则：**先恢复可测账号策略**，禁止再用「仅 API」代替本条 PASS。

### W4 · verify 对内化 — 根因 R3

- verify 结果写入 **run 事件 / delivery.summary**（已有方向加强）  
- 用户默认回复：**禁止**粘贴 verify JSON  
- 防假绿保留：服务端可在「宣称可运行却 L0 fail」时 fail-closed 或改写 final  

### W5 · 审查尺子纠正 — 根因 R6

| 旧 | 新 |
|----|-----|
| API 冒烟可过部署 | **UI 下载路径**为交付类卡必选项 |
| 执行窗本机打开 = 人类 Y | 仅当 **业主或等价公网登录 UI** 时算人类交付 Y |
| 机审字段出现无所谓 | 主回复机审字段 = **体验 FAIL** |

### W6 · 回归集（人类视角）

1. 孟德尔课件：UI 下载 + 打开测验可点  
2. 隐式多文件：≥2 下载芯片，无 ID 主文  
3. 闲聊：无产物、无机审表  
4. 负例：模型若贴源码，服务端剥离后仍可下载  

## 3. 明确不做（反表面补丁）

```text
❌ 只改中文措辞，ID 仍主展示
❌ 用户窗改名「产物编号」继续展示
❌ 无 W3 只做 W1
❌ 为过卡写死「孟德尔」特判
❌ 取消账本/verify（倒退）
```

## 4. 切片与完成定义

| ID | 完成 |
|----|------|
| HDS0 | RCA 评审确认（本文） |
| HDS1 | W1 提示词双轨合入 |
| HDS2 | W2 final_text 人包硬门 + 单测 |
| HDS3 | W3 下载桥 + UI 芯片 |
| HDS4 | W4 verify 对内 |
| HDS5 | W5 审查文档/ACCEPT 补丁 |
| HDS6 | W6 公网 UI 回归（真登录）PASS |

```text
HUMAN_DELIVERY_SURFACE: PASS ⇔ HDS1–HDS6
且 业主标准：拿得到 + 打得开 + 主窗无机审体检单
CLAIM-WB: NO
```

## 5. 建议执行序

```text
HDS1+HDS2（快，止血用户窗）
→ HDS3（真交付，最长）
→ HDS4 可与 HDS2 并行
→ HDS5 文档
→ HDS6 公网 UI 一票否决回归
```
