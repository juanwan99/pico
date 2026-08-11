# CLAIM-WB 路径（诚实 · 禁止代签）

```text
DOC: docs/CLAIM-WB-PATH.md
STATUS: BINDING 纪律
DATE: 2026-08-11
Issue: #445 Phase E
CLAIM-WB: NO · 本文不签 YES
```

## 谁能签

| 角色 | CLAIM-WB |
|------|----------|
| **仅业主** | 可签 YES / 拒绝 |
| 总管 / 写入 / 审查 / 测试窗 | **禁止** 代签 YES |

## 当前公网 tip（写文时须实查）

开工以 `GET https://pico.aivia.asia/api/pico/tip` 为准，禁止死抄。

## 仍欠项（示例清单 · 随回执更新）

- 视觉门 / 产品六条终签未宣称  
- #438 Y1 补帧是否齐（见证据目录）  
- 抗重启 B1 是否已部署并人测  
- 历史账本旧英文失败行是否已由 UI 映射遮住  

## 禁止句

```text
禁止: 工程 CI 绿 ⇒ CLAIM-WB YES
禁止: 账本 succeeded ⇒ 产品 Ready
禁止: 代理人写 CLAIM-WB: YES
```

## 允许句

```text
PACKAGE READY · <卡名>（工程）· CLAIM-WB: NO
请求业主审 CLAIM-WB 材料 · 材料含 tip + 帧 + 诚实欠项
```
