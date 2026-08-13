# pack-zombie-sandbox-s2 · 人眼帧（段 B）

```text
CARD: T-ZOMBIE-AND-SANDBOX-S2 (#516) 段 B
CLAIM-WB-DEGREE-WEB: NO
B3: forbidden
isolate_stronger_than_s1: Y (pico-sandbox sidecar · not LibreChat)
b2_human_in_loop: Y
jiaowu_wechat_required: N
8080/18088: sandbox worker must NOT bind
```

执行者（生产窗）补帧；本目录 **不** 放伪造 PNG。下列是应拍的画面，文件名建议与表一致，单帧 >20KB。

| 建议文件 | 拍什么 |
|----------|--------|
| `isolate-session.png` | 隔离会话可见：B2 view 页（横幅「请在此画面自行登录，不要在聊天里发送密码」）+ 公开页（example.com 即可），不是 LibreChat 进程里的 Chrome |
| `b2-login-prompt.png` | 同一画面含人在环文案；密码框在 view 页而不是聊天输入框 |
| `v390.png` | 视口约 390 宽的一帧（手机宽） |
| `s1-inspect-raster.png` | 自己的 HTML 仍能 inspect + 真 PNG 光栅（S1 保留） |

不要拍：微信/教务登录成功（不是过关条件）。若那些站挡住自动化，拍人话失败文案即可。
