# pack-result-web-pane · 结果区网页屏

```text
DATE: 2026-08-13
CARD: T-PACK-RESULT-WEB-PANE #533
BASE/PRODUCT at start: 1e9a02144c7036cf12385b9fc056d66b627af053
CLAIM-WB-DEGREE-WEB: NO
VERDICT_AUTHORITY: NONE
PRODUCT PASS: unsigned
```

结果区「网页」态（390 宽）。画面来自 sidecar Chromium 真页（example.com / IANA）+ 公开登录 fixture。
密码框在结果区内；帧里只显示掩码。不是独立 `/view`，也不是 invoke JSON。

| 文件 | 字节 | 宽 | 说明 |
|------|------:|----|------|
| `01-pane-example-com.png` | 32467 | 390 | 出屏：网页态 + example.com + 登录文案 + 密码框 |
| `02-pane-after-click-iana.png` | 72456 | 390 | 点击 Learn more 后 IANA |
| `03-pane-login-masked.png` | 28369 | 390 | 登录框；密码已打码 |
| `v390.png` | 32467 | 390 | 与 01 同帧 |

微信/教务不要求成功。未自签 PASS。
