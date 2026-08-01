# Codex 长任务卡 · D1 夜 · ≈6 小时

```
SPRINT: docs/SPRINT-3DAY-PUSH.md
ONEFLOW: docs/ONEFLOW.md
```

## 使命（按序，6h 内尽量全部完成）

1. Git 闭环：M2 续 tip 与 main 合并进 main，生产对齐  
2. S7 最小真闭环：提案→确认/拒绝→审计，UI 同 change id  
3. 测 + 上线 + GitHub 回写  

目标授权 = 同范围 merge 意图 + 阶段 A 部署。阻塞仅红例外。

## HARD

- 仅 juanwan99/pico · 不写 edu · 不自 PASS · 不升 v1.3  
- 禁 PROXY=1 · 禁公网 18765/27017/8080 · 禁打印 key  
- 前端不像素战役；仅 S7 所需最小 UI  
- 生产 /opt/pico · docker-compose.host.yml · https://pico.aivia.asia  
- 演示 teacher@example.com / <redacted-demo-password>

## 必读

docs/SPRINT-3DAY-PUSH.md · docs/ONEFLOW.md · docs/MASTER-PLAN.md · docs/W2-S7-NOTES.md（若有）

## 时间盒

### H0–H1.5 Git 闭环

```bash
git fetch origin
# 工作副本合并 main 与含 b736c6a 的功能提交
# push → PR → main → CI 绿 → merge
# 生产：main tip · rebuild · health.git_sha · ## DEPLOYED
```

冲突：保留 T1–T3 与 OneFlow 文档；禁丢账本修复。

### H1.5–H5 S7 最小闭环

1. Change 提案可产生（接现有，不重造）  
2. API：pending / confirm / reject  
3. UI 横幅同一 change id  
4. 测：confirm、reject、跨 membership  
5. 浏览器一条可见路径  

### H5–H6 固化

pytest / selftest · 生产 rebuild · 冒烟 · CANDIDATE + DEPLOYED · 报告 · 停  

## 结束报告模板

```
## D1 夜 6h 结果
- hours used:
- main SHA:
- branch SHA:
- PR:
- CI:
- merged? Y/N
- health.git_sha:
- S7 API/UI/tests/browser:
- smoke:
- blockers:
- D2 接手点:
```

## 禁止

开新模块/像素/edu；CI 红硬合；只调查不交付。
