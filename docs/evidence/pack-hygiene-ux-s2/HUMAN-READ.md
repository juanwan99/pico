# pack-hygiene-ux-s2 · 人眼帧

```text
DATE: 2026-08-13
tip: b8aaaca2ff78d97f29793de1aaa2c1f592cc7070
login: https://pico.aivia.asia/login 200
CLAIM-WB-DEGREE-WEB: NO
search_cite_frame: Y
preview_seen_frame: Y
inspect_raster: Y
v390: Y
hygiene_closed: #468 #470 #476 #479 #474
kept_open: #316 #449 #498 #505 #170 #159 #475
cross_account_preview: 404
loopback_inspect: web.denied
8080: edu-core-bff (Pico UI 18088)
```

老师聊天里能看见搜索来源（可点链接，未编造）。做一页 HTML 后能打开预览（h1「第一课」）。
`sandbox_preview_inspect` 回 title/h1，并落了 PNG 光栅（inspect-raster.png）。390 宽有一帧。

| 文件 | 说明 |
|------|------|
| `search-sources.png` | 公网一题搜索后，结果区/过程「来源」可点链接 |
| `preview-open.png` | `教案首页.html` 结果区打开，h1 第一课 |
| `inspect-seen.png` | 预览打开 + 过程含 sandbox_preview_inspect |
| `v390.png` | 视口约 390 宽 |
| `inspect-raster.png` | inspect API 产出的真实 PNG 光栅 |
