# Contract: edu sidebar session

```
STATUS: BINDING for Pico · REQUIREMENT for edu-core
VERSION: 1.0 (2026-09-09 · #975 T-SIDEBAR-WIRE)
OWNER_PICO: juanwan99/pico
OWNER_SCHOOL: juanwan99/edu-core (not implemented in this repo)
UPSTREAM DESIGN: edu-core#604 (壳级 Pico 拟议层 · 2026-08-15 业主锁) · edu-core#829 (人看到的 = AI 看到的 · AI 权 = 人权) · edu-core#833 (会话跟人走，手跟页走)
```

## 0. One sentence

The sidebar is the same Pico as the workbench (same true Pi, same CORE hands,
same ledger), embedded next to a school page. It sees only **this teacher,
this page, this conversation**, and can **propose** changes to the left page
that the school executes after the teacher confirms.

## 1. Request shape (edu → `POST /v1/chat/completions`)

| Part | Requirement | Why |
|------|-------------|-----|
| `Authorization` | edu-minted JWT; `school_id` / `membership_id` come from claims only | AI 权 = 人权 |
| `messages[0].role=system` | contains the marker `附属，不是用户要求` and the page short profile as JSON (`{"page": {"title": …, "table"?: …, "affordances"?: […]}}`) | Pico recognises a sidebar turn by this marker, nothing else |
| `X-Conversation-Id` | **required**. edu generates it per **teacher + page** (same lifetime as its `bindKey` brain key). New id when edu clears the brain (logout, 新对话, 换校). | Pi memory lives in a session file keyed by `school / membership / conversation`. Pico does **not** replay `messages[]` history on the Pi path. |
| `model` | any allowed id; a sidebar turn that is not json_only always runs on Pi | same hands is not a side effect of the SKU string |
| `allowed_tools` | ignored for sidebar turns (`[]`, web-only lists are not a castration) | #905 |
| `affordances[]` | optional; in `metadata.affordances`, or in the system JSON (`affordances` / `page.affordances`), or in the json_only user JSON | see §3 |
| `"output":"json_only_no_files"` / `X-Pico-Output` | the one-shot propose contract (#577); unchanged by this document | |

## 2. What Pico guarantees on a sidebar turn

1. **No cabinet.** SYSTEM never carries this teacher's workbench day-use block (recent ledger titles). #761.
2. **No cross-teacher session.** Session dir is `school / membership / conversation`; two teachers on the same page-keyed conversation id never share a Pi session file.
3. **History semantics.** Pi path ignores `messages[]` beyond the last user turn; continuity comes from the session file above. If edu omits `X-Conversation-Id`, every turn is a fresh session (allowed, but the rail is then stateless).
4. **Same hands.** CORE (`generate_html_document`, `sandbox_office_lib`, `generate_image`, `workspace_*`, `web_*`, `kb_search`, `ask_user`, sandbox doors). Thinking off; tool progress rides `content` so the rail can show it.
5. **Left-page hand.** When `affordances[]` is present: one extra tool `propose_page_mutation` (contracts/tools.md §4.7). Otherwise the model has no way to touch the left page and must say so.

## 3. Mutations envelope (Pico → edu)

Whenever the request carried `affordances[]`, the response has a **top-level**
field, present even when empty:

```json
{
  "id": "chatcmpl-…",
  "choices": [{ "message": { "role": "assistant", "content": "已拟好两处改动，请在左边确认。" } }],
  "pico_mutations": [
    { "affordanceId": "input:lesson:l1:weekly", "params": { "weekly_lessons": 5 },
      "label": "英语 周课时", "tier": "work", "status": "staged" }
  ]
}
```

- Streaming: the same field rides the final `finish_reason:"stop"` chunk (next to `usage`).
- `affordanceId` is always one of the request's ids. `params` is opaque to Pico. `tier` is copied from the affordance (`work` default, `final` for 回写/进绿/授权 — edu keeps them in separate confirm packs, edu-core#604 §5.3).
- The human `content` stays human: no JSON blob for the shell to parse.
- Pico also writes one ChangeProposal ledger row (`status=proposed`) per turn with mutations — the audit trail (contracts/change-handoff.md). Confirm/execute is the school's; Pico writes nothing to the school.

edu must: show the confirm card from `pico_mutations`, run its own commands after confirm, and **not** take `content` prose as instructions.

## 4. Left-page table reads

`page.table` is a 16×12 viewport, not the table. Pico has no window hand for the
left-page web table (contracts/sidebar-table-window.md v1.1). Until the school
ships a paging hand, the model fills only from seen cells + empty columns and
says the table is not fully read.

## 5. Out of scope

- Page-level memory (edu-core#498 L4) — later stage.
- Pico executing any mutation, calling school commands, or writing school data.
- A second proposal object: `pico_propose_change` is legacy (hosted/Kimi, `/v1/tools/invoke`), not on the true-Pi gateway.
- Rebuilding the json_only propose path — unchanged in this stage.
