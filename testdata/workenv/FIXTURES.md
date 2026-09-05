# Frozen fixtures for workenv B1/A (do not retune after start)

Files: `gradebook.xlsx`, `roster.csv`. Freeze date 2026-09-05. Same model as live (`openai-responses` / `gpt-5.6-sol`). Hide list L before T1 and T2.

## T1

- File: `gradebook.xlsx` sheet `成绩`. A1 姓名 B1 平时 C1 期末 D1 总分. Rows 2–7 six students, D empty.
- Round 1 user: `把 D2:D7 写成期末40%加平时60%的公式，保存为 xlsx。`
- Open: D2 is `=B2*0.6+C2*0.4` or equivalent; Excel/openpyxl computes numbers.
- Round 2 after round 1 terminal, new `run_id`, same `conversation_id`: `把标题改成「三年二班成绩」，D 列公式别丢。`
- Open: title changed; D2 still a formula. Session is host `{school}/{conversation}/pico.jsonl`.
- Do not register `generate_xlsx_document` / `cell` / `value` / `values`.

## T2

- File: `roster.csv` columns `姓名,学号,组别`, 10 rows.
- User: `用这个 CSV 做两份东西：1) 按组别汇总人数的 xlsx；2) 一页说明 Word，点名各组人数。不要网页。`
- Open: xlsx has group counts; docx names the same counts. No new tool/Skill/schema.

## L (hide)

`generate_html_document` `generate_docx_document` `generate_pptx_document` `generate_xlsx_document` (patch params too) `edit_docx_document` `edit_pptx_document` `edit_xlsx_document` `sandbox_pptx_lib` `sandbox_workspace_exec` `workspace_list_files` `workspace_read_file` `workspace_write_file`.
