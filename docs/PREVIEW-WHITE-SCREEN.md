# Live Preview 白屏诊断结论（Codex 方案落地）

```
DATE: 2026-07-29
STATUS: EVIDENCE LOG + MEMORY
LAST_WINDOW: Grok-Pico写入（LibreChat P0）
BRANCH_BASE: grok/pico-debrand-nextchat @ 429f85f…
CANDIDATE: e9f0703000083c7a4dc9a037ddaede5af2e161f1
```

## 一句话根因（给业主 / 下一窗）

**白屏是因为 Grok Live Preview 代理（:6014）在未鉴权或会话异常时返回 403/空 body；  
不是 LibreChat 没起来，也不是 Pico API 主流程写错。**

产品 UI 在 **:8080** 时本身是好的（Playwright 可见 **Welcome back**）。

---

## 结论（与 Codex 一致）

**根因在 Grok Live Preview 层，不在 Pico API / Mongo / LibreChat 主流程。**

### 决定性证据（复测 2026-07-29）

| 路径 | 结果 |
|------|------|
| `GET http://127.0.0.1:8080/login` | **200** + HTML `title=Pico` + **「Pico 正在加载…」** |
| Playwright → `:8080/login` | **Welcome back** 登录表单；console **0 error** |
| `GET http://127.0.0.1:6014/login`（无 preview-auth） | **403 Forbidden**，**body 长度 0** |
| Playwright → `:6014/login` | body 空 → **纯白** |
| `GET :18765/health` | 200 JSON（API；**不是**产品页） |
| pin `:6015/__control/target` | `{"port":8080}` |

### 误判清单（下次别犯）

| 错误动作 | 为何错 |
|----------|--------|
| 白屏 → 立刻换壳 / 重写前端 | 6014 不吐 HTML 时换任何壳都白 |
| 只 curl 8080 就说「预览好了」 | 用户走的是 6014 鉴权后的面板 |
| 把 API JSON 根路径当产品成功 | 产品是 LibreChat 登录/聊天 HTML |
| 设 `PROXY=1` | 弄崩 LibreChat undici |
| 不 pin 8080 | 代理可能粘到 18765/27017 等非 HTML 口 |

### 代理版本

- 路径：`/opt/preview-proxy/xai-grok-preview-proxy-0.1.11`  
- 无 `--version`；目录名 ≈ **0.1.11**（早于 changelog 0.2.90 / 0.2.96）

### 用户如何登录（演示）

1. 在 **Grok 聊天里的 Live Preview** 打开产品（不要另开外部 sandbox 域名）。  
2. 应看到登录页 **Welcome back**（或先看到「Pico 正在加载…」再变成登录页）。  
3. 使用：

| 字段 | 值 |
|------|-----|
| Email | `teacher@example.com` |
| Password | `pico-demo-123` |

4. 点 Continue / 登录。  
5. 若超过约 10 秒连「Pico 正在加载…」都没有 → 仍是面板未吃到 8080（平台层），不是账号错。

### Agent 侧已做

- pin 8080 + 保活；LibreChat 公网仅 8080；API 18765 loopback  
- 「Pico 正在加载…」无 JS 可见 + SW self-destroy  
- 禁止 `PROXY=1`  
- 证据截图：`screenshots/preview-8080.png` / `preview-6014.png` / `preview-diagnose.json`

### 平台侧建议

1. 升级 preview-proxy（8080 优先 + 强制最新内容）  
2. 重建 Live Preview 会话清 sticky/CDN  
3. 鉴权 cookie 下 6014 仍空 body → 报 xAI 平台 bug

## 验收

- [x] in-container 8080 Playwright 见 Welcome back  
- [ ] 用户 Live Preview 见 Welcome back（依赖平台鉴权会话；业主若已可见则面板会话已通）  
- [x] target=8080  
- [x] 6014 无鉴权 = 403 空 body  
- [x] 根因与误判清单写入 `CORRECTED-GOALS.md` §4.4 / 错误记忆 #15–#18  
