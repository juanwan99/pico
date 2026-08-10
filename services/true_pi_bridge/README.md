# true_pi_bridge

Thin Node extension for **phase-1 true Pi RPC** (`#431`).

## Role

- Loaded by `pi --mode rpc --no-builtin-tools -e pico-gateway-tools.ts`
- Registers **only** the 7 Pico gateway tools
- Each tool calls `PICO_TRUE_PI_TOOL_URL/v1/tool` with `PICO_TRUE_PI_TOOL_TOKEN`

## Not in this package

- bash / host shell
- arbitrary filesystem
- delivery policy / skill OS
- second ledger

## Pin

```text
@mariozechner/pi-coding-agent@0.73.1
```

Phase-1 default production image does **not** require this binary; shadow/bypass only.
