> **SUPERSEDED by KA-4 HARD (#288):** transitional `run_agent_loop` / `runner.py` **removed** (plan A).  
> Emergency→loop is a permanent **no-op**. Rollback = **redeploy previous tip**.  
> This file is historical soft boundary only.

# KA-4 软交付（不删 runner）

```
DOC: docs/KA4-SOFT.md
STATUS: BINDING soft boundary · #284
DATE: 2026-08-05
```

## 做

| 项 | 说明 |
|----|------|
| 默认路径 | 生产 `pico-agent` → **Kimi Agent**（RUNTIME=1 · 空 canary · scope=all） |
| 自研环可达条件 | **仅** `PICO_KIMI_AGENT_RUNTIME=0` **或** `PICO_LEGACY_AGENT_LOOP_EMERGENCY=1` |
| 断言 | 默认 settings / 生产默认组合下 **不**静默 dual-run 进 `run_agent_loop` |
| 文件 | **保留** `services/orchestrator/pico_orchestrator/runner.py`（回滚与 emergency） |
| 文档 | TRUTH O2/O3 · GAP KA-4 软 · STATE-NOW 现状句与 #278 已签一致 |

## 不做

| 项 | 说明 |
|----|------|
| 删除 `runner.py` / 卸依赖 | 禁止（本包硬边界） |
| 宣称「自研已物理清除」 | 禁止 |
| 改 prod-default 语义 | 空 canary=all 保持 |
| 全球 product PASS / orchestration complete | **NOT CLAIMED** |

## 回滚仍可用 loop

1. `PICO_KIMI_AGENT_RUNTIME=0` → recreate `pico-api` → health `scope=off`  
2. 或 `PICO_LEGACY_AGENT_LOOP_EMERGENCY=1` → recreate（默认仍须 0）  
3. 恢复：RUNTIME=1 · emergency=0 · 空 canary · batch 标签 → scope=all  

证据形态：health 字段 + 抽样 run `runtime=kimi-agent|null`（见 #278 K6）。

## 代码锚点

- 选择器：`pico_orchestrator.runtime.should_use_kimi_agent` / `run_agent_runtime`  
- emergency / allow_all：`Settings.pico_legacy_agent_loop_emergency` · `kimi_agent_default_all`  
- 单测：`tests/unit/test_kimi_runtime.py` · `tests/unit/test_ka4_soft.py`
