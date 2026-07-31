# 热修 · N2 UI 运行一次 proxy 路由

```
TYPE: HOTFIX
PRIOR: #64 TEST REPORT FAIL
RISK: 黄 · FAST 代合
```

## 根因（验证窗）
前端 `POST /api/pico/v1/automations/{id}/run`；Pico API 有 `/v1/automations/{id}/run`；
`apps/librechat/api/server/routes/pico.js` **缺**对应 POST 代理 → 404 → UI「任务不存在」。

## 【给：②】
```text
补齐 pico.js：POST /v1/automations/:id/run → 转发 Pico API。
单测或最小路由测试若仓库已有模式则补。
PR → CI → FAST 代合 → 部署 librechat（必）→ ## DEPLOYED。
同 PR 或紧随部署 #70（N3）若生产未到 1a0bd67。
```

## 【给：③】
```text
部署后：公网 UI 点「运行一次」须产生 Task/Run；再跑 N3 拼错 skill 用例。
## TEST REPORT 贴热修 PR 与 #70。
```
