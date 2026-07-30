# 接入 Kimi（Moonshot）

```
DOC: docs/KIMI-CONNECT.md
STATUS: HOWTO
```

## 拓扑（固定）

```text
用户 Live Preview
  → LibreChat :8080
    → OPENAI_REVERSE_PROXY → Pico API 127.0.0.1:18765/v1
      → KIMI_API_KEY → https://api.moonshot.cn/v1  （真模型，密钥仅服务端）
```

- **禁止** 把 Kimi 密钥写进 LibreChat / 浏览器。  
- LibreChat 只用开发代理密钥 `pico-dev` 调 Pico；Pico 再用 `KIMI_API_KEY` 调 Moonshot。

## 配置

在仓库根目录 `.env`（**勿提交**）：

```bash
KIMI_API_KEY=sk-你的密钥
# 可选别名：
# MOONSHOT_API_KEY=sk-你的密钥
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.6
```

推荐模型（2026）：`kimi-k2.6` · `kimi-k3` · `kimi-k2.7-code`  
`moonshot-v1-*` 对新账号逐步下线。

密钥申请：<https://platform.moonshot.cn/> 或 <https://platform.kimi.com/>

改完密钥后重启 Pico API：

```bash
# 沙箱内由 agent 重启 uvicorn :18765；用户侧只需刷新 Live Preview
```

## LibreChat

```env
ENDPOINTS=openAI
OPENAI_API_KEY=pico-dev
OPENAI_REVERSE_PROXY=http://127.0.0.1:18765/v1
OPENAI_MODELS=kimi-k2.6,kimi-k3,kimi-k2.7-code,moonshot-v1-8k,pico-agent
```

- `kimi-*` / `moonshot-*` → 真流式直连模型  
- `pico-agent` → 带工具环的 Agent 路径（同样需要 KIMI_API_KEY）

## 验收

1. `GET /v1/models`（Bearer pico-dev）列出 kimi 模型  
2. 流式对话返回 token（非「尚未配置 Kimi 密钥」）  
3. Live Preview 选 `kimi-k2.6` 能正常回复  

无密钥时诚实失败：中文提示配置 `KIMI_API_KEY`，**不得**用 mock 假绿 S1。
