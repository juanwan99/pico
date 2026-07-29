# Pico

独立 AI 底座（Phase 1+）。

## Product shell

**LibreChat** (`apps/librechat`) — MIT 开源壳，已接 Pico OpenAI 兼容 API。

- 预览入口：:8080 / :8000 → LibreChat :3080
- 后端：Pico API `127.0.0.1:18765`
- 演示：允许注册；`teacher@example.com` / `pico-demo-123`

详见 [docs/OSS-SHELL.md](docs/OSS-SHELL.md)。

```bash
./scripts/run-product.sh
```
