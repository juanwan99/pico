# 速度阻碍清理（VELOCITY-CLEAN）

```
DOC: docs/VELOCITY-CLEAN.md
STATUS: BINDING for process hygiene
TRUTH: docs/TRUTH-FREEZE.md · docs/WHAT-IS-PICO.md · docs/STATE-NOW.md
DATE: 2026-08-01
```

## 0. 业主命题

1. **目标从来只有开源 Kimi Agent**；`run_agent_loop` 不是目标、不是长期选型。  
2. **阻碍速度的东西要深度清理**（假叙事、假流程、假完成、部署断环）。

## 1. 什么在拖速度（根因）

| 类 | 说明 | 是否开源问题 |
|----|------|----------------|
| 认知污染 | 把实现债讲成「长期自研目标」；假「已接入」 | 否 · 人/文档 |
| 合同缝 | 壳模型 vs API allowlist | 集成 |
| 诚实控制面 | cancel/zombie | 产品工程 |
| **部署断环** | 合 main 但 pico-prod 不可达 → 用户零收益 | **当前最大** |
| 流程税 | 自动队列、过期 PLAN issue、多层控制器文 | 自造 |
| 假完成返工 | 名实不清导致正本清源占带宽 | 自造 |

## 2. 已砍 / 正在砍

| 项 | 动作 |
|----|------|
| run_agent_loop = 目标 | **禁止**；TRUTH/WHAT-IS/STATE 消毒 |
| Plan B harness #121 | 已拒合 |
| EXECUTION-QUEUE 自动派工 | SUPERSEDED |
| 过期 #1 PLAN / #21 POLISH / #28 PREVIEW | 关闭 SUPERSEDED |
| 「合 main 就算进度」 | STATE-NOW：无 DEPLOYED 不算用户侧前进 |
| 用 KA-3 辩论挡日用部署 | 禁止 |

## 3. 刻意保留（不是阻碍，是防返工）

- GitHub 证据闭环（CANDIDATE / CI / TEST REPORT）  
- 写入窗不自 PASS  
- 只写 pico；禁密钥；禁 edu-cloud  
- 换核须授权  

砍这些会更快假上线，然后更慢。

## 4. 速度主链（唯一默认）

```text
修用户可见断点 → 合 main → **部署成功** → 烟测 PASS → 再谈下一刀
```

编排归位并行可以，但 **不得**占用「部署通道未通」时的全部注意力去写新叙事文档。

## 5. 总管自检

- [ ] 本回合有没有把债说成目标？  
- [ ] 本回合有没有在部署断环时只加文档？  
- [ ] 打开的 issue 是否仍对应用户成功路径？

## 6. 当前物理断点（2026-08-01）

| 断点 | 证据 | 动作 |
|------|------|------|
| SSH 别名 `pico-prod` 未配置 | 执行窗 `Could not resolve hostname pico-prod` | 业主/运维在 **跳板机** 配 `~/.ssh/config`（见 DEPLOY-TWO-HOST §0） |
| 公网产品可达性 | 总管沙箱探测曾见 **502** / 连接失败 | **先恢复 nginx+compose 健康**，再 exact-SHA 升 tip |
| #152/#153 已合 main | 用户侧未吃到 | 通道通后 `prod-update.sh` + #142 重跑 |

**顺序硬约束：** 通道自检 → 恢复服务（若 502）→ 部署 tip → 烟测。  
禁止在通道断时开新「叙事/控制器」长 PR 当进度。

