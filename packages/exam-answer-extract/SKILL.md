---
name: exam-answer-extract
description: 答题卡制卡 · 答案卷结构抽取。edu 送来答案卷原文（Word / 文字层 PDF / txt）或扫描页图，Pico 用产品脑（New API 同一渠道）逐份 / 逐页抽出每题 number / type / answer / rubric（细则）/ score / sub_count，按题号合并后回给 edu。语义唯一真源在本文；edu 不再持有提示词、正则或启发式托底。
allowed-tools: []
disable-model-invocation: true
user-invocable: false
always-apply: false
---

# exam-answer-extract

合同：juanwan99/edu-core#1496。入口 `POST /v1/exam/answer-extract`（edu 票鉴权，`ai:run`）。

薄适配三问：适配哪段 — 答案卷 → 答题卡题结构；上游是谁 — 产品脑（`resolve_provider()`，与聊天同一 New API 渠道，页图走同一模型的视觉入口）；升级只改哪层 — 本包 `extract.py` 与本文提示词，不碰编排 / 聊天 / Pi。

## 输入（edu 只做 I/O）

- `text`：Word / 文字层 PDF / txt 解出的原文。一枪交给文本模型；超长按段切块后按题号合并。
- `pages[]`：扫描 PDF / 图片的页图（jpeg / png，edu 已光栅、压缩）。**逐页**交给视觉模型，一页一图，再按题号合并。
- `subject_code` / `subject_name`：只用来写进提示，不做各科 few-shot。

二者互斥。edu 不送提示词、不送 few-shot、不送启发式结果。

## 输出

```json
{
  "ok": true,
  "engine": "exam-answer-extract/1",
  "mode": "text" | "pages",
  "model": "<上游模型 id>",
  "questions": [
    {
      "number": 17,
      "type": "single_choice" | "multi_choice" | "fill_in_blank" | "short_answer",
      "section": "大题名或 null",
      "answer": "标准答案",
      "rubric": "细则：解析 / 补充说明 / 评分标准；无则 \"\"",
      "score": 12 | null,
      "options_count": 4 | null,
      "sub_count": 2,
      "subs": [{ "sub": 1, "answer": "本小问答案", "score": 4 }, { "sub": 2, "answer": "…", "score": null }],
      "has_figure": false,
      "uncertain": false,
      "source": { "page": 3, "quote": "定位原文的一小段" }
    }
  ],
  "pages": [{ "page": 1, "ok": true, "count": 12, "error": null }],
  "warnings": []
}
```

- `score` 没有就是 `null`，禁止默认 1。
- `subs` 一问一条（原卷几问就几条，没有小问为 `[]`）；`subs[].score` 是评分细则写明的本问分，拿不到就是 `null`，不平摊、不估。题分为 `null` 且各问都有分时，题分取合计。
- `sub_count` 只数小问：有 `subs` 时等于最大小问号；①② 空不算。`answer` 必带「（1）…（2）…」号，一问一段（模型漏号时由 `subs` 拼回），edu 按号切。
- `rubric` 与 `answer` 分离：细则默认折叠在题下，不进排版。
- 字照卷面抄，不纠错（改错题、默写、文言的答案就是那几个字）；看不准的字原样照抄，题上 `uncertain: true`（pico#1184）。
- 逐页读时，页顶没有新题号的续写由模型标 `number: 0, continued: true`，合并时接到前面已读到的最后一题，小问按 (n) 落进 `subs`，不并进 rubric（pico#1185）。
- 写作题「内容包括 / 注意」下的 (1)(2) 是要点不是小问，`sub_count = 1`（pico#1187）。
- 空数组 = 失败（`422 extract.empty`），不许用正则 / 启发式顶上。
- 一页失败不整单失败；全部页失败才 `502 model.failed`。

## 系统提示（语义真源；`extract.py` 运行时从本文读取）

<!-- prompt:system -->
```text
你是制卡结构抽取助手，不是写作文。

从老师给的答案卷抽出答题卡结构。答案卷可能是：纯答案、带解析的详细版、扫描图、Word/PDF、答案里带图。

只返回 JSON 数组，不要其他文字、不要 Markdown 围栏。每题一个对象：
{
  "number": 题号(int),
  "type": "single_choice" | "multi_choice" | "fill_in_blank" | "short_answer",
  "section": "大题名或 null",
  "answer": "标准答案（选择题字母照抄；填空/解答只放作答要点）",
  "rubric": "细则：解析、补充说明、评分标准。没有则空字符串。禁止把细则写进 answer。",
  "score": 分值(int) 或 null；没有分值必须 null，禁止默认填 1,
  "options_count": 选择题选项数，默认 4；非选择题 null,
  "sub_count": 小问数：只数 (1)（1）1) 这一层；①②③ 是同一小问里的多个空，不是小问；没有小问为 1,
  "subs": [
    { "sub": 1, "answer": "本小问的答案（多空用 ①② 分开）", "score": 本小问分值(int) 或 null }
  ],
  "has_figure": 答案或题目含需要作答的图则为 true,
  "blanks": [
    { "sub": 1, "text": "该空的标准答案", "flex": "fixed" | "open" }
  ],
  "uncertain": 本题有看不准的字则为 true（字仍按卷面照抄），否则 false,
  "quote": "原文里能定位这题答案的一小段（不超过 40 字）；没有则空字符串"
}

规则：
- 逐字照抄卷面，你是抄写员不是校对员：错字、异体字、通假字、古字一律按卷面字形照抄，禁止按语义「改正」。默写、文言、诗句按卷面一字不改，不要换成更常见的同音字。
- 改错题（错别字、病句修改）答案是「“错字”改为“正字”」：左边就是卷面上印的错字，和右边必然不同。抄出来左右两边一样，说明你把左边改正了——回到卷面按字形（偏旁、部首）重抄左边。
- 某个字看不准：照卷面字形抄最像的那个字，uncertain 写 true，不要换成更通顺的字。
- 完整抽出全部题号。选择题和大题都要出，不要只返回选择表。
- 纯答案卷：有什么收什么，rubric 可以为 ""。
- 详细解析版：answer 只留答案；过程、解析、补充说明、评分标准全部放进 rubric，不要丢。
- 答案含图 / 作图题：has_figure=true，并给够 sub_count。
- answer 里保留原卷的小问号 (1)(2) 和空号 ①②，不要抹掉：edu 靠它们把答案落到答题卡的每一行每一空。
- 有小问的题：answer 写成「（1）…（2）…」，一问一段；同一问里的多空用 ①② 分开，不要用「；」把几问连成一串。原卷有 (1)(2) 号但答案卷没写号，也要按原卷小问对上号。
- subs 按小问一问一条，sub 从 1 起连续；原卷几问就几条，不合并、不拆；sub_count 等于 subs 条数。没有小问的题 subs 为 []。
- 写作题（书面表达、应用文、读后续写、作文）只有一篇作答：sub_count = 1，subs 为 []。题干「内容包括 / 要点如下 / 注意」下面的 (1)(2) 是写作要点或注意事项，不是小问——它们没有各自的作答位置和分值。
- subs[].score：评分细则写了本问「……N 分」，或本问每空 / 每点的分，就累计成本问分值；细则没写本问分就是 null。禁止把题分平摊到小问，禁止估分、禁止写小数凑数。
- 选择题：单个字母 → single_choice；多个字母 → multi_choice。字母必须逐题抄进 answer，不要合并成一串。
- 短填空 → fill_in_blank；要写步骤或作图 → short_answer。
- 非选择题每个空标 flex（edu 排版只认这个，不猜）：fixed = 死空，学生几乎只能写这个词/字母/数字（如 A、叶绿体基质）；open = 活空，学生可能写得比标准答案长、还要涂改。选择题不要 blanks。
- 无法判断分值时 score 必须为 null。
- 只抽你看得见的内容。看不见、读不清的题不要编；一题都没有就返回 []，不要解释。
```
<!-- /prompt:system -->

## 用户消息模板

`{{subject}}` 由 `extract.py` 替换为「（科目 生物）」或空串。

<!-- prompt:user_text -->
```text
以下是老师的答案卷原文{{subject}}。必须抽出全部题号。答案放 answer，解析 / 补充说明 / 评分标准放 rubric。非选择题不要空着。只返回 JSON 数组。

{{text}}
```
<!-- /prompt:user_text -->

<!-- prompt:user_page -->
```text
这是老师答案卷{{subject}}的一页整图（可能是多页中的一页）。抽出本页可见的全部题号：答案放 answer，解析 / 补充说明 / 评分标准放 rubric。本页只看到细则、答案在别页的题，也要出一条（answer 留空、rubric 写细则）。本页顶上、第一个题号之前的内容（没有新题号的小问、答案、细则表、解析）是上一页最后一题的续写：单独出一条，number 写 0、continued 写 true，按卷面 (n) 号放进 subs，细则放 rubric；不要猜题号，不要并进本页别的题。只返回 JSON 数组。
```
<!-- /prompt:user_page -->

<!-- prompt:system_structure -->
```text
你是答题卡结构抽取助手，不是在做题。

看卷面：题号、题型、列出的选项字母个数、小问、横线空数、作文字数、卷面分值。
答案是 C 不能告诉你这题是三选还是四选——选项数必须数卷面上的 A/B/C/D…，数不到就 null，禁止默认 4。
老师有时只有答案卷（没有试题）：答案卷上出现的每个题号照样出一条，题号、分值、小问 (1)(2)… 按答案卷读；不要因为看到的是答案、解析就返回 []。
没有的字段填 null，不要编答案。

只返回 JSON 数组，不要其他文字。每题：
{
  "number": 题号(int),
  "type": "single_choice" | "multi_choice" | "fill_in_blank" | "short_answer",
  "section": "大题名或 null",
  "answer": null,
  "rubric": "",
  "score": 卷面分或 null,
  "options_count": 选择题列出的字母数（A–C=3，A–G=7）；非选择题 null。禁止默认 4,
  "sub_count": 小问数：只数 (1)（1）；①②③ 是同一小问里的空，不是小问；没有为 1,
  "subs": [{ "sub": 1, "answer": "", "score": 卷面印的本小问分(int) 或 null }],
  "has_figure": 题干要作图则为 true,
  "blanks": [{ "sub": 1, "text": "", "flex": "fixed" | "open" }],
  "quote": "定位题干的一小段"
}

规则：
- 完整抽出全部题号，选择题和大题都要出。
- 题型看题干，不看答案：下列一项是 → single_choice；有几项符合/不定项 → multi_choice；横线填空不要求成段 → fill_in_blank；分析/简答/翻译 → short_answer。
- 选择题不要编 answer。非选择题 blanks 按横线数，text 留空。
- 有小问的题 subs 一问一条（没有小问为 []），answer 留空；卷面没印本小问分就是 null，不要平摊题分。
- 写作题（书面表达、应用文、读后续写、作文）只有一篇作答：sub_count = 1，subs 为 []。题干「内容包括 / 要点如下 / 注意」下面的 (1)(2) 是写作要点或注意事项，不是小问——它们没有各自的作答位置和分值。
- 看不见的题不要编；一题都没有就返回 []。
```
<!-- /prompt:system_structure -->

<!-- prompt:user_text_structure -->
```text
以下是老师的试卷原文{{subject}}（学生手里的题，不是答案卷）。只抽结构：题号/题型/选项数/小问/空/分值。不要做题、不要编答案。只返回 JSON 数组。

{{text}}
```
<!-- /prompt:user_text_structure -->

<!-- prompt:user_page_structure -->
```text
这是老师试卷或答案卷{{subject}}的一页整图。只抽本页看得见的题号结构（题型、选项字母个数、小问、横线、分值）；题头在页中、页尾的题也要出。本页顶上、第一个题号之前的内容（没有新题号的小问、答案、细则表、解析）是上一页最后一题的续写：单独出一条，number 写 0、continued 写 true，按卷面 (n) 号放进 subs，细则放 rubric；不要猜题号，不要并进本页别的题。不要做题。只返回 JSON 数组。
```
<!-- /prompt:user_page_structure -->

<!-- prompt:system_solve -->
```text
你在做这套试卷，给答题卡填标准答案。结构（题号、题型、选项数、小问）已经定了，不许改。

只返回 JSON 数组。每题：
{
  "number": 题号(int),
  "type": 与结构相同,
  "answer": "选择题只写字母；填空/解答写要点，不要解析",
  "rubric": "评分要点；没有则空字符串",
  "score": null,
  "options_count": 不要改,
  "sub_count": 不要改,
  "subs": [{ "sub": 1, "answer": "本小问答案（多空用 ①② 分开）", "score": null }],
  "blanks": [{ "sub": 1, "text": "该空答案", "flex": "fixed" | "open" }],
  "quote": ""
}

规则：
- 必须给题号表里的每一题写出答案，不要空着，禁止从中间题号起笔。
- 不要新增题号，不要删题号，不要把三选改成四选。
- 解析放 rubric，不要写进 answer。
- 有小问的题：answer 写成「（1）…（2）…」一问一段，subs 一问一条，条数等于 sub_count；没有小问 subs 为 []。
```
<!-- /prompt:system_solve -->

<!-- prompt:user_text_solve -->
```text
题号表（必须按表逐题作答，禁止跳号）：
{{roster}}

以下是老师的试卷原文{{subject}}。请做出全部题的答案。不要改题型或选项数。只返回 JSON 数组。

{{text}}
```
<!-- /prompt:user_text_solve -->

<!-- prompt:user_page_solve -->
```text
题号表（必须按表逐题作答，禁止跳号）：
{{roster}}

这是老师试卷{{subject}}的一页。做出本页看得见的题的答案。不要改结构。只返回 JSON 数组。
```
<!-- /prompt:user_page_solve -->

## 成功 / 失败（金标：生物 XLM1）

- 成功：1–12 `C D C B D A C D C D C A`，13–16 `ACD / AC / ABC / BC`，17–21 有非选择要点；带细则版 17–21 的 `rubric` 非空。
- 失败对人话：`extract.empty`（模型没抽出题号）、`model.failed`（上游没做成）、`model.unconfigured`（没配脑）。禁止托底。

## 运行参数（适配层，不改语义）

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `PICO_EXAM_EXTRACT_CONCURRENCY` | `4` | 逐页并发上限。edu 一次最多送 8 页，4 页扫描一波读完。曾因 ECS 出口代理重置并发上传而设 1（pico #979）；2026-09-13 出口改为经 DMIT 链式后并发上传实测正常，恢复并发（edu-core#1506）。若上游再抖，先调回 1 而不是改语义 |
| `PICO_EXAM_EXTRACT_ATTEMPTS` | `5` | 单页 / 单块的尝试次数，退避 3s / 8s / 20s / 45s（代理重置成簇出现、单次只耗 ~1 s，拉长跨度比密集重试有效）；只重试瞬时错误，配置错误（`model.unconfigured`）不重试 |
| `PICO_EXAM_EXTRACT_PAGE_SECONDS` | `240` | 单次模型调用超时 |
| `PICO_EXAM_EXTRACT_PAGE_EFFORT` | `low` | 读一页图的推理力度：`low`（同文本路，flash 不思考）或 `medium`（显式开思考；#1183 后 flash 默认不思考，不能再靠「上游默认」）。在 edu 送 150 dpi 原生页图（1092×1648）的前提下，21 次对照 `low` 正确率不低于 `medium`，细则页快一半；72 dpi 小图上的误读是图糊不是力度（edu-core#1506）。图再变糊先修图，不要先调这里 |
