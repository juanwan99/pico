# Pico 双档性能对照表

tip 实查：`8dbac365c9ca411e5110d45e769b814f3cb7fb2a`（#478 合后装机 · 2026-08-12）

## 目标

- Pico 快速 = `pico-fast` → `deepseek-v4-flash` + thinking **off** + 紧预算
- Pico 深度 = `pico-deep` → `deepseek-v4-flash` + thinking **on** + 熔断

## 预算对照（代码）

| 模式 | backend_model | thinking | max_steps | max_tokens | 熔断 |
|------|---------------|:---:|---:|---:|:---:|
| pico-fast | deepseek-v4-flash | off | 12 | 8000 | 否 |
| pico-deep | deepseek-v4-flash | on | 24 | 32000 | 是 |

## 真 tip / 真 run_id（#478 装后 · 禁止编造）

| 模式 | 题型 | wall_s | steps | tool_exec | art | oom | settle | run_id | tip | notes |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| **pico-fast** | HTML 交件（UI 选 Pico 快速） | **9.42** | 6 | 3 | 2 | N | Y | `c2a306cd-3a8a-49c7-bb49-4a65cda3a584` | 8dbac365… | visual-gate fast-c1 · **model 列=pico-fast** · skill 不盖 fast · human_page |
| pico-fast | 短烟列表 | 6.79 | 4 | 2 | 3 | N | Y | `0bbe56b2-a769-4607-abc8-913404207b01` | 8dbac365… | d-list · model=pico-fast |
| **pico-deep** | 深度推理（UI） | **10.68** | — | 0 | — | N | Y | `45bbe6ae-8f74-495b-8afb-43e966353574` | 8dbac365… | visual-gate deep-hard · model=pico-deep · monologue clean |

wall_s 来自 `runs.started_at/ended_at` 实算。

### 装前对照（#469 tip e742474 · 考古 · 不作本卡 Ready）

| 模式 | 题型 | wall_s | run_id | notes |
|---|---|---:|---|---|
| pico-deep | HTML（skill 曾强制 deep） | 11.36 | db76e401-ea8b-4697-9ce8-5d5ab69037b4 | #478 前缺陷 · 已修 |
| pico-fast | API 短答 | 2.83 | b02988f1-4ee2-462f-a155-d4f58f2fb01a | API 直打 |

## 结论

- **真 pico-fast 交件**已有 UI run_id + 帧；skill 路径不再覆盖显式 fast（#478）。
- 深度档 UI run settle 可证。
- 熔断契约单测锁定；本窗未做无限空转 hang 真机（N/A · 单测已锁）。
