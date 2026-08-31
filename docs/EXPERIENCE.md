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

PLACEHOLDER_DO_NOT_USE
