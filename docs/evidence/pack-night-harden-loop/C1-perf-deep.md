# C1 · pico-fast / pico-deep perf smoke

CLAIM: T-NIGHT-HARDEN-LOOP (SOLO) C1 anti-regression.

tip: `0b3bfa2a50dda498cb8a372c2f6d65d1956a4a56`  
host: shared ECS · LibreChat loopback `127.0.0.1:18088` (nginx `pico.aivia.asia` → 18088)  
CLAIM-WB: NO

## Wall-clock samples（post-502 fix · 实采）

| 模式 | wall_s | run_id | tip | notes |
|------|--------|--------|-----|-------|
| **pico-fast** | **2.208** | `chatcmpl-8af894e84d1a42f18ca172e6` | 0b3bfa2a… | 短答/API 烟测 · model=pico-fast |
| **pico-deep** | **2.634** | `chatcmpl-56dcb107f240407c80769c4f` | 0b3bfa2a… | 深度档烟测 · model=pico-deep |

wall_s 来自 run 实算（started_at → ended_at 或等价计时）。

## 关联

- Code anti-regression: `docker-compose.host.yml` `PORT: "18088"` — never `8080` on shared ECS (edu-core-bff).
- Baseline human read: [C0-baseline/HUMAN-READ.md](./C0-baseline/HUMAN-READ.md)
