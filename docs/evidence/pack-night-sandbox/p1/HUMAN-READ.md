# P1 人测 · T-NIGHT-SANDBOX-COMPUTER

```text
DATE: 2026-08-14
BASE:  9beeba6e1589562ad6a7ea8a5d5c6e597668dd72
PRODUCT at CLAIM: e8c0ad7757e65f98c351dc7182d3c1ae1b2c6e82
LOCAL: Playwright against LibreChat + pico-api + sandbox_worker
CLAIM-WB-DEGREE-WEB: NO
```

Playwright 当真老师点。不是 Jest / API 200。

| 条 | 结果 | 帧 |
|----|------|-----|
| S1 打开 https://example.com → 右栏 Example Domain | Y | S1-example.png · S1-viewport.png |
| S2 打开课堂笔记.docx → Writer 标尺/菜单 + 正文 | Y | S2-writer.png · S2-viewport.png |
| S3 中栏无成品条 / 气泡预览 | Y | S3-chat-clean.png |
| S4 390 关右栏仍能打字 | Y | S4-390.png |

本地聊天 403 是缺 DeepSeek key，不挡沙箱屏。公网合装后再跑 S1 S2。
