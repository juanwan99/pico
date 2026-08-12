# Dual-mode evidence matrix · tip 8dbac365

## 任务卡 #479 T-DUAL-CLOSE-478

| ID | 结果 | 证据 |
|---|---|---|
| D1 列表仅两档 | **PASS** | Landing 下拉仅 Pico 快速/深度 · `d-list/model-dropdown.png` · models-ui.json DIRTY=[] |
| D2 默认 fast | **PASS** | 芯片默认 Pico 快速 |
| D3 真 pico-fast 交件 | **PASS** | run `c2a306cd-3a8a-49c7-bb49-4a65cda3a584` model=**pico-fast** · fast-c1 V0–V3 human_page |
| D4 pico-deep | **PASS** | run `45bbe6ae-8f74-495b-8afb-43e966353574` model=pico-deep · deep-hard 帧 |
| D5 tip 对齐 | **PASS** | main=deploy=公网 tip=`8dbac365c9ca411e5110d45e769b814f3cb7fb2a` |
| P1 PERF 真 run_id | **PASS** | PERF.md 已回填 · 无 PENDING |
| P2 skill 不盖 fast | **PASS** | HTML 交件 run model=pico-fast（#478 fix） |

## 帧路径

```text
docs/evidence/pack-dual-mode-perf/
  d-list/     model-dropdown.png + V0–V2
  fast-c1/    V0–V3 (真fast交件)
  deep-hard/  V0–V2
  PERF.md · MATRIX.md · README.md
```

CLAIM-WB-DEGREE-WEB: **NO**
