# Contract: sidebar table graded load

```
STATUS: BINDING for Pico · REQUIREMENT for edu-core
VERSION: 1.1 (2026-09-09 · #975: inspect_document retired by #953; Pico has no window hand today)
OWNER_PICO: juanwan99/pico
OWNER_SCHOOL: juanwan99/edu-core (not implemented in this repo)
```

## Goal

Do not treat one slice as the whole table.

```text
No ask  → current page name / filename only. Do not claim the file was read.
Has ask → load until leftover_rows = 0 and leftover_cols = 0.
```

Pico must not invent a second school table SoT. School still owns the left page.

## Pico (this repo · current state)

| Default | On ask |
|---------|--------|
| Sidebar hint: page title / filename only | **Uploaded** office files: read with `sandbox_office_lib` (full file, isolated python) |
| Do not claim full read from `page.table` | **Left-page web table:** Pico has no window hand since `inspect_document` left the gateway (#953). The model must say the table is not fully read and fill only from seen cells + empty columns |

`page.table` from school is a viewport, not the ledger. The window
(`start_row` / `leftover_rows` …) must come from the school side; Pico will
not rebuild an inspect projector to page a table it does not own.

## edu-core must ship (later window · not this PR)

Today `slimScreen` / `shapeAccessory` always send `columns.slice(0, 16)` and `rows.slice(0, 12)` with no leftover. Pico cannot page the left-page 数据表.

School must add, without Pico writing edu-core:

1. **Default accessory:** `page.title` (and filename if any). Do not dump 16×12 cells unless the teacher asked to work the grid.
2. **When the teacher asked:** a window on the open web table, same idea as Pico inspect:
   - `columns`, `rows` for this window
   - `start_row`, `start_col`, `end_row`, `end_col`
   - `total_rows`, `total_cols`
   - `leftover_rows`, `leftover_cols`
3. **A follow-up hand** Pico can propose (or school can send on the next turn) to fetch the next window until leftovers are 0. Confirm still writes; this hand is read-only.
4. Cap one window (16×12 is fine). Cap is a page, not a lie that the table is that small.

Until that ships, Pico will not claim the left-page table was fully read, and will not `insert_col` just because the slice is 16 columns.

## Out of scope here

- Raising the school 40-field schema cap
- Pico HTTP to `/v1/schools/.../web-tables` (that would be a second SoT)
- Editing edu-core in the Pico window
