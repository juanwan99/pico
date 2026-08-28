# 阶段总计划 · 对标 WorkBuddy（办公核心 · 编程兼顾）

```text
DOC: docs/STAGE-PLAN-WB-CORE.md
STATUS: 总管计划稿 · 2026-08-28 · 待业主逐条 要/不要/改
不是在飞卡 · 不 stamp · 不改 #740 卡面
仓: juanwan99/pico ONLY
北极星: #744 / PR #745 宪法 v1.4（草案 1；main 尚未合入）
组织: docs/STAGE-PACKAGE-MODE.md（一张阶段包 · SOLO · 执行=grok-ecs）
加载: docs/ADR-CAPABILITY-LOADING.md
办公: docs/ADR-OFFICE-DOC-PIPELINE.md
工具: grok-ecs（PR #746）· 禁默认 spawn-executor
```

---

## 0. 一句话

```text
对标 WorkBuddy：通用 Web 工作台。
办公是核心能力。编程兼顾。互不否决。
先拆焊、加载诚实；再加厚办公；再让沙箱编程看得见；编排后置。
```

对话纪律仍是 Grok 形。核 = 上游 Pi + DeepSeek。薄适配。六条 YES ≠ 能力终局。

---

## 1. 门 0（计划开工前 · 不是能力卡）

| # | 项 | 状态（2026-08-28） | 谁 |
|---|----|-------------------|-----|
| G0 | #740 老师**新对话**验 PPT 契约，手 PASS | 在飞 OPEN · 已部 `0c28f7b2…` | 老师 |
| G1 | 宪法 v1.4 合 main（#745 · 不部） | PR 开着 | 执行窗合 |
| G2 | `grok-ecs` 合 main（#746 · CI 3/3 · 不部） | PR 开着 | 执行窗合 |
| G3 | 后续执行只走 `bash scripts/spawn-grok-ecs.sh --issue N` | 本窗已证 `GROK_ECS_OK` | 总管 |

**G0 未清，不开下一张 stamp-ok。** 同域第二张废派。本页只计划。

---

## 2. 四步（顺序不许颠倒）

| 步 | 阶段包名（拟） | 一句话 | 何时 stamp |
|----|----------------|--------|------------|
| **S1** | T-LOAD-HONEST | 拆焊 + 诚实加载 | G0 清 + 业主点头本页 |
| **S2** | T-OFFICE-THICK | 办公核心加厚（上游 document skill 做法 + 现有 sandbox） | S1 老师 PASS |
| **S3** | T-CODE-SANDBOX | 编程兼顾：隔离沙箱并列可见，服务办公 | S2 老师 PASS |
| **S4** | — | 编排后置 | **无卡** |

每步一张 SOLO 卡、一个 PR 主链。执行 = **grok-ecs**。总管不合不部。

---

## 3. S1 · T-LOAD-HONEST（第一步 · 唯一建议下一包）

### 3.1 现网缺口（代码事实 · tip `0c28f7b2…`）

| 缺口 | 落点 | 为何是加载不是编排 |
|------|------|-------------------|
| SYSTEM 焊「Photos still use generate_image」 | `agent_assets/system.md` L16 | 系统点名胜负 |
| CORE 16 个 schema 每轮全挂 | `capability_loading.py` `CORE_VISIBLE_TOOLS` | 常驻过多 |
| 办公天花板 `sandbox_pptx_lib` 在 EXTENDED | 同文件 | 默认「做个 PPT」看不见厚度 |
| 编程 `sandbox_workspace_exec` 在 EXTENDED | 同文件 | **S1 不动**（留给 S3） |
| 场景 Skill 苗（教案/出题） | `SCENE_SKILL_IDS` | 禁自动挂；S1 加测锁死 |

### 3.2 范围内（建议内部序 · 不拆多 Issue）

1. **拆焊**：删 SYSTEM 照片唯一路径句。工具说明只写「做什么 + 何时用」，不写「必须走某工具」。`generate_diagram` 说明可留何时用。
2. **办公天花板可见**：`sandbox_pptx_lib` 从 EXTENDED 升到模型默认能看见（办公核心 = 加载不能先藏）。优先：**旧动词说明点名该工具 + 该工具进入可见集**。不新开办公核。
3. **目录诚实**：`$skill_catalog` 继续只挂名 + 一句何时用。`SCENE_SKILL_IDS` 不因「课件/精美」自动进 `allowed_tools`。单测锁死。
4. **常驻不膨胀**：办公相关 generate/edit/inspect 留在 CORE（办公核心）。不把浏览/发布/host 重活拉回 CORE。不自研 ToolSearch。

### 3.3 禁区

- ToolSearch / `DeferExecuteTool` / 第二编排核
- 五包清单 / 第三张 spec 办公卡
- `if 精美/课件 then` 自动挂 Skill
- 整仓抄 Proprietary Anthropic skill
- `pi install` 拉主机 bash
- 公网 host bash
- 改 #740 卡面 / 记忆 OS / MCP / 商店 / 连接器
- 默认 `spawn-executor` / `@cursor`

### 3.4 DoD（可勾）

- [ ] `system.md` 无「Photos still use generate_image」
- [ ] 默认对话 Pi 看得见 `sandbox_pptx_lib`（或旧 pptx 动词说明能调到它，且它在可见集）
- [ ] 单测：正文含「课件」不自动挂 scene Skill
- [ ] 单测：SYSTEM / 网关说明无「照片必须 / 必须造图」
- [ ] CI 3/3 · tip-pin · 写入不自签
- [ ] 老师手（过门）：**新对话** ①问「这是什么」只解释 ②说「做成 PPT」能交文件 ③要图不否决文档；系统不先帮你选

### 3.5 成果包（S1 末）

```text
SHA / tip / CI
焊句删除前后各一行
默认可见工具列表（CORE）
老师三问手测（新对话）
未做：办公厚度（S2）· 编程可见（S3）· 编排（S4 永不做卡）
```

### 3.6 业主验收（≤6）

1. 问句不再被推进交文件  
2. 点名 PPT 仍能交（不回归 #740 空图）  
3. 要图 / 要文档互不否决  
4. 没有「必须造图」系统句  
5. 不出现新菜单/商店  
6. 执行回执来自 grok-ecs，不是新云端 Cursor  

---

## 4. S2 · T-OFFICE-THICK（S1 过后再写卡面）

```text
目标：办公选了真能干成。天花板 = 上游 document skill 做法 + 现有隔离 sandbox。
做：薄适配方法论进 sandbox_pptx_lib / generate_*；默认对话用得上厚度。
不做：第三张 spec 卡；腾讯 JSX；课型母版；焊「必须精美」。
稳妥默认仍是 spec generate_*。两条路径（Pico 写的 / 老师丢进来的）见 ADR-OFFICE。
```

---

## 5. S3 · T-CODE-SANDBOX（S2 过后再写卡面）

```text
目标：隔离沙箱执行并列可见；能跑、能改、能服务办公产物。
现网：sandbox_workspace_exec = HTML/Python AST，且在 EXTENDED。
不做：公网 host bash；Cursor 克隆；第二品类。
```

---

## 6. S4 · 编排后置

无卡。不加厚编排层。不写词表路由。以后多源自动选，核仍是 Pi。

---

## 7. 红线（全程）

只写 pico · 薄适配 · 唯一账本 · 租户隔离 · 不自 PASS · 过门=老师手 · 1卡1PR · 证据贴 Issue · 合了未部不算完 · 禁 edu-cloud · 禁假绿 CLAIM

---

## 8. 请业主核（要 / 不要 / 改）

| # | 命题 |
|---|------|
| P1 | 门 0：#740 老师过门 + #745/#746 合 main 之后，才 stamp S1 |
| P2 | 下一张唯一阶段包 = S1 T-LOAD-HONEST（拆焊 + 办公天花板可见 + 目录不自动挂） |
| P3 | S1 把 `sandbox_pptx_lib` 变成默认看得见（加载诚实）。不加厚办公核 |
| P4 | S1 **不**把 `sandbox_workspace_exec` 升默认（留给 S3） |
| P5 | S2/S3 只预告，现在不写卡、不 stamp |
| P6 | S4 永不做卡 |
| P7 | 执行窗 = grok-ecs，不再起云端 Cursor |

通过后总管才出 S1 标准任务卡 + `## 派发` + `spawn-grok-ecs.sh`。
