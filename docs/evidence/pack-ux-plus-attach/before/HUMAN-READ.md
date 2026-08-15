# T-UX-PLUS-ATTACH · 公网 before

```text
tip: de6cbe01ce05d270df46760578ef9838b5f7f649
公网: https://pico.aivia.asia
拍法: 登录后真点 · 非 CSS 假帧
CLAIM-WB: NO
```

## P1 首页点 + · `P1-plus-menu-1280.png`

菜单看得到：快速 / 深度 / 上传附件。首页 composer 没有 overflow-hidden，所以「点 + 没反应」主要不是这一页裁菜单。

## P3 选完文件 · `P3-chip-1280.png`

点「上传附件」系统选文件会弹出（P2=Y），选完输入区 **没有文件芯片**。首页 Landing 不画 `FileFormChat`，人选了等于没选。

## P4 390 点 + · `P4-plus-menu-390.png`

菜单能出来。左缘贴边，但仍点得到。

## 对话页点 + · `P1-chat-plus-menu-1280.png`

已发出「只回一句：ping」。底栏点 +，**菜单在 DOM 里但画面上完全看不见**（被 `.pico-wb-composer { overflow-hidden }` 裁掉）。这就是业主说的「点加号没反应」。

帧哈希见 `report.json`。
