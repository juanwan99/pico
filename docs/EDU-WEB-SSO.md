# Edu web SSO (T-PICO-SSO-LOGIN)

School login is the only login the teacher sees. Pico workbench consumes a **one-time** edu ticket and opens as that membership.

| | |
|--|--|
| Ticket | HS256 JWT `aud=pico-web` · `jti` · TTL ≤ 90s · `school_id` + `membership_id` + `display_name` · optional `named_ids` (item UUIDs only) |
| Consume | `POST /v1/edu-sso/consume` on pico-api (loopback). Replay → 401 |
| Session | `GET /api/auth/edu-sso?ticket=` on LibreChat → host-only cookies, `SameSite=Lax` (cross-site first hop) → `/c/new` |
| Identity | LibreChat `eduId` = membership. Display name from school staff name (else login). Proxy header `school_id:membership_id` |
| Materials | Workbench lists/searches via `/v1/edu/materials` as this membership. **Default unchecked** (本场成员 included). Ticket `named_ids` are not pre-checked. Teacher ticks this turn. Unchecked → no school file bodies in the round. |
| Fail | Invalid/spent/expired ticket → Pico `/login?sso=used|expired|…` with a human line. Do not dump a password wall. Do not take down edu |

Forbidden: iframe, edu `/pico` subpage, parent-domain `.weiyuji.cn` cookies, field/student/page/material **bodies** on the ticket or jump URL, school-wide service dump, hot-patching a running container. Named item **ids** may ride the one-time ticket for audit only; consume must not persist them as default checks.

Formal release: merge to `main`, then `PICO_DEPLOY_SHA=<main-sha> bash scripts/prod-update.sh`.

手机任务可在 `POST /v1/tasks` 带 `source: "mobile"` 和可选的 `upload_ids`（最多 8 个本人经 `POST /v1/files` 上传、尚未挂到正式对话的图片 ID）。返回的 `task.conversation_id` 用于电脑上续改。
电脑左栏同步只看 `GET /v1/tasks` 最近 50 条任务，更早的手机任务不补。导入的用户消息显示照片张数，续改时 Pico 仍可读取原图。
