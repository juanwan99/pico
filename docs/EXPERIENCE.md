# 经验（唯一真源）

```text
仓: juanwan99/pico ONLY
DATE: 2026-08-25
用法: 开窗读本文。禁止把正文贴进卡或对业主聊天。
派发条只点名编号（最多 3 条）。过期删。
工具: docs/TOOLING-CATALOG.md（本文不抄）。
北极星: docs/DIRECTION-NOW.md §0-star · 用法 = Grok
```

## 派发 / 收口

1. **只改 pico。** 禁写 edu-core / edu-cloud。
2. **1 卡 1 PR。** CI 红、测炸、部翻车，都在**原 PR 原分支**补。禁止为修测/修部/修 Dockerfile/改文档新开第二张 PR。同卡续 = 业主说还差。
3. **无部署权拒领。** 不能 `PICO_DEPLOY_SHA=… bash /opt/pico/scripts/prod-update.sh` = 不 stamp。DONE 必须 `curl -fsS https://pico.aivia.asia/api/pico/tip` = origin/main。合了未部 = 没完。
4. **禁止 PR 写 `Closes #<卡>`。** 部前关卡 = 失真。合了未部要打回 OPEN。
5. **证据贴本卡 Issue 评论。** 禁止截图 docs PR。
6. **过门是老师手。** 写 1px 轨 / 词表 / 选择器 = 退回。禁开工。
7. **同域一张 `stamp-ok`。** 残债同卡。禁 `T-*-DEBT`。
8. **卡面四行合同。** 已锁事实写 Issue 评论，禁止把手册/315 贴进卡。

## 现网 / 产品

9. **GIT SHA 不当 Docker build-arg。** 当 ARG 会让每次部重下 torch（#658/#659）。SHA 只进 compose `.env`。改 Python 工具说明 ≠ Pi 看见；真路径是 `pico-gateway-tools.ts` + SYSTEM.md。
10. **用法 = Grok。** 禁问句/材料特判、禁词表监工、禁自研压缩器/记忆 OS。只接 Pi 官方 compact。
11. **CLAIM-WB-DEGREE-WEB 仍 NO。** 不代签 PASS。
12. **`juanwan99/oneflow` 不当真源**（已 Archive）。
