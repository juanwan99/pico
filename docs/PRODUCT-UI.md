<!-- STALE: nextchat paths obsolete; shell = apps/librechat. See CALIBRATION-NOW.md -->
# Product UI = NextChat (OSS) + Pico backend

```
NOT: hand-rolled three-column shell
YES: open-source full AI assistant product (NextChat / ChatGPT-Next-Web)
```

## Stack

| Layer | Choice |
|-------|--------|
| UI product | [NextChat](https://github.com/ChatGPTNextWeb/NextChat) (MIT) — full chat system |
| Backend | Pico API OpenAI-compatible `/v1/chat/completions` + agent ledger |

## Run

```bash
# API
make api   # :8000 — includes /v1/chat/completions

# UI
cd apps/nextchat
cp .env.local.example .env.local   # or use committed template
npx next dev -H 0.0.0.0 -p 8080
```

`.env.local` points `BASE_URL` at Pico and uses `OPENAI_API_KEY=pico-dev` (proxy key).

## What you get from NextChat (not reinvented)

- Full chat sessions / history / export
- Markdown, code, prompts, masks
- Settings / multi-model UX
- Mobile-ready product chrome
- Streaming chat UX

Pico owns: tools allowlist, Task/Run/Event ledger, safety pins.
