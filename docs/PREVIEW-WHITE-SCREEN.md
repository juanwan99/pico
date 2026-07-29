# Live Preview 白屏诊断结论（Codex 方案落地）

```
DATE: 2026-07-29
STATUS: EVIDENCE LOG
LAST_WINDOW: Grok-Pico写入（LibreChat P0）
BRANCH_BASE: grok/pico-debrand-nextchat @ 429f85f4682fb525a77dee72df51b43ff05b4fac
```

## 结论（与 Codex 一致）

**根因在 Grok Live Preview 层，不在 Pico API / Mongo / LibreChat 主流程。**

### 决定性证据（本窗复测 2026-07-29）

| 路径 | 结果 |
|------|------|
| `GET http://127.0.0.1:8080/login` | **200** + HTML `title=Pico` + 文案 **「Pico 正在加载…」** |
| Playwright → `:8080/login` | **Welcome back** 登录表单可见；console **0 error** |
| `GET http://127.0.0.1:6014/login`（无 preview-auth） | **403 Forbidden**，**body 长度 0** |
| Playwright → `:6014/login` | body 空 → **纯白**；console 仅 403 |
| `GET :18765/health` | 200 JSON（API loopback；**不是**产品页） |
| `POST :6015/__control/target {"port":8080}` | `{"port":8080}` |
| 演示账号 | `teacher@example.com` / `pico-demo-123` 可 register+login API 200 |

因此：用户 Live Preview 若鉴权/会话异常、或 sticky/CDN 卡在旧空响应，会看到**与 6014 无鉴权相同的白屏**；  
**不是** LibreChat 在 8080 没起来。

截图（in-container）：`screenshots/preview-8080.png`（绿）· `screenshots/preview-6014.png`（白）· 机器可读 `screenshots/preview-diagnose.json`。

### 对照 Codex 优先级

1. **P0 成立**：6014 层决定能否把 8080 HTML 交给面板；本机 8080 完整可用无法单独证明面板。  
2. **P1**：仅保留一个 `0.0.0.0` HTML 口（8080）；API/mongo 仅 loopback。  
3. **P2**：`PROXY` 禁止设置为 `1`（会弄崩 LibreChat undici）。  
4. **P3**：源 `client/index.html` 注入无 JS 可见「Pico 正在加载…」+ early SW unregister；`scripts/librechat-postbuild-sw.sh` 将 dist `sw.js` 换成 **self-destroying** SW。

### 代理版本（本环境新发现）

- 二进制路径：`/opt/preview-proxy/xai-grok-preview-proxy-0.1.11`  
- **`--version` 不可用**；目录名表明版本约 **0.1.11**（远早于 changelog 0.2.90 / 0.2.96）  
- 行为仍符合：鉴权门 + 空 body 白屏；多服务时需 pin 8080

### 用户侧正确动作

- **不要**外部浏览器硬开 sandbox 域名（常 404/鉴权跳转）  
- 依赖 **Grok 聊天内 Live Preview 面板的鉴权会话**  
- 若面板纯白且 **超过 10 秒看不到「Pico 正在加载…」** → 面板未渲染到 8080 HTML（平台层）  
- 若能看到「正在加载…」但永不变成 Welcome back → 再查 6014 资产 MIME（P2）

### Agent 侧已做（本窗）

- Mongo `:27017` → Pico API `127.0.0.1:18765` → LibreChat `:3080` → public mirror **`:8080`**
- pin `POST /__control/target {"port":8080}` + `scripts/pin-preview-8080.sh` 保活
- `scripts/run-product.sh` / `startup.sh` 复活栈；禁止 `PROXY=1`
- 首屏「Pico 正在加载…」+ self-destroy SW
- 本机 Playwright 验收通过（**不**声称用户 Live Preview 已通）

### 平台侧建议（需 xAI / 新 sandbox）

1. 升级 preview-proxy 至含 **8080 优先 + 强制最新内容** 的版本（changelog 0.2.90 / 0.2.96；当前约 **0.1.11**）  
2. 重建 Live Preview 会话以清 sticky/CDN  
3. 若 6014 Playwright 在已鉴权 cookie 下仍 403/空 body → 报 xAI 平台 bug

## 验收标准

- [x] in-container 8080 Playwright 见 Welcome back  
- [ ] 用户 Live Preview 见 Welcome back（依赖平台鉴权会话 — **本窗未声称达成**）  
- [x] target=8080  
- [x] 6014 无鉴权 = 403 空 body（解释白屏机制）  
- [x] HTML 无 JS 可见「Pico 正在加载…」  
- [x] SW self-destroy 流程（非仅删 register 行）
