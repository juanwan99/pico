# 测试任务 · 轨 A/B 工作区工具与技能（当前优先）

```
TYPE: TEST
STATUS: OPEN
AGAINST: main 含 #60+#59（目标 SHA 以生产 health 为准，期望 d0bd3fb 或更新 tip）
EXEC: 测试窗（独立 · 非写入自嗨）
ENV: 优先 production via jump；演示 teacher@example.com
```

## 背景

写入已合：workspace 工具 + skill 绑定。  
生产曾 rebuild 对齐 SHA，但 **live Agent** 可能因 Moonshot tool schema（`anyOf`）失败。  
测试窗必须 **实测** 并写 `## TEST REPORT`，不得只看 PR 描述。

## 用例

| ID | 步骤 | PASS 标准 |
|----|------|-----------|
| T1 | 登录公网 /login | 进入工作台 |
| T2 | 直调或 UI：能完成一次「写产物」 | 右栏/文件可见；可打开或下载 |
| T3 | `structured_outline` 或 summarize 技能 | 有结构结果或产物，无 5xx |
| T4 | 选 skill-summarize / lesson 等 **真聊多步** | **无** Moonshot schema 400；有工具调用或诚实降级说明 |
| T5 | S7 propose→确认/拒绝 | 状态正确 |
| T6 | 端口抽检 | 8080/18765/27017 公网不可达 |
| T7 | health.git_sha | 记录完整 SHA |

T4 FAIL 时：记录完整错误文案 → 总管派 **schema 热修** 写入任务 → 复测。

## 给测试窗（复制）

```text
角色：Pico 测试窗（只验收，不大改代码）。
读：docs/TEST-WINDOW.md · docs/TEST-TASK-AB-WORKSPACE.md
环境：跳板进生产或公网 UI + 生产 health。
执行 T1–T7，在 PR #60 或新 Issue 贴 ## TEST REPORT（模板见 TEST-WINDOW.md）。
T4 若 schema 400：判 FAIL，附响应片段（无 key）。
禁止：假 DEPLOYED；写 edu-cloud；只报 CI 绿。
```

## 总管收口

- TEST PASS + SHA 对齐 → 允许 ## DEPLOYED 或总管确认已部署可用  
- TEST FAIL → 写入修 · 再测  
