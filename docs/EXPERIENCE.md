# 经验（唯一真源）

```text
仓: juanwan99/pico ONLY
DATE: 2026-08-27
用法: 开窗读本文。禁止把正文贴进卡或对业主聊天。
派发条只点名编号（最多 3 条）。过期删（总管同轮删/并）。
工具: docs/TOOLING-CATALOG.md（本文不抄用法表）。
北极星: docs/DIRECTION-NOW.md §0-star · 用法 = Grok
按域检索: A 派发 · B 产品 · C 部署/ECS · D Cloud Agent
```

## A · 派发 / 收口

1. **只改 pico。** 禁写 edu-core / edu-cloud。
2. **1 卡 1 PR。** CI 红、测炸、部翻车，都在**原 PR 原分支**补。禁止为修测/修部/修 Dockerfile/改文档新开第二张 PR（同卡续 = 业主说还差）。
3. **无部署权拒领。** 不能 `PICO_DEPLOY_SHA=… bash /opt/pico/scripts/prod-update.sh` = 不 stamp。DONE 必须 `curl -fsS https://pico.aivia.asia/api/pico/tip` = origin/main。合了未部 = 没完。
4. **禁止 PR 写 `Closes #<卡>`。** 部前关卡 = 失真。合了未部要打回 OPEN。
5. **证据贴本卡 Issue 评论。** 禁止截图 docs PR。
6. **过门是老师手。** 写 1px 轨 / 词表 / 选择器 = 退回。禁开工。
7. **同域一张 `stamp-ok`。** 残债同卡。禁 `T-*-DEBT`。
8. **卡面四行合同。** 已锁事实写 Issue 评论，禁止把手册/315 贴进卡。
9. **聊天默认易失。** 约束下一窗 → Issue 评论或 `STATE-NOW` / 本文 / `TOOLING-CATALOG`。回复用 `§编号` / `Issue#`，禁「上次我们说」。
10. **合与部只归执行窗。** 总管 / 主管窗 / 本类 Cloud Agent：**不合 main、不跑 prod-update**。总管做：派发·两问戳·黄红审戳·现况三行·经验/工具入库。P0 止血可调查、起候选 PR，**合与部仍交执行窗**（有 stamp 才领）。禁止「总管代合代部」当常态。
21. **自循环总线 = 合同 Issue 评论标题。** 只认 `## 派发` / `## CANDIDATE` / `## DEPLOYED` / 五句 `DONE`。禁止 mailbox / ECS 常驻 Grok / 聊天当真源。
22. **总管环（不合不部）：** stamp → 派发条贴本卡 `## 派发` → **spawn-executor**（官方 `POST /v1/agents`；首条=派发条；`CURSOR_EXECUTOR_ENV` = 单独执行环境，含 TS/SSH）→ 订 PR/CI → timer 读评 → tip-pin → 刷 STATE-NOW/#634 → CLEAR。无钥则合同 PR/Issue 评 `@cursor`。合了未部关卡=打回 OPEN。禁止 mailbox / ECS 常驻。禁止总管代合代部（含「应急改+部」）。
23. **三态：** `OPEN` 有 stamp 在飞 · `WAIT` 等人/审/过门（不开新卡）· `CLEAR` tip=main + 五句后停或下一张。人只留：目标 · 黄红争议 · 老师手 · PASS。同域第二张 stamp-ok=废派。

## B · 现网 / 产品

11. **用法 = Grok。** 禁问句/材料特判、禁词表监工、禁自研压缩器/记忆 OS。只接 Pi 官方 compact。
12. **CLAIM-WB-DEGREE-WEB 业主 2026-08-26 已签 YES** @ tip `dcb47c00…`（#449/#316 OWNER DECISION）。工程仍禁改口/再代签。记忆 OS 仍挂起；人视角薄层（名+最近文件）#733/#736 已部。
13. **`juanwan99/oneflow` 不当真源**（已 Archive）。
14. **改 Python 工具说明 ≠ Pi 看见。** 真路径：`pico-gateway-tools.ts` + `SYSTEM.md`。
24. **办公文档 = [ADR-OFFICE-DOC-PIPELINE](./ADR-OFFICE-DOC-PIPELINE.md)。** spec/`generate_*` = **稳妥默认**，不是天花板。卡 1 #690 / 卡 2 #694 已收口。禁再加厚 spec 当天花板（「第三张办公卡」指这个）。上限 = 上游 Pi skill + 沙箱库；禁 host bash、禁自研幻灯 OS。
27. **能力笼子已拆（#703 T-UNMASK-PI）。** 聊天图进 Pi RPC `images`；有图走 vision 模型；上传收 png/jpg；PPT 三页硬律退役（只打空壳）；进度词不再写「课件」。控制面仍留：账本·租户·假绿门·不代登·用法=Grok。贴图实测走 `/v1/chat/completions` 真载荷（`content[]` + 旁路 `image_urls`）。相对 `/images/` 不拉（禁 SSRF）。沙箱预览/截图 PNG 已可记入下一轮 chat `images[]`（#707）。贴图/拖图全是图且提供商可贴时直送提供商，不弹 LibreChat 三选。回形针无 SharePoint 时一点即传，不弹目的地菜单。
25. **HTML 公网页 = 能力。** 公网链 `/p/{id}`（不是 SPA）。`publish_html_page` / 收集口 / `unpublish_html_page`。数据落发布人账本。禁焊场景提示词。#697 已收口。
28. **出图：智谱 glm-image（#729）。** 硅基流动出图已否决，禁止再建议。真源 = `ZHIPU_API_KEY` + `POST …/paas/v4/images/generations` · model=`glm-image`。禁 GLM-Flash 当出图。禁自研图核。SILICONFLOW 出图路径 fail-closed。
29. **Meili hybrid：只认 live embedder。** health `meili_embedder` ≠ 有钥。禁每条 upsert `ensure()` PATCH（会冲垮 task 队列）。清洪水用 `POST /tasks/cancel`（不是 DELETE）。#733/#737。
30. **PPT 图进页 = `image_artifact_id`。** 出图成功 ≠ 进页。`[image:…]` / markdown 写在 body 不会嵌。Pi 真源：`pico-gateway-tools.ts` + SYSTEM。生产 `LedgerArtifactStore.read` 必传 `title=`；`_load_spec_images` 漏传会 TypeError，图在账本、页里 0。单测 MemoryStore 给 default 会漏。缩正文给图必须同时钉 top/height，只改 width 会 height=0 叠标题。#740。

## C · 部署 / ECS

15. **GIT SHA 不当 Docker build-arg。** 当 ARG 会让每次部重下 torch（#658/#659）。SHA 只进 compose `.env`。
16. **部署真源：** `PICO_DEPLOY_SHA=<40> bash /opt/pico/scripts/prod-update.sh`；证伪用 **tip-pin** + **remote-health**（见 TOOLING-CATALOG）。公网 tip 与 ECS loopback 必须同 SHA。
17. **SSH 进机：只用 Tailscale MagicDNS。** Host 别名 `ecs` / `pico-prod` → `aliyun-hy`，用户 `ops`。禁止拿 Cloud Agent 公网 egress IP 去开安全组 22（IP 漂移 = 假通路）。

## D · Cloud Agent

18. **环境 Secrets（名 only · 值不进仓）：** `TS_AUTHKEY`（reusable/ephemeral）、`PICO_PROD_SSH_PRIVATE_KEY`；建议 `PICO_PROD_SSH_USER=ops`、`PICO_PROD_SSH_HOST=aliyun-hy`。脚本对错误值 `ps` / 公网 `47.*|139.*|100.*` 会强制改回 ops@aliyun-hy。
19. **Bootstrap：** `scripts/cloud-agent-install.sh`（install）+ `scripts/cloud-agent-start.sh`（每 boot：tailscaled → `tailscale up` → 写 `~/.ssh` → 软测 `ssh ecs`）。Dashboard Environment 的 install/start 可回退到 `~/.local/bin` 同名脚本（snapshot 基座）。
20. **禁止：** 密钥写进 `environment.json` / Issue / PR；把「白名单 22」当 Cloud Agent 部署通道；Save 前不经 draft build + 新 agent 验 `ECS_OK`。

```text
派发点名示例：经验 §3 §17 §22 · 工具 spawn-executor · tip-pin · ssh-ecs
```
