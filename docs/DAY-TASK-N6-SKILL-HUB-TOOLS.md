# 日间任务 · N6 能力中心展示技能工具绑定（只读）

```
TYPE: DAY
STATUS: OPEN
RISK: 黄 · FAST 可代合
context_reset: false
```

## 目标

在 **能力中心 / Skills UI**（已有入口）为每个受控 skill **只读展示** Pico `skill_policy` 绑定的工具列表与 risk（chat-only / read / write_s7）。

- 数据与 `services/orchestrator/pico_orchestrator/skill_policy.py` 一致（可 API 暴露只读快照或构建期生成 JSON，二选一）
- 未知 skill 不展示为「全工具」
- 不新增第二套 skill 目录；不改全局白名单
- 中文标签；桌面可用即可

## 非目标

M5、像素、用户自定义 skill 编辑器、扩工具。

## 验收

1. 打开能力中心：skill.summarize 等可见工具名  
2. skill.chat 显示无工具/纯对话  
3. skill.write_s7 显示 propose 类工具 + 需确认提示  
4. 回归：真聊/运行一次不坏  

## 实现提示

- 可加 `GET /v1/skills` 或 `/v1/skills/catalog`（ai:read），返回 id/name/tools/risk/requires_s7  
- LibreChat 能力中心拉取并渲染  
- 单测：catalog 与 policy 交集一致  
