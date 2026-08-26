# ADR · 办公文档管道（底子 · 技术选型）

```text
DOC: docs/ADR-OFFICE-DOC-PIPELINE.md
ID: ADR-OFFICE-DOC-PIPELINE
DATE: 2026-08-26
STATUS: Accepted · 业主令：底子打好，选型要对，后期慢慢追上主流
CLAIM-WB: 不改签（已 YES · 本 ADR 不代签）
REPO: juanwan99/pico ONLY
LAW: docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md
北极星: docs/DIRECTION-NOW.md §0-star · 用法 = Grok
现况: docs/STATE-NOW.md · 本 ADR 是选型真源，不是在飞卡
```

---

## 0. 一句话

```text
对标 Claude / Codex 文档 skill 的形态，不是对标 Word 里的 Copilot。
真源 = 结构化中间稿（spec）。
文件 = 成熟库渲染出的投影。
检查 = OOXML 合法 + 能打开。
Pi 只调白名单工具，不写 python-docx，不跑公网 bash。
```

覆盖（Excel / 批注 / 模板）只扩 spec 字段，不换核。**产品只两张卡：核 → 覆盖。**

## 1. 对标与天花板

| 对标 | 他们怎么做 | Pico 跟不跟 |
|------|------------|-------------|
| **Claude / Codex 文档 skill（本线对标）** | SKILL 工艺 + **中间稿** + `python-docx` / `python-pptx` / `openpyxl` + 检查。不把 `.pptx` 当源去补丁。 | **跟。** 同库、同管道。差的是现在还停在「一坨字 → 文件」。 |
| **Word/PPT 里的 Copilot** | 原生对象模型、修订气泡、协作光标。 | **不跟。** 另一条产品。本线永不承诺。 |

**实用天花板（追上主流 = 到这一档，不是超过微软）：**  
老师日常通知 / 教案 / 方案 Word、汇报 PPT、成绩表 Excel——真文件、能读结构、能按地址改、表和图在文档里、坏文件不装绿。设计师级动画 / SmartArt / VBA / 旧 `.doc` 诚实失败。

## 2. 决策（选型锁死）

| 项 | 选定 | 未选（否决） |
|----|------|----------------|
| **真源** | 版本化 JSON **spec**（`pico.office.spec/v1` 起） | 纯文本 body 当长期真源；把 `.docx/.pptx` 当可补丁源 |
| **渲染** | PyPI：`python-docx` · `python-pptx` · **`openpyxl`**（Excel 不再手写 OOXML） | 自研 OOXML 引擎；模型即兴写 Python；COM / Word.exe |
| **读** | 同库 **inspect** → 地址清单（段/页/表/图/批注） | 模型猜「第 3 段」；OCR 当结构 |
| **改（Pico 自己生成的文件）** | 改 spec → **整份重渲染** | 在投影上东补一刀西补一刀当主路径 |
| **改（老师上传、无 spec）** | inspect + **按地址薄改**（其余不动） | 假装能还原完整 spec 再重建（丢格式） |
| **检查** | `is_valid_ooxml` 失败关；LibreOffice `sandbox_document_open` **只预览** | LibreOffice 当排版引擎；坏包装绿 |
| **Pi 看见** | `pico-gateway-tools.ts` + `SYSTEM.md`；动词少、spec 富 | 给 Pi host bash / 代码执行；MCP 办公室栈 |
| **图** | `generate_image` 产物 **插入** spec（进 Word/PPT） | 图和文档两张皮 |
| **升级** | 只改适配层（spec 字段 + 三个模块） | 桥内再造 Office OS |

### 两条路径（必须同时成立）

```text
A  Pico 写的文件：spec 是真源 → render(spec) → 字节入账本
                  再改 = 改 spec 再 render（投影可丢）

B  老师丢进来的文件：无 spec → inspect 出地址 → 按地址 edit
                  不承诺「提取成 spec 再重建仍像素级一样」
```

Codex 社区的教训：**不要把 pptx 当真源去补丁。** 那只适用于路径 A。路径 B 必须诚实。

## 3. 底子（代码落点 · 未开工也先锁目录）

后期实现收口到这三个模块，禁止再在 `document_generators.py` 里堆第三套写法：

| 模块（拟） | 职责 | 上游 |
|------------|------|------|
| `office/spec.py` | 校验 / 升版 `pico.office.spec/vN` | 无（契约） |
| `office/inspect.py` | 字节 → 地址大纲 | python-docx / pptx / openpyxl |
| `office/render.py` | spec → 合法 OOXML 字节 | 同上 |
| `office/edit.py` | 路径 B 按地址改（现 `office_editors.py` 迁入） | 同上 |
| `office/qa.py` | 包合法；可选 LO 能打开 | 现有校验 + sandbox |

现有 `generate_docx_document` / `generate_pptx_document` **名字保留**（Pi 已认识）。内部改为：文本先编成 v1 spec 再 render。禁止平行第二套「吐字成文件」长期活着。

手写 XLSX XML（`build_xlsx_document`）= **过渡遗产**。产品 Excel 必须换 `openpyxl`。旧函数只许测夹具，不许当老师面。

Pi 工具面保持**少动词**：

```text
inspect_document
render_document      ← spec 进、文件出（kind=docx|pptx|xlsx）
edit_document        ← 路径 B；按地址
verify_document      ← 合法 + 能打开
```

`generate_*` / `edit_docx_*` 可当兼容别名，内部走上面四个。**禁止**为字体/颜色/批注各开一个工具。EXPERIENCE §14：改 Python docstring ≠ Pi 看见。

## 4. spec v1（卡 1 冻结形状，卡 2 只加字段）

```text
pico.office.spec/v1
  kind: docx | pptx | xlsx
  title: string
  theme?: { heading_font?, body_font?, accent? }   ← 薄主题，不是设计系统
  blocks: 有序列表
    docx: heading | para | table | image | page_break
    pptx: slide { title, bullets[], notes?, image? }
    xlsx: 卡 1 预留 kind；卡 2 用 openpyxl 落地
```

升版规则：只加字段，不改已有含义。渲染器不认识的字段 = 忽略并在 inspect 里标明 `unsupported`，禁止静默丢老师正文。

## 5. 两张卡（业主 2026-08-26：四刀太多）

选型（本 ADR / #689）**不算产品卡**。产品只两张，1 卡 1 PR，串行，第二张必须等第一张 tip 过门。无在飞则讨论，点头才 stamp。

| 卡 | 一句话 | 做完 | 硬不做（丢给下一张或永不做） |
|----|--------|------|------------------------------|
| **1 核** | 把管道铺上：spec v1 + inspect + render(docx/pptx) + 表/图进文档 + 按地址 edit + verify（合法 + LO 能打开）。`generate_*` 内部改走 spec。 | 日常 Word/PPT 不再「一长条字」；能读结构、能改指定段/页、图在文档里。形态回到 Claude/Codex skill 同档。 | Excel 产品面；批注；模板填空；薄主题字段可先收进 spec **但不做满设计系统** |
| **2 覆盖** | 同一核加字段：Excel=`openpyxl`；批注；薄 theme；模板占位替换；旧格式/不支持项人话失败。 | 成绩表能算能改格；Word 能留意见；套简单模板；坏文件不装绿。 | 修订气泡 UX；数据透视；PDF 排版引擎；`.doc/.ppt/.xls` 转写；设计师母版市场 |

**为什么两张可行、一张不行：**  
卡 1 是换核（旧「吐字成文件」退役）。卡 2 是加字段。捏成一张 = 核和覆盖一起翻，黄、难回滚、假绿风险。拆回四张 = 碎。两张是底。

每张验收：还是不是**唯一** spec/inspect/render。第二套生成器 / Pi bash / MCP 办公室栈 = 打回。

## 6. 禁区（违法或必落后）

1. 让 Pi / DeepSeek **即兴写 python-docx**（Codex 社区已证明文件常坏）。  
2. 公网默认 host bash / 代码执行当办公能力。  
3. 自研 MCP 协议栈或「四十个细工具」办公室服务器。  
4. 自研 OOXML / 排版引擎 / 第二套账本。  
5. 只加 `font`/`color` 旋钮、不建 spec——做完仍是旧形态。  
6. 承诺对齐 Word 内 Copilot。  
7. 猜任务自动交 Word（北极星：老师没点名就不交）。  
8. 改 edu-cloud。

## 7. 审查三问（每张办公 PR 必答）

1. 适配哪一段？（spec / inspect / render / edit / qa）  
2. 上游是谁？（三个 PyPI 名 + 版本）  
3. 上游升级是否只改适配层？（是 → 合；否 → REVISE）

## 8. 后果

- **现在：** 卡 1 #690 · 卡 2 [#694](https://github.com/juanwan99/pico/issues/694) 均过门 @ 产品 tip `18537f47…`。记忆 / 人视角日用仍挂起。  
- **禁第三张办公卡。** 覆盖已收口，不再拆残债卡。  
- **产品承诺：** 两张做完 = 日常真文件办公同档 Claude/Codex skill；不同档 Word 内 Copilot。
