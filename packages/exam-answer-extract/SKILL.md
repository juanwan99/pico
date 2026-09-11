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
      "has_figure": false,
      "source": { "page": 3, "quote": "定位原文的一小段" }
    }
  ],
  "pages": [{ "page": 1, "ok": true, "count": 12, "error": null }],
  "warnings": []
}
```

- `score` 没有就是 `null`，禁止默认 1。
- `rubric` 与 `answer` 分离：细则默认折叠在题下，不进排版。
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
  "sub_count": 小问数，识别 (1)（1）1) ①；没有小问为 1,
  "has_figure": 答案或题目含需要作答的图则为 true,
  "quote": "原文里能定位这题答案的一小段（不超过 40 字）；没有则空字符串"
}

规则：
- 完整抽出全部题号。选择题和大题都要出，不要只返回选择表。
- 纯答案卷：有什么收什么，rubric 可以为 ""。
- 详细解析版：answer 只留答案；过程、解析、补充说明、评分标准全部放进 rubric，不要丢。
- 答案含图 / 作图题：has_figure=true，并给够 sub_count。
- 选择题：单个字母 → single_choice；多个字母 → multi_choice。字母必须逐题抄进 answer，不要合并成一串。
- 短填空 → fill_in_blank；要写步骤或作图 → short_answer。
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
这是老师答案卷{{subject}}的一页整图（可能是多页中的一页）。抽出本页可见的全部题号：答案放 answer，解析 / 补充说明 / 评分标准放 rubric。本页只看到细则、答案在别页的题，也要出一条（answer 留空、rubric 写细则）。只返回 JSON 数组。
```
<!-- /prompt:user_page -->

## 成功 / 失败（金标：生物 XLM1）

- 成功：1–12 `C D C B D A C D C D C A`，13–16 `ACD / AC / ABC / BC`，17–21 有非选择要点；带细则版 17–21 的 `rubric` 非空。
- 失败对人话：`extract.empty`（模型没抽出题号）、`model.failed`（上游没做成）、`model.unconfigured`（没配脑）。禁止托底。
