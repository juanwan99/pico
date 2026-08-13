# pack-zombie-sandbox-s2 · 人眼帧

```text
DATE: 2026-08-13
tip: a84161375ef2dfe2112a9068a38bd3390c431d3a
login: https://pico.aivia.asia/login 200
CLAIM-WB-DEGREE-WEB: NO
zombie_audited: N=1076
zombie_marked: N=0
#159: CLOSED
isolate_stronger_than_s1: Y
b2_frame: Y
v390: Y
sidecar: pico-sandbox :18767 (not 8080/18088)
```

沙箱浏览器在独立 sidecar（uid 65532、cap_drop ALL）。老师可打开人在环画面；聊天里写明不要发密码。
微信/教务不作为过关条件。跨账号 session 404；127.0.0.1:18765 与 10/8 为 web.denied。

| 文件 | 说明 |
|------|------|
| `b2-view.png` | 公网打开 example.com 沙箱会话，过程含 sandbox_browser_open，禁止聊天交密码 |
| `isolate-session.png` | 执行步骤可见隔离会话/sidecar 工具 |
| `v390.png` | 视口约 390 宽 |
