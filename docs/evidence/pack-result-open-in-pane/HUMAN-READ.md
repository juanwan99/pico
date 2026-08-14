# pack-result-open-in-pane · 右侧打开文件/网站 + 宽/缩放/全屏

```text
DATE: 2026-08-14
CARD: T-RESULT-OPEN-IN-PANE #540
BASE:  b1e2ca8766d199f7a74f7f375e3102eeba7d5b71
PRODUCT at CLAIM: fa16db524a751d0da44a492cf874f4869bbfa6e4
CLAIM-WB-DEGREE-WEB: NO
VERDICT_AUTHORITY: NONE
PRODUCT PASS: unsigned
```

A 帖选定：**隐藏** iframe「浏览器」主入口，并入「网页」态。  
R1 调查：桌面真宽被 CSS `--pico-wb-result-w: 316px !important` 钉死；全屏只拉外壳、网页截图 `max-w-[390px]`。已改为默认 480 + 可拖，html/网页可缩放，全屏铺满内容。

| 文件 | 说明 |
|------|------|
| `01-open-html.png` | 宽区 html 铺满（1280，结果区 ≥480） |
| `02-open-site.png` | 打开 example.com → 网页态（宽区） |
| `03-open-source.png` | 点来源后同样进网页态 |
| `04-zoom.png` | 缩放 150%，比例可见 |
| `05-fullscreen.png` | 全屏后画面铺满工作台，不是 400 细条 |
| `v390.png` | 390 宽可用，无横向撑爆 |
| `06-live-tip.png` | 公网 tip 真页：打开 example.com → 结果区网页态 |
| `06-live-tip-workbench.png` | 同上整台（对话「打开 https://example.com」+ 右侧网页） |

Office：区内诚实下载，不承诺翻页。未自签 PASS。
G-live：公网 `git_sha=e8c0ad7757e65f98c351dc7182d3c1ae1b2c6e82`（合装 SHA）。

