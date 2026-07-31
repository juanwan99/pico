# 日间 · 轨 B · 技能真绑定

```
TYPE: DAY
TRACK: B
PLAN: docs/STANDALONE-AI-24H.md
LEASES: skill_policy.py · apps/librechat/skill/** · CapabilityHub DEMO_SKILLS · skill smoke/selftest
FORBID: 改 tools_builtin 注册（等 A）；M5；第二目录
```

## 给 Codex-B

```text
git fetch && pull main
读 STANDALONE-AI-24H §0/D3 与本文。
将 ≥5 个 skill 的 tools 绑到真实工具名（与 A 对齐；A 未合时先按约定命名，A 合后 rebase）。
chat-only 技能保持 tools=[] 并在文案标明。
write 类继续 requires_s7 + pico_propose_change。
更新 SKILL.md、Hub 列表、smoke 全 id。
PR → CANDIDATE → 等总管。
声明：ADR A · 无 displayTitle。
```

## 验收

- [ ] ≥5 skills 非空 tools 或明确 chat-only 标注
- [ ] smoke 全绿
