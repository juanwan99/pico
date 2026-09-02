# Edu web SSO (T-PICO-SSO-LOGIN)

School login is the only login the teacher sees. Pico workbench consumes a **one-time** edu ticket and opens as that membership.

| | |
|--|--|
| Ticket | HS256 JWT `aud=pico-web` · `jti` · TTL ≤ 90s · `school_id` + `membership_id` + `display_name` · optional `named_ids` (item UUIDs only) |
| Consume | `POST /v1/edu-sso/consume` on pico-api (loopback). Replay → 401 |
| Session | `GET /api/auth/edu-sso?ticket=` on LibreChat → host-only cookies → `/c/new` |
| Identity | LibreChat `eduId` = membership. Display name from school staff name (else login). Proxy header `school_id:membership_id` |
| Materials | Workbench lists/searches via `/v1/edu/materials` as this membership. **Default unchecked** (本场成员 included). Ticket `named_ids` are not pre-checked. Teacher ticks this turn. Unchecked → no school file bodies in the round. |
| Fail | Invalid/spent ticket → Pico `/login`. Do not take down edu |

Forbidden: iframe, edu `/pico` subpage, parent-domain `.weiyuji.cn` cookies, field/student/page/material **bodies** on the ticket or jump URL, school-wide service dump, hot-patching a running container. Named item **ids** may ride the one-time ticket for audit only; consume must not persist them as default checks.

Formal release: merge to `main`, then `PICO_DEPLOY_SHA=<main-sha> bash scripts/prod-update.sh`.
