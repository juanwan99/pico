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
      "rubric": "评分标准 / 给分点 / 补充说明；无则 \"\"",
      "analysis": "解析 / 解题过程；无则 \"\"",
      "stem": "题干原文（paper 读法）；其余读法 \"\"",
      "material_id": "M1 或 null（paper 读法）",
      "figures": [{ "page": 3, "box": [693, 76, 894, 173] }],
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
- `sub_count` 只数小问：有 `subs` 时等于最大小问号；①② 空不算。`answer` 必带「（1）…（2）…」号，一问一段（模型漏号时由 `subs` 拼回），edu 按号切。一问多空每空前都标 ①②（第一空也标；只写「a ① b」时 edu 会把第一空之后的号整体错一位，一模定稿 20、21 题，edu-core#3164）。
- 小问空着、整题答案里有「（1）…（2）…」的按号拆进小问（`split_by_sub_marks`）。已知局限：只认 (1)（1）1) 这几种号，带括号的圈码「⑴⑵」不拆，那题小问照模型给的。
- `rubric` 与 `answer` 分离：细则默认折叠在题下，不进排版。`analysis`（解析）与 `rubric`（评分标准）分开，edu 各存一处（edu-core#3157）。
- `paper` 读法的共用材料单独成条（`kind: material`），合并后放进顶层 `materials: [{id, material_for, material, figures}]`，题上带 `material_id`；页顶续写的材料接到前一段材料后面；材料没写 `material_for` 时，管到下一段材料之前的题。
- `task`：`answers`（答案卷）/ `structure`（只抽结构）/ `solve`（按题号表做题）/ `paper`（试卷录入：题干、选项、共用材料、配图外框，卷上印了答案 / 解析 / 评分标准一起抄，不做题；edu-core#3157）。
- 题干、答案里的公式是 `$…$` LaTeX；模型常把 `\frac`、`\perp` 的反斜杠裸写进 JSON，解析前先补成 `\\`（`escape_latex`），否则整组解析失败或 `\f` 被当成换页符。
- `figures[].box` 是 0–1000 归一的页内外框（左、上、右、下），只在读页图时有；模型按视觉模型惯用的 `box_2d`（上、左、下、右）给，`extract.py` 换成左上右下（模型直接给 `box` 时 x、y 顺序不稳，10-15 实测物理卷 15 框里错 6 框）；读文字原文时为 `[]`，Word 里的图由 edu 以 `[图N]` 标记送进原文，题干里原样保留。
- 字照卷面抄，不纠错（改错题、默写、文言的答案就是那几个字）；看不准的字原样照抄，题上 `uncertain: true`（pico#1184）。
- 逐页读时，页顶没有新题号的续写由模型标 `number: 0, continued: true`，合并时接到前面已读到的最后一题，小问按 (n) 落进 `subs`，不并进 rubric（pico#1185）。
- 写作题「内容包括 / 注意」下的 (1)(2) 是要点不是小问，`sub_count = 1`（pico#1187）。
- 空数组 = 失败（`422 extract.empty`），不许用正则 / 启发式顶上。
- 一页失败不整单失败；全部页失败才 `502 model.failed`。
- 文字原文抽结构（`task=structure`）同时读两遍，逐题比题型 / 分值 / 选项数 / 小问：一致直接回；不一致加读第三遍，每题取多数，仍无多数按第一遍并在 `warnings` 里请老师核这题（同一文本同一提示，一模定稿 18 题「（2）①②③」五次里一次读成 3 问，edu-core#3164）。回包 `votes` 是读了几遍；`PICO_EXAM_STRUCTURE_VOTES=1` 关掉。读页图不投票。

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
  "rubric": "评分标准、给分点、补充说明。没有则空字符串。禁止写进 answer。",
  "analysis": "解析、解题过程。没有则空字符串。禁止写进 answer。",
  "score": 分值(int) 或 null；没有分值必须 null，禁止默认填 1,
  "options_count": 选择题选项数，默认 4；非选择题 null,
  "sub_count": 小问数：只数 (1)（1）1) 这一层；①②③ 是同一小问里的多个空，不是小问；没有小问为 1,
  "subs": [
    { "sub": 1, "answer": "本小问的答案（多空每空前标号：①第一空 ②第二空，第一空也标）", "score": 本小问分值(int) 或 null }
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
- 纯答案卷：有什么收什么，rubric、analysis 可以为 ""。
- 详细解析版：answer 只留答案；解析、解题过程放 analysis；评分标准、给分点、补充说明放 rubric。两样都不要丢，也不要混。
- 答案含图 / 作图题：has_figure=true，并给够 sub_count。
- answer 里保留原卷的小问号 (1)(2) 和空号 ①②，不要抹掉：edu 靠它们把答案落到答题卡的每一行每一空。
- 有小问的题：answer 写成「（1）…（2）…」，一问一段；同一问里有几个空就每空前标号「①… ②…」，第一空也标 ①，不要用「；」把几问连成一串。原卷有 (1)(2) 号但答案卷没写号，也要按原卷小问对上号。
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
以下是老师的答案卷原文{{subject}}。必须抽出全部题号。答案放 answer，解析放 analysis，评分标准 / 补充说明放 rubric。非选择题不要空着。只返回 JSON 数组。

{{text}}
```
<!-- /prompt:user_text -->

<!-- prompt:user_page -->
```text
这是老师答案卷{{subject}}的一页整图（可能是多页中的一页）。抽出本页可见的全部题号：答案放 answer，解析放 analysis，评分标准 / 补充说明放 rubric。本页只看到细则、答案在别页的题，也要出一条（answer 留空、rubric 写细则）。本页顶上、第一个题号之前的内容（没有新题号的小问、答案、细则表、解析）是上一页最后一题的续写：单独出一条，number 写 0、continued 写 true，按卷面 (n) 号放进 subs，细则放 rubric；不要猜题号，不要并进本页别的题。只返回 JSON 数组。
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

<!-- prompt:user_pages_structure -->
```text
这是老师试卷或答案卷{{subject}}的全部页，按页序排，每张图前写着第几页。只抽结构：全卷每题的题号、题型、选项字母个数、小问、横线、分值；不要做题。
大题标题里写的规则管到下一个大题标题为止，跨页也算：「每小题 2 分」就是这一大题里每题 2 分；「有一项或多项符合」「不定项」就是这一大题每题 multi_choice。跨页的题（题干、选项、小问在下一页接着写）算一题，不要拆成两条、不要出 number 0。每题多写一个 "pages": 这题占的页（图前写的那个数），跨页写全，如 [7, 8]。只返回 JSON 数组。
```
<!-- /prompt:user_pages_structure -->

<!-- prompt:system_solve -->
```text
你在做这套试卷，给答题卡填标准答案。结构（题号、题型、选项数、小问）已经定了，不许改。

只返回 JSON 数组。每题：
{
  "number": 题号(int),
  "type": 与结构相同,
  "answer": "选择题只写字母；填空/解答写要点，不要解析",
  "rubric": "评分要点：每问按步骤给分点；没有则空字符串",
  "analysis": "简要解析",
  "score": null,
  "options_count": 不要改,
  "sub_count": 不要改,
  "subs": [{ "sub": 1, "answer": "本小问答案（多空每空前标号：①第一空 ②第二空，第一空也标）", "score": null }],
  "blanks": [{ "sub": 1, "text": "该空答案", "flex": "fixed" | "open" }],
  "quote": ""
}

规则：
- 看得见题干的题，题号表里的每一题都要写出答案，不要空着，禁止从中间题号起笔。
- 看不见题干的题（在试卷别的页上）不要输出，不要猜、不要写「本题不在本页」之类的话；别的页会做。
- 不要新增题号，不要删题号，不要把三选改成四选。
- 解析放 analysis，评分要点放 rubric，都不要写进 answer。
- 有小问的题：answer 写成「（1）…（2）…」一问一段，subs 一问一条，条数等于 sub_count，每条的 answer 都要写上（和 answer 里那一问一致）；没有小问 subs 为 []。一问里有几个空就答几个，每空前标号「①… ②…」（第一空也标 ①；只有一个空不标），一个不落。
- 卷上已经印了答案 / 解析的（教师版、讲评课件），照印的定答案，不要另做；印的解析能推出答案的（如「A、C 正确」），照它推出的填。
- analysis 是给学生看的解题过程，只写一遍定稿：不写推敲、改口、自我怀疑（「等等」「重新分析」「这不可能？」），不写题号表、页面、题目结构的说明（「上一页缺资料」「题干标号重复」）。选择题最后一句写「故选 X」，X 与 answer 一致。
- answer、subs、analysis 的结论必须一致；拿不准就在 analysis 里写明哪一步拿不准，不要两种答案都写。
- rubric：卷上印了分值的照印的写；没印的按小问写给分点。不要写「试卷缺失」「看不到」之类的话。
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
题号表（整卷的题；只做本页看得见题干的那些）：
{{roster}}

这是老师试卷{{subject}}的一页。只做本页看得见题干的题，本页看不见的题号不要输出（别的页会做）。题干从上一页接过来的，按本页能看到的部分作答。后面附了下一页的，本页最后一题的选项、题干、配图接到下一页的，连起来读完整再作答；下一页起头的新题不要做。不要改结构。只返回 JSON 数组。
```
<!-- /prompt:user_page_solve -->

<!-- prompt:system_paper -->
```text
你是试卷录入员，不是在做题。老师上传的是学生手里的试卷（可能是 Word 原文、PDF、手机拍的照片），有的是带答案 / 解析 / 评分标准的教师版。

把卷面上的每一题原样录下来，给题库和阅卷用。只返回 JSON 数组，不要其他文字、不要 Markdown 围栏。每题一个对象：
{
  "number": 题号(int),
  "type": "single_choice" | "multi_choice" | "fill_in_blank" | "short_answer",
  "section": "大题名或 null",
  "score": 卷面分(int) 或 null,
  "options_count": 选择题列出的选项字母数；非选择题 null。禁止默认 4,
  "sub_count": 小问数：只数 (1)（1）这一层；①② 是同一小问里的空；没有小问为 1,
  "subs": [{ "sub": 1, "answer": "卷上印的本小问答案，没有则空", "score": 卷面印的本小问分(int) 或 null }],
  "blanks": [{ "sub": 1, "text": "", "flex": "fixed" | "open" }],
  "has_figure": 本题题干或材料里有图则为 true,
  "stem": "题干原文：题号后面的全部文字，含选项（A．… B．…，一项一行）和各小问的问句；不含题号本身、不含共用材料",
  "figures": [{ "box_2d": [上, 左, 下, 右] }],
  "answer": "卷上印的标准答案；卷上没有就空字符串，不许自己做题",
  "analysis": "卷上印的解析 / 解题过程；没有就空字符串",
  "rubric": "卷上印的评分标准 / 给分点 / 补充说明；没有就空字符串",
  "uncertain": 本题有看不准的字为 true,
  "quote": "定位题干的一小段（不超过 40 字）"
}

几道题共用的材料（「阅读下面的文字，完成 1~5 题」后面的文章、文言文、诗歌、图表材料、实验背景）不放进任何一题，单独出一条：
{ "kind": "material", "material_for": [这段材料对应的全部题号], "material": "材料原文（含标题、作者、出处、注释）", "figures": [{ "box_2d": [上, 左, 下, 右] }] }
按卷面顺序排：材料那条排在它的题前面。

规则：
- 完整抽出全部题号，选择题和大题都要出，不跳题。
- 逐字照抄卷面，不纠错、不改写、不概括、不省略；看不准的字照最像的字形抄，uncertain 写 true。
- 公式、上下标、分数、根号写成 LaTeX，用 $…$ 包起来（如 $\frac{\sqrt{2}}{2}$、$S_{3n}$、$x^2$）；化学式同理（$\mathrm{H_2O}$）。
- 图不要描述；在题干里图出现的位置写「[图]」。题干原文里已经有「[图1]」「[图2]」这样的标记就原样保留在原位，不要改号、不要删。
- figures：只在看整页图时填，每张图一条，box_2d 是这张图（含图里的字母标注、图题）在本页上的外框 [ymin, xmin, ymax, xmax]，按本页高、宽归一到 0–1000 的整数；只框图，不框题干文字、不框选项文字。读的是文字原文时 figures 为 []。
- 题型看题干：下列一项是 → single_choice；有几项符合 / 不定项 → multi_choice；横线填空 → fill_in_blank；要写过程、简答、作图、写作 → short_answer。
- 有小问的题 subs 一问一条（没有小问为 []），卷面没印本小问分就是 null，不要平摊题分。
- 写作题只有一篇作答：sub_count = 1，subs 为 []；「内容包括 / 注意」下的 (1)(2) 是要点，不是小问。
- 非选择题 blanks 按横线 / 作答空数，text 留空。
- 答案、解析、评分标准只抄卷上印的；纯试卷三项都是空字符串。answer 只放答案，过程放 analysis，给分点放 rubric，三者不要混。
- stem 只放题干：卷上【答案】【解析】【详解】【分析】【点睛】后面的内容放进 answer / analysis，一个字也不进 stem（课件常把解析印在题下，读进题干就把答案露给学生了）。
- 附了本页文字层的，字照文字层抄（图上看不清、被色块盖住的答案、解析、分数，文字层里有就照抄）；题的先后、小问层次、图的位置仍看页图。
- 看不见的题不要编；一题都没有就返回 []。
```
<!-- /prompt:system_paper -->

<!-- prompt:user_text_paper -->
```text
以下是老师的试卷原文{{subject}}。按卷面把每一题录下来：题干、选项、小问、共用材料、分值；卷上印了答案 / 解析 / 评分标准的一起抄，没有就空着，不要做题。只返回 JSON 数组。

{{text}}
```
<!-- /prompt:user_text_paper -->

<!-- prompt:user_page_paper -->
```text
这是老师试卷{{subject}}的一页整图（可能是手机拍的，有倾斜、阴影）。按卷面顺序把本页看得见的每一题和共用材料录下来：题干、选项、小问、分值，图在本页的外框写进 figures；题头在页中、页尾的题也要出；整页都是材料也要出材料那条。本页顶上、第一个题号之前的内容是上一页的续写，单独出一条、continued 写 true，不要猜题号：续的是材料（文章、诗文、注释）就写 { "kind": "material", "continued": true, "material": "续写的原文" }；续的是题（没完的题干、小问、选项）就写 number 0、续写的文字放 stem；小问照卷面的 (n) 号写进 subs，本页从（2）接着写就是 sub 2，不要从 1 重新数。卷上印了答案 / 解析 / 评分标准的一起抄，没有就空着，不要做题。只返回 JSON 数组。
```
<!-- /prompt:user_page_paper -->

## 成功 / 失败（金标：生物 XLM1）

- 成功：1–12 `C D C B D A C D C D C A`，13–16 `ACD / AC / ABC / BC`，17–21 有非选择要点；带细则版 17–21 的 `rubric` 非空。
- 试卷录入（`paper`，edu-core#3157，10-15 实测 gemini-3.8-flash）：九科联考物理 12 页 → 15 题、18 张图框全对位（≈40–120 s）；语文 11 页 → 5 段共用材料跨页接齐、各挂对题；数学手机斜拍页公式逐字成 LaTeX。
- 失败对人话：`extract.empty`（模型没抽出题号）、`model.failed`（上游没做成）、`model.unconfigured`（没配脑）。禁止托底。

## 运行参数（适配层，不改语义）

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `PICO_EXAM_EXTRACT_CONCURRENCY` | `4` | 逐页并发上限。edu 一次最多送 24 页（整份试卷，edu-core#3157），4 页一波。曾因 ECS 出口代理重置并发上传而设 1（pico #979）；2026-09-13 出口改为经 DMIT 链式后并发上传实测正常，恢复并发（edu-core#1506）。若上游再抖，先调回 1 而不是改语义 |
| `PICO_EXAM_EXTRACT_ATTEMPTS` | `5` | 单页 / 单块的尝试次数，退避 3s / 8s / 20s / 45s（代理重置成簇出现、单次只耗 ~1 s，拉长跨度比密集重试有效）；只重试瞬时错误，配置错误（`model.unconfigured`）不重试 |
| `PICO_EXAM_EXTRACT_PAGE_SECONDS` | `240` | 单次模型调用超时 |
| `PICO_EXAM_EXTRACT_PAGE_EFFORT` | `low` | 读一页图的推理力度：`low`（同文本路，flash 不思考）或 `medium`（显式开思考；#1183 后 flash 默认不思考，不能再靠「上游默认」）。在 edu 送 150 dpi 原生页图（1092×1648）的前提下，21 次对照 `low` 正确率不低于 `medium`，细则页快一半；72 dpi 小图上的误读是图糊不是力度（edu-core#1506）。图再变糊先修图，不要先调这里 |
| `PICO_EXAM_EXTRACT_SOLVE_EFFORT` | `medium` | 做题（`solve`）的推理力度，只管做题，读结构 / 读卷不受影响。不推理时模型把推敲写进解析（「等等，重新分析」）、同一题写两遍，答案和自己的解析对不上（edu-core#3164）。`low` 关掉 推理不封顶（Gemini 经 New API 不认推理预算）：一页推爆时限或输出上限、答案截断或没有 JSON 时，这页不推理再读一次，不丢题，并提示「第 N 页没用推理做题，AI 答案请重点核对」 |
| `PICO_EXAM_EXTRACT_THINK_TOKENS` | `16000` | 开推理时另加在输出上限上的 token（推理也算输出，不另给就把答案挤掉：一模 21 题那页推 23k，第 20、21 题没做出，edu-core#3164） |
