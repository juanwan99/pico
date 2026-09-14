# 知识库入库 · 格式矩阵与返回码（`POST /v1/kb/ingest`）

```text
DOC: docs/KB-INGEST-FORMATS.md
STATUS: BINDING · 2026-09-14（#994 阶段 2 · #997 · 对仓 #990）
引擎: Docling 格式后端（Office/markup）· pypdfium2 文字层（PDF）· RapidOCR（扫描 PDF / 图片）
镜像: no-torch（T-PICO-NO-TORCH）。禁止 docling.DocumentConverter（导入即拉 docling_parse/torch）。
```

edu 侧显示 `detail.message` 原文即可，不要再翻译。

## 支持矩阵

| 后缀 | 引擎 | `engine` | `tags` | 说明 |
|---|---|---|---|---|
| `.docx` | Docling `MsWordDocumentBackend` | `docling` | `docling` | 标题 / 段落 / 表格 → markdown |
| `.xlsx` | Docling `MsExcelDocumentBackend` | `docling` | `docling` | 每张 sheet 一张表 |
| `.pptx` | Docling `MsPowerpointDocumentBackend` | `docling` | `docling` | 标题 + 要点 |
| `.md` `.markdown` | Docling `MarkdownDocumentBackend` | `docling` | `docling` | |
| `.html` `.htm` | Docling `HTMLDocumentBackend` | `docling` | `docling` | |
| `.pdf` 有文字层 | pypdfium2 | `pdfium-text` | `pdfium` | 不渲页、不 OCR |
| `.pdf` 无文字层（扫描件） | pypdfium2 渲页 + RapidOCR | `rapidocr` | `pdfium` `empty-layer` `ocr` (+`ocr-truncated`) | 页数上限 `PICO_KB_OCR_MAX_PAGES`（默认 40），超出只读前 N 页并打 `ocr-truncated` |
| `.png` `.jpg` `.jpeg` `.webp` `.bmp` `.tif` `.tiff` | RapidOCR | `rapidocr` | `image` `ocr` | 一张图一份 |
| `.doc` `.xls` `.ppt` | — | — | — | **不转**。415，提示另存为 OOXML（回形针那条路会经 soffice 转，kb/ingest 不会） |
| 其它 | — | — | — | 415 |

**OCR 只在显式 `POST /v1/kb/ingest` 跑**（在线程里，不占事件循环；`PICO_KB_OCR_THREADS` 默认 2 核）。账本→Meili 的重投影 / 部署时 `reindex-all` / 回形针 sidecar 一律 `ocr=False`：扫描件在这些路上是快速 miss，标 `ocr-skipped`。现网 2026-09-14 教训：部署 reindex-all 把每份历史扫描件都 OCR 一遍，pico-api 400% CPU、事件循环被堵、health 超时。

OCR 模型：`rapidocr` 轮子自带 PP-OCRv6 det/rec small + cls mobile（中英），零下载；`/opt/docling-models/rapidocr-onnx.json` 若存在则覆盖。

实测（生产镜像 · 2026-09-14）：docx 首次 2s（后端 import），之后 <0.1s；xlsx/pptx <0.1s；单页扫描 PDF 约 4s；单张图约 1.7s；中文行识别完整。

## 返回码

| HTTP | `code` | 什么时候 | `message`（原样显示） |
|---|---|---|---|
| 200 | — | 读到内容 | 返回 `engine` `tags` `slices[]` |
| 400 | `empty` | 文字层空且 OCR 没认出字；或 Office 文件里没有文字 | OCR：「这份是扫描件或图片，OCR 没认出文字。换清晰一点的版本，或先转成带文字层的 PDF。」 其它：「文件里没读到文字。空文档、纯图形或受保护的文件都会这样。」 |
| 400 | `file.invalid` | base64 坏 / 无内容 | 「文件内容不是合法的 base64」等 |
| 413 | `file.too_large` | > 20MB | 「文件太大（上限 20MB）」 |
| 415 | `unsupported_format` | 不在矩阵内 | 「这种格式（.doc）知识库读不了。旧版 .doc 请先另存为 .docx 再入库。」 / 「这种格式（.xyz）知识库读不了。支持：docx / xlsx / pptx / md / html / PDF / png / jpg。」 |
| 422 | `ingest.failed` | 引擎抛出未归类异常（兜底） | 「这份没读出来。换个格式再试；持续失败请把文件名发给管理员。」 |
| 503 | `ocr_missing` | RapidOCR ONNX 找不到 | 「OCR 引擎没就位，扫描件暂时读不了。请管理员看镜像里的 RapidOCR 模型。」 |
| 503 | `docling_missing` | Docling 后端 import 失败 | 「文档转换引擎没就位，请管理员看镜像里的 Docling 后端。」 |
| 503 | `hf_offline` | 模型目录缺（历史遗留归类） | 「文档转换需要的模型没在机上，请管理员看模型目录。」 |
| 503 | `ingest.unavailable` | 入库包本身 import 失败 | |

## 记账（#990-3 核实 · 不改价）

`edu_kb_ingest` 每次调用记一条 `usage_events`（`source=kb_ingest` · `tokens_unknown`），成功失败都记，同内容同 `item_id` 去重。`bill_to` 只看票：带 `ai:school-run` → `school`，否则 `member`；请求体里的 `bill_to` 不能抬价。单测 `test_ingest_usage_success_and_payer`。

## 不做

- 不装 torch / docling 全家桶；不接 Docling PDF 管线（布局/表格模型）。
- 不把 OCR 接进回形针→模型那条路（#865 厚桥四层）。
- 不做手写识别承诺；RapidOCR 对手写基本不识。
