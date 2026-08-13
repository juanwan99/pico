# pack-b2-real-browser · 人眼帧（真 Chromium viewport）

```text
DATE: 2026-08-13
BASE: 6f089b96ce2154df9a9c726dd5f384bd89ddd755
PRODUCT: a84161375ef2dfe2112a9068a38bd3390c431d3a (live tip only; not merge base)
login: not claimed
CLAIM-WB-DEGREE-WEB: NO
real_browser: Y
click_navigates: Y
fake_banner_gone: Y
v390: Y
sidecar: pico-sandbox Playwright/Chromium :18767 (not product UI ports)
VERDICT_AUTHORITY: NONE
PRODUCT PASS: unsigned
```

老师 view 像素来自 sidecar 无头 Chromium viewport（390×844），不是 httpx+S2 光栅横幅页。
点站内链接后 URL/title 变；Cookie 只在会话内存/tmpfs，随 destroy 死。

| 文件 | 说明 |
|------|------|
| `viewport-example-com.png` | 公开站 example.com 真 viewport（>20KB） |
| `viewport-after-click.png` | 点击 More information 后的画面；URL 离开 example.com |
| `v390.png` | 同一 viewport 的 390 宽帧 |
| `viewport-after-type.png` | 公开站输入框键入后的画面（wikipedia.org search） |
| `capture-meta.txt` | 前后 URL/title 与点击坐标 |

微信/教务不是过关条件。跨账号 session 404；127.0.0.1:18765、10/8、169.254、pico.aivia.asia 为 web.denied。
