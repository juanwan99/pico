# true_pi_bridge

Thin Node extension for **phase-1 true Pi RPC** (`#431`).

## Role

- Loaded by `pi --mode rpc --no-builtin-tools -e pico-gateway-tools.ts`（现网 argv。业主 2026-09-28 #1090 A：目标改为隔离工作区打开内建工具，实现走第 1 张卡）
- Registers Pico gateway tools (workspace/generate/verify + `web_search` / `web_fetch`)
- Each tool calls `PICO_TRUE_PI_TOOL_URL/v1/tool` with `PICO_TRUE_PI_TOOL_TOKEN`

## Not in this package

- host shell（隔离工作区 Pi 内建 bash 已放开 · #1090 A）
- 宿主任意文件系统
- delivery policy / skill OS
- second ledger

## Pin

```text
@earendil-works/pi-coding-agent@0.84.4
```

Phase-1 default production image does **not** require this binary; shadow/bypass only.
