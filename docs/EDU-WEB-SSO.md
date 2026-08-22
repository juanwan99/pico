# Edu web SSO (T-PICO-SSO-LOGIN)

School login is the only login the teacher sees. Pico workbench consumes a **one-time** edu ticket and opens as that membership.

| | |
|--|--|
| Ticket | HS256 JWT `aud=pico-web` · `jti` · TTL ≤ 90s · only `school_id` + `membership_id` |
| Consume | `POST /v1/edu-sso/consume` on pico-api (loopback). Replay → 401 |
| Session | `GET /api/auth/edu-sso?ticket=` on LibreChat → host-only cookies → `/c/new` |
| Identity | LibreChat `eduId` = membership. Proxy header `school_id:membership_id` |
| Fail | Invalid/spent ticket → Pico `/login`. Do not take down edu |

Forbidden: iframe, edu `/pico` subpage, parent-domain `.weiyuji.cn` cookies, field/student/page/material on the ticket or jump URL, hot-patching a running container.

Formal release: merge to `main`, then `PICO_DEPLOY_SHA=<main-sha> bash scripts/prod-update.sh`.
