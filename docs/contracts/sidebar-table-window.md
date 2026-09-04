# Contract: sidebar table graded load

```
STATUS: BINDING for Pico · REQUIREMENT for edu-core
VERSION: 1.0
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

## Pico (this repo · done on the Pico side)

| Default | On ask |
|---------|--------|
| Sidebar hint: page title / filename only | `inspect_document` windows: `start_row` / `start_col` / `max_rows` / `max_cols` |
| Do not claim full read from `page.table` | Repeat until `leftover_rows` and `leftover_cols` are 0 |

`page.table` from school is a viewport, not the ledger.

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
