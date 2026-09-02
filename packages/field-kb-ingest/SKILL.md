---
name: field-kb-ingest
description: Ingest a field file/page/table into edu KB slices via IBM Docling. Forced on green / page-table create. Do not invent a second parser.
allowed-tools: []
disable-model-invocation: true
user-invocable: false
always-apply: false
---

# field-kb-ingest

Engine = **IBM Docling** (MIT) for Office. PDF: **pypdfium2 text layer first**, RapidOCR only when the layer is empty (scans). Pico only adapts. Do not copy the source of record into Pico. Do not build a vector index or a Pico PDF kernel.

Triggers (edu enforces; people do not click「入库」):

- file turns green
- display page exists
- web table exists
- chat「再入库」reuses this same package

Output: `{ ok, engine, slices:[{ title, excerpt, tags }] }`.
Excerpt must be headers or paragraphs, not an empty name.
