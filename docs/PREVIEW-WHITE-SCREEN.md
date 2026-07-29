# Live Preview 白屏诊断结论（Codex 方案落地）

```
DATE: 2026-07-29
STATUS: EVIDENCE LOG
```

## 结论（与 Codex 一致）

**根因在 Grok Live Preview 层，不在 Pico API / Mongo / LibreChat 主流程。**

### 决定性证据

| 路径 | 结果 |
|------|------|
| `GET http://127.0.0.1:8080/login` | **200** + 完整 HTML（Welcome back / Pico） |
| Playwright → `:8080/login` | **可见登录页**（非白、非 JSON） |
| `GET http://127.0.0.1:6014/login`（无 preview-auth cookie） | **302 → grok.com/preview-auth** 或 **403**，**body 长度 0** |
| Playwright → `:6014/login` | **URL 停在 6014，body 空 → 纯白** |
| `agent_target` | 已 pin **8080**；候选含 8080/18765/27017 |

因此：用户 Live Preview 若鉴权/会话异常、或 sticky/CDN 卡在旧空响应，会看到**与 6014 无鉴权相同的白屏**；  
**不是** LibreChat 在 8080 没起来。

### 对照 Codex 优先级

1. **P0 成立**：6014 层决定能否把 8080 HTML 交给面板；本机 8080 完整可用无法单独证明面板。  
2. **P1**：仅保留一个 `0.0.0.0` HTML 口（8080）；API/mongo 仅 loopback。  
3. **P2**：`PROXY` 禁止设置为 `1`（会弄崩 LibreChat undici）。  
4. **P3**：已对 dist 注入「Pico 正在加载…」首屏 + SW unregister + self-destroy `sw.js`。

### 代理版本

- `xai-grok-preview-proxy --version`：**不可用**（无该 flag）  
- 无法在本环境确认是否已含 changelog **v0.2.90 / v0.2.96** 修复  
- 行为仍符合：多候选 + 鉴权门 + 空 body 白屏

### 用户侧正确动作

- **不要**外部浏览器硬开 sandbox 域名（常 404/鉴权跳转）  
- 依赖 **Grok 聊天内 Live Preview 面板的鉴权会话**  
- 若面板纯白且 **超过 10 秒看不到「Pico 正在加载…」** → 面板未渲染到 8080 HTML（平台层）  
- 若能看到「正在加载…」但永不变成 Welcome back → 再查 6014 资产 MIME（P2）

### Agent 侧已做

- pin `POST /__control/target {"port":8080}` + 保活  
- LibreChat only on 8080；API 18765 loopback  
- 首屏可见 fallback + SW 拆除  
- 禁止 `PROXY=1`

### 平台侧建议（需 xAI / 新 sandbox）

1. 升级 preview-proxy 至含 **8080 优先 + 强制最新内容** 的版本（changelog 0.2.90 / 0.2.96）  
2. 重建 Live Preview 会话以清 sticky/CDN  
3. 若 6014 Playwright 在已鉴权 cookie 下仍 403/空 body → 报 xAI 平台 bug

## 验收标准（未因本窗达成用户面板）

- [x] in-container 8080 Playwright 见 Welcome back  
- [ ] 用户 Live Preview 见 Welcome back（依赖平台鉴权会话）  
- [x] target=8080  
- [x] 6014 无鉴权 = 302/403 空 body（解释白屏机制）
