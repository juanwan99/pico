# pack-b2-ship · 公网装车后真 Chromium 帧

```text
DATE: 2026-08-13
CARD: T-SANDBOX-B2-SHIP #524
MERGED: 2400db340edc38bc105eac3b4e8e1a02c6ba6499  (#523 + hotfix #525)
PUBLIC_TIP_AT_CAPTURE: 2400db340edc38bc105eac3b4e8e1a02c6ba6499
login: 200
CLAIM-WB-DEGREE-WEB: NO
live_click: Y
real_browser: Y
fake_banner_gone: Y
VERDICT_AUTHORITY: NONE
PRODUCT PASS: unsigned
```

装车后在现网 pico-api（origin `127.0.0.1:18765`，公网 tip 已对齐）打开 example.com，点 Learn more。像素来自 sidecar Playwright Chromium 390×844，不是合成横幅。

| 文件 | 字节 | 说明 |
|------|------:|------|
| `viewport-example-com.png` | 20194 | 真 example.com |
| `v390.png` | 20194 | 同帧 390 宽 |
| `viewport-after-click.png` | 63956 | 点击后真 IANA Example Domains |
| `capture-meta.txt` | — | URL/title/坐标 |

验收：`127.0.0.1:18765` → `web.denied`；跨账号 view/screenshot → 404。
