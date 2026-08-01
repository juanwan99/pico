# 快路径（加快进度 · 禁止自建重体系）

```
DOC: docs/FAST-PATH.md
STATUS: BINDING default for day-to-day ship
DATE: 2026-08-01
NOT: multi-window OS · auto E1 queue · 长文总管仪式
```

## 一句话

**改 → 合 → 装 → 点两下 → 三行报告。** 同一会话做完。不要拆 4 张验证卡。

## 默认五步（开发/部署同一条线）

```bash
# 0) 生产 /opt/pico 与 .git 须属部署用户（非 root），否则 fetch 失败（#175）
# 1–2) 小 PR，CI 绿，合 main（总管或有合权的人）

# 3) 生产（ssh 进 /opt/pico 或跳板后）
git fetch origin main
TIP=$(git rev-parse origin/main)
PICO_DEPLOY_SHA=$TIP bash scripts/prod-update.sh

# 4) 同人立刻自测（不要另派无 ssh 的窗）
# 跳板上：
bash scripts/remote-health.sh          # 或: bash scripts/remote-health.sh aliyun
# 浏览器：login → 聊一句 → 停一下

# 5) Issue 三行（可贴在任意相关 issue，禁止空喊「做完了」）
# SHA: <health.git_sha>
# chat: OK/FAIL
# stop: OK/FAIL
```


## 窗口约定（业主 2026-08-01 钉死）

| 窗口 | 职责 |
|------|------|
| **窗口 1** | **部署窗**（ssh 生产、`prod-update`、remote-health） |
| **窗口 2** | 写入（代码/文档 PR） |
| **窗口 3** | 写入/调查（可并行另一写入或 DIAG） |
| **窗口 4** | **独立验证窗**：已登录账号 + **视觉** + 可操控网页点测（login/chat/stop）；**不是**窗口 1 |

派工时 `window:` 必须写 1|2|3|4，禁止用含糊的「验证窗/部署窗」替代编号（可同时写编号+职责）。
窗口 4 有账号与视觉时，生产 chat/stop 烟测默认派 **窗口 4**，不要派给窗口 1（窗口 1 往往无浏览器登录态）。

## 硬禁（会变慢的）

- 为同一功能连开「部署卡 + 烟测卡 + 视觉卡 + 文档卡」当默认  
- 无 ssh 的窗去验生产 loopback（必 BLOCKED）  
- 再造自动派工 / RACI / 控制器第二真源  
- 没授权就开 KA flag 或写「已接入」  
- 用新长文代替部署和点测  

## 仍要保留（防假完成，不是体系）

- CI 绿再合  
- exact SHA 部署（`prod-update.sh`）  
- 聊/停各点一次  
- 密钥不进 GitHub  

## 大变更才加码

黄/红、换核（KA-3）、清生产 DB：另说，**不**套进日常五步。

## 与旧文档

- 详细运维：`DEPLOY-TWO-HOST.md`  
- 目标冻结：`TRUTH-FREEZE.md`  
- 快照：`STATE-NOW.md`  
- 日常默认以 **本页** 为准，冲突时目标类仍听 TRUTH-FREEZE。
