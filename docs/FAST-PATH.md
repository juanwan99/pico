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
