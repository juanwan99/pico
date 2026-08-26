# 卡头模板 · 视觉门 + 工具合同

```text
STATUS: BINDING 抄录块 · UI/交付/Agent 卡强制（#386 D4A · #387 T3）
CLAIM-WB: NO
```

复制到执行卡 / Issue 正文（可整段粘贴）：

---

```text
【视觉门 · BINDING #384】
- 公网浏览器 · 像人点完
- 帧：V0 题面 · V1 过程主气泡 · V2 终态 · V3 产物打开
- 主气泡禁工具/机审独白（generate_* / artifact_id / min_required / 源码墙 → FAIL）
- 无图 = 不得请求 Ready
- 审查必须读图；只读表 = 审查无效

【工具合同 · docs/TOOLING-CATALOG.md】
批准 id：
  visual-gate · tip-pin · remote-health · gh-git
  ssh-ecs · cloud-agent-ts · prod-update
  playwright-mcp · chrome-devtools-mcp · pytest-ruff
证据路径：docs/evidence/<card>/<scene>/V0–V3
回执必贴：bash scripts/tool-status.sh --json（无 secret）
missing 非空 或 blocked_for_visual_gate=true → BLOCKED，禁止场景视觉过/Ready

禁止：
  Cool / Keel / mailbox / relay / self-drive / 常驻总控
  第二 E2E 栈 · Browser Use/Stagehand 当 Ready · Percy 替主气泡
  闭源 Computer Use 当验收真源 · 无图 Ready · 只读表审查
  Cloud Agent 公网 22 / egress 白名单当部署通道（用 ssh-ecs）

CLAIM-WB: NO · 产品 Ready：默认未过（直至 #384 帧齐且审查读图）
```

---

## 回执最小段（执行结束贴卡）

```text
## tool-status（无密）
```
（粘贴 `bash scripts/tool-status.sh --json` 输出）

```text
## 视觉证据
| 场景 | V0 | V1 | V2 | V3 | 主气泡洁净 | 状态诚实 |
|------|----|----|----|----|------------|----------|
| … | path | path | path | path | Y/N | Y/N |
```
