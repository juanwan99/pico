# 经验（唯一真源）

```text
仓: juanwan99/pico ONLY
DATE: 2026-08-31
用法: 开窗读本文。禁止把正文贴进卡或对业主聊天。
派发条只点名编号（最多 3 条）。过期删（总管同轮删/并）。
工具: docs/TOOLING-CATALOG.md（本文不抄用法表）。
北极星: docs/DIRECTION-NOW.md §0-star · 用法 = Grok
按域检索: A 派发 · B 产品 · C 部署/ECS/执行者 · D Cloud Agent
```

## A · 派发 / 收口

1. **只改 pico。** 禁写 edu-core / edu-cloud。
2. **1 卡 1 PR。** CI 红、测炸、部翻车，都在**原 PR 原分支**补。禁止为修测/修部/修 Dockerfile/改文档新开第二张 PR（同卡续 = 业主说还差）。
3. **无部署权拒领。** 不能 `PICO_DEPLOY_SHA=… bash /opt/pico/scripts/prod-update.sh` = 不 stamp。DONE 必须 `curl -fsS https://pico.aivia.asia/api/pico/tip` = origin/main。合了未部 = 没完。
4. **禁止 PR 写 `Closes #<卡>`。** 部前关卡 = 失真。合了未部要打回 OPEN。
5. **证据贴本卡 Issue 评论。** 禁止截图 docs PR。UI 卡：执行窗合部后把过门截图贴合同 Issue **回执**（图跟五句一起）。Cloud Agent 本机无浏览器 ≠ 免过门；派发条写明「截图写回执」。
6. **过门是公网结果句。** 主管见 live tip=main 且结果句可见则自签 PASS。业主抽检不对开新卡。写 1px 轨 / 词表 / 选择器 = 退回。禁开工。禁焊提示词/定向场景。
7. **同域一张 `stamp-ok`。** 残债同卡。禁 `T-*-DEBT`。
8. **卡面四行合同。** 已锁事实写 Issue 评论，禁止把手册/315 贴进卡。
9. **聊天默认易失。** 约束下一窗 → Issue 评论或 `STATE-NOW` / 本文 / `TOOLING-CATALOG`。回复用 `§编号` / `Issue#`，禁「上次我们说」。
10. **合与部默认本窗。** 执行者 = 业主正在说话的这扇 Grok 沙箱。不要 spawn 子 agent / Cursor 云 Task / SSH 调 ECS grok。主管做：对齐需求·开卡·合·部·结果可见则自签 PASS。
21. **自循环总线 = 合同 Issue 评论标题。** 只认 `## 派发` / `## CANDIDATE` / `## DEPLOYED` / 五句 `DONE`。禁止 mailbox / 把 ECS 当第二账本 / 聊天当真源。
22. **总管环（自驱动闭环）：** 对齐需求 → stamp → 本窗改+测+PR（叠 live）→ CI 绿立刻 squash 合 → 有差才部（ssh-ecs / prod-update）→ tip-pin → 结果可见则自签 PASS → 刷 STATE-NOW/#634。ECS 只部。合了未部关卡=打回 OPEN。禁止 mailbox。卡别拆太细。禁止拉 Cursor 云 Task 当执行者。
23. **三态：** `OPEN` 有 stamp 在飞 · `WAIT` 等人/审（不开新卡）· `CLEAR` tip=main + 主管 PASS。人只留：目标 · 黄红争议 · PASS。同域第二张 stamp-ok=废派。

## B · 现网 / 产品

11. **用法 = Grok。** 禁问句/材料特判、禁词表监工、禁自研压缩器/记忆 OS。只接 Pi 官方 compact。
12. **CLAIM-WB-DEGREE-WEB 业主 2026-08-26 已签 YES** @ tip `dcb47c00…`（#449/#316 OWNER DECISION）。工程仍禁改口/再代签。记忆 OS 仍挂起；人视角薄层（名+最近文件）#733/#736 已部。
13. **`juanwan99/oneflow` 不当真源**（已 Archive）。
14. **改 Python 工具说明 ≠ Pi 看见。** 真路径：`pico-gateway-tools.ts` + `SYSTEM.md`。
24. **办公文档 = [ADR-OFFICE-DOC-PIPELINE](./ADR-OFFICE-DOC-PIPELINE.md)。** spec/`generate_*` = **稳妥默认**，不是天花板。卡 1 #690 / 卡 2 #694 已收口。禁再加厚 spec 当天花板（「第三张办公卡」指这个）。上限 = 上游 Pi skill + 沙箱库；禁 host bash、禁自研幻灯 OS。
27. **能力笼子已拆（#703 T-UNMASK-PI）。** 聊天图进 Pi RPC `images`；有图走 vision 模型；上传收 png/jpg；PPT 三页硬律退役（只打空壳）；进度词不再写「课件」。控制面仍留：账本·租户·假绿门·不代登·用法=Grok。贴图实测走 `/v1/chat/completions` 真载荷（`content[]` + 旁路 `image_urls`）。相对 `/images/` 不拉（禁 SSRF）。沙箱预览/截图 PNG 已可记入下一轮 chat `images[]`（#707）。贴图/拖图全是图且提供商可贴时直送提供商，不弹 LibreChat 三选。回形钉无 SharePoint 时一点即传，不弹目的地菜单。
25. **HTML 公网页 = 能力。** 公网链 `/p/{id}`（不是 SPA）。`publish_html_page` / 收集口 / `unpublish_html_page`。数据落发布人账本。禁焊场景提示词。#697 已收口。
28. **出图：业主 New API 反代多 Gemini 账户（#752 · 业主 2026-08-28）。** 硅基流动出图已否决，禁止再建议。真源 = New API `PICO_IMAGE_GATEWAY_URL` + `PICO_IMAGE_GATEWAY_KEY`（Pico 不轮询、不直连 Google）。`gemini-*-image` 走网关 `POST …/v1beta/models/{model}:generateContent`（官方 New API 对 `/v1/images/generations` 只映射 imagen）。imagen-* 仍走 `POST …/v1/images/generations`。智谱 glm-image 仅无网关时的退路。禁网页套餐 cookie 反代。禁自研图核。SILICONFLOW 出图路径 fail-closed。**聊天脑同样只打 New API**（`DEEPSEEK_BASE_URL=http://127.0.0.1:3000/v1` · 模型仍 `gpt-5.6-sol` · `api=openai-responses`）。AIProxy 是 New API 的 Custom 渠道上游（`…/openai/responses`，禁止带 `/v1`），不是 Pico 直连。Wei-Shaw/sub2api 只绑 host loopback，作账号登录态；轮询/计费在 New API。禁止把 Sub2API SPA 当老师前端或 cookie 接管 pico.aivia.asia。管理者页 `/admin/gateway`（ADMIN only）面向所有者：薄读 `channel-monitors` 画 7 日/168h 状态盘，软按钮只转发 refresh/test/clear-error/recover-state；硬重登/签合规走独立公网 `https://workbench.aivia.asia`（Sub2API 真页 · 密码 + 谷歌验证器）。禁止挂到 pico.aivia.asia。Pico 不代签合规，不自研账号 OS。机上 `.env` 用 `SUB2API_ADMIN_EMAIL` / `SUB2API_ADMIN_PASSWORD` / `SUB2API_ADMIN_API_KEY`（值不进 git）。业主绑 Google Authenticator 后密码登录返回 `requires_2fa`，Pico 薄读走 `X-API-Key`（不是 Bearer JWT）。Dify 运行面退役；`workbench.aivia.asia` 主机名只给所有者账号台。
29. **Meili hybrid：只认 live embedder。** health `meili_embedder` ≠ 有钥。禁每条 upsert `ensure()` PATCH（会冲垮 task 队列）。清洪水用 `POST /tasks/cancel`（不是 DELETE）。#733/#737。
30. **PPT 图进页 = `image_artifact_id`。** 出图成功 ≠ 进页。`[image:…]` / markdown 写在 body 不会嵌。Pi 真源：`pico-gateway-tools.ts` + SYSTEM。生产 `LedgerArtifactStore.read` 必传 `title=`；`_load_spec_images` 漏传会 TypeError，图在账本、页里 0。单测 MemoryStore 给 default 会漏。缩正文给图必须同时钉 top/height，只改 width 会 height=0 叠标题。#740 业主 PASS 2026-08-29 @ tip `2e668686…` · 不关卡。
31. **加载诚实（#748）。** 办公天花板 `sandbox_pptx_lib` 常驻 CORE。挂 Skill 只要还露 `generate_pptx_document`，就必须成对露 `sandbox_pptx_lib`，否则挂 Skill = 藏天花板。焊句禁回潮（Prefer generate_pptx / Photos still use）。编程沙箱仍 EXTENDED。禁词表自动挂。只改 Python 说明 ≠ Pi 看见（仍认 §14）。
32. **产品尺 ≠ 三问（#748）。** 自验必须拆 pptx：页数、嵌图、同聊改是否落盘。模型打勾 / UI「已完成」不当过。三问只证加载没焊死。办公厚度是 S2，不是再出一张更漂亮的三问。同名再写必须覆盖老师盘；沙箱同名打开必须重载，不能切回旧窗。只查老师盘会漏账本新版本。
33. **办公厚度（#752）。** 缺 `image_artifact_id` 不得毁掉整份 PPT（跳过该图，observation.images 诚实）。成品条在已有 pptx/docx/xlsx 时不挂 sidecar 图。加厚走 `sandbox_pptx_lib` 帮手（`add_title_slide` / `add_content_slide` / `add_table`）+ 现有 slide 字段排封面/表，不加 spec 字段。焊句仍禁。GPT 脑会发 `accentColor` / `fontFace` / `backgroundColor` 和 `type=cover` 多行副标题；投影必须认这些别名，封面不得因要点>1 行退回白底黑字 content 布局。脑已切 GPT ≠ 成品像 GPT——丢 theme 会看起来仍像薄模板。**裸调同一颗 GPT 写 python-pptx（色块/卡片）明显好过 spec 条目墙。** SYSTEM 禁止把「能用的 PPT」定义成 body bullets。spec = 库存版式；自由几何走 `sandbox_pptx_lib`。禁止用 spec 投影当天花板。沙箱拒 `import pathlib`、只认 `save_deck`、source 2 万字、exec 缺 `isinstance` = 裸调稿跑不起来。`prs.save` 一律接到账本路径；pathlib 只许 stub（`mkdir` 忽略，禁读写宿主）；source 上限 8 万；`import os` 仍拒。
34. **聊天脑走 New API，上游才是 AIProxy Responses。** Pico 换 DS 只接 **OpenAI Responses** 这条：Pi `--provider openai` + `baseUrl`=`http://127.0.0.1:3000/v1` + `api=openai-responses` + 模型 `gpt-5.6-sol` + `--thinking medium`。New API Custom 渠道 `aiproxy-openai` 钉死上游 `https://…/openai/responses`（直打 `/openai/v1/responses` = 404）。无 `store:true`。不要用 urllib 默认 UA 探活 AIProxy。DEEPSEEK_* 仍是脑槽位，钥改成 New API 的 `pico-gateway` token，不是 AIProxy 钥。`gpt-*` 贴图不要切回 deepseek vision。**出图仍走同一 New API 的 Gemini 渠道**（`PICO_IMAGE_GATEWAY_*` · `gemini-3.1-flash-image`）。禁止为 Claude/Grok 再造核。长请求：Responses **必须 `stream:true`**（非流式/首包>约 100s → Cloudflare/AIProxy **HTTP 524**，不是 Pico 拒长文）。Pico 聊天 SSE 发 comment keepalive，禁把心跳写进气泡。直连 GPT 禁打 `chat/completions`。GPT 思考不是空转，禁 180s 无工具熔断。上游 `stopReason=error`（如 usage limit）或空 content 不得标 succeeded 空气泡；人话失败，假绿禁止。
35. **沙箱打开 Office = 内容框。** 默认「打开」docx/pptx/xlsx 走 `GET …/content?preview=1`，用 python-docx / python-pptx / openpyxl 投影页面/幻灯片画布（Codex 同形态）。不是 LibreOffice Writer/Impress 整窗。LibreChat `pico.js` 必须转发 `preview=1`（禁只放行 `download`，丢掉会落到「无法展开内容框」）。图与生成网页在结果区铺满（iframe/img）。外网网址仍走隔离 Chromium 截图。禁把 LO 当默认预览。
36. **用量账不做钱。** Pico 只记 `usage_events`（谁/校/kind/后端模型/token 或诚实 unknown）。积分门脸 = 同一本账派生（服务端换算，三位小数）；edu 导出用 Pico 给出的积分数字，禁止再乘。禁在 Pico 建点池/余额。char/4 估数不能给 edu 计费，也不得留在账上（启动 scrub 成 unknown）。档位不得当 `model`。钱/钱包在 edu-core，拉 `GET /v1/internal/usage/export`（`PICO_HOOK_SERVICE_TOKEN`）。老师面：每一轮钉在该条回复末尾（预计→实际），不清理、不互相覆盖；usage 晚到先留预计，禁止「未结算」当结束态，禁止把预计写进 token 列。完成态按 `run_id` 从 `usage_events` 结算；刷新/历史用 `conversation_id` 再钉到该条。事件停 unknown 而 run blob 已有 token 则回填同一本账（禁 char/4）。#824 @ tip `af3e8ad0…`。
37. **聊天回形钉 = 老师唯一上传口。** 图和文档同一回形钉：图本轮进 Pi `images[]`；文档落 `POST /v1/files`，抽出失败也落盘，AI 用 `workspace_read_file` 按文件名读。LibreChat 本地仓不是老师柜。ingest HTTP 失败不得假装已传。「我的文件」是生成物柜，不是第二本地上传口。禁目的地三选 / VectorStore / 转到学校当上传。禁第二套文件 OS。
38. **HTML 交互页断网。** `generate_html_document` 禁 CDN / `import https` / `//cdn` / Three.js / Chart.js；外链引擎与 `window.THREE` 空舞台失败闭合，不剥成空舞台再报成功。校验同样扫 import/src/href/引擎全局。禁放行 jsdelivr。#780 业主 PASS 2026-08-29 @ tip `e9e032b3…`。
39. **学校材料 ≠ 工作区文件。** 勾选的是 edu membership 条目，不是 LibreChat/sandbox 路径。`excerpts_for_conversation` 空/失败要 GET item 正文；表格/Office 走现有 `extract_for_kb` + `persist_edu_file` 进本轮工作区再 inject 文件名。只把 UUID 丢给 `workspace_read_file` = Not Found。存档禁止 native `<select>` 再叠自绘 ▾（与学校材料同一套按钮+一个三角）。#824 业主 PASS 2026-08-31 @ tip `af3e8ad0…`。

## C · 部署 / ECS / 执行者

15. **GIT SHA 不当 Docker build-arg。** 当 ARG 会让每次部重下 torch（#658/#659）。SHA 只进 compose `.env`。
16. **部署真源：** `PICO_DEPLOY_SHA=<40> bash /opt/pico/scripts/prod-update.sh`；证伪用 **tip-pin** + **remote-health**（见 TOOLING-CATALOG）。公网 tip 与 ECS loopback 必须同 SHA。
17. **SSH 进机：只用 Tailscale MagicDNS。** Host 别名 `ecs` / `pico-prod` → `aliyun-hy`，用户 `ops`。禁止拿 Cloud Agent 公网 egress IP 去开安全组 22（IP 漂移 = 假通路）。

80. **执行者 = 业主正在说话的这扇 Grok 沙箱。** 不要再 SSH 调 ECS grok，不要拉 Cursor 云 Task。ECS 只部。跨机传话会丢。
81. **开窗先自检，假红当事故。** 密钥根可以是目录（`/root/.edu-secrets` 或 `$HOME/.edu-secrets`），一钥一文件；私钥文件可以叫 `ecs_ops`。不要用 `[[ -f 目录 ]]` 判断「无钥」——目录不是文件，会假红。无钥才 BLOCKED；钥齐但 ssh 不通才是真红。自检一边 BLOCKED 一边 exit 0 = 撒谎。
82. **不要 sudo bash 写密钥或跑装机脚本。** sudo 会清掉环境变量，看起来像没钥。tailscaled 需要提权就在脚本里对那一条 sudo，整段不要包。
83. **Tailscale 主机名按这台沙箱的 hostname，前面加仓前缀（`pico-…`）。** 禁止设成对面仓的固定名（如 `cursor-edu-core`）——会把另一扇窗踢下线。两窗不要抢同一个 Tailscale 节点。
84. **沙箱没有 Docker。** 改和测在沙箱；部在 ECS（`ssh ecs` 再跑仓内 prod-update）。不要为了「本地起全栈」在沙箱装 Docker。
85. **对齐现网 SHA，不要默认把落后的 origin/main 合进现网。** main 落后 tip 时，PR 叠在 live 那根树上。合入 main 后再部。DONE 认公网 tip = 本卡 SHA（合后 tip 应等于 origin/main）。
86. **抽测走用户能看见的那条路。** Grok 沙箱右侧预览必须是现网反代，禁止 iframe 套一套假站。禁止只打 API 当过门。过门仍是公网看得见结果句；CI 绿 ≠ 过门。
87. **装机一次，自检每次。** 钥落到目录（chmod 700 目录、600 文件）后跑仓内 install / ssh-up；自检发现钥齐但 ssh 死，允许自动再 probe 一次。钥禁止进聊天、Issue、PR。两台机器磁盘不通，不要等总管窗「把钥传过来」。
88. **切窗只复制现行总管卡。** 仓内模板改了不等于 Issue 钉文改了——接窗抄的是钉评。正源链接不要指向落后的 origin/main。
89. **高质量执行清单（开卡后不等人喊开工）：** 自检真绿（含 ssh）→ CLAIM → 改+单测 → PR 叠 live → CI 绿立刻 squash 合 → 有差才部 → 五句回执。合了未部关卡=打回。证据贴本卡 Issue，不进 PR。部前禁 Closes。
90. **右侧不是 iframe 现网。** Grok 只展示沙箱 8080。现网几乎都有 `X-Frame-Options: SAMEORIGIN`，嵌 `pico.aivia.asia` 会白屏。要看见真站：在 8080 反代现网（`scripts/grok-preview-proxy.mjs`）。
91. **反代要改四样，缺一样就不稳：** 请求 Host / Origin / Referer 改成现网；响应删 `X-Frame-Options` 和 CSP；`Location` 从 `https://pico.aivia.asia/...` 改成相对路径；`Set-Cookie` 去掉 Domain，SameSite=Lax。
92. **开发路径不要进反代。** `/__grok`、`/@`、`/src`、`/node_modules`、`/auth/popup` 留给 Vite。其余 `/` 和 `/api` 走现网。不要在 8080 再起一套本地产品 SPA 冒充现网。
93. **自检打预览源，不打公网 URL。** 看标题是不是真站；再 POST 登录过预览。过了才叫右侧稳住。Playwright 也走 `127.0.0.1:8080`。
94. **抽测 = 预览里点老师路径。** 不要只 curl 公网 API。预览源和公网源 cookie 不同；API 200 不等于右侧能开。
95. **8080 断了右侧就黑。** startup 先探活再起。上游挂了返回人话 502，不要空转。

## D · Cloud Agent

18. **环境 Secrets（名 only · 值不进仓）：** `TS_AUTHKEY`（reusable/ephemeral）、`PICO_PROD_SSH_PRIVATE_KEY`；建议 `PICO_PROD_SSH_USER=ops`、`PICO_PROD_SSH_HOST=aliyun-hy`。脚本对错误值 `ps` / 公网 `47.*|139.*|100.*` 会强制改回 ops@aliyun-hy。
19. **Bootstrap：** `scripts/cloud-agent-install.sh`（install）+ `scripts/cloud-agent-start.sh`（每 boot：tailscaled → `tailscale up` → 写 `~/.ssh` → 软测 `ssh ecs`）。Dashboard Environment 的 install/start 可回退到 `~/.local/bin` 同名脚本（snapshot 基座）。
20. **禁止：** 密钥写进 `environment.json` / Issue / PR；把「白名单 22」当 Cloud Agent 部署通道；Save 前不经 draft build + 新 agent 验 `ECS_OK`。

```text
派发点名示例：经验 §3 §17 §22 §80 §90 · 工具 grok-sandbox-exec · grok-preview-proxy · tip-pin · ssh-ecs
```
