# 夜卡 N1 · Workbench 主路径 P0 · ≈6 小时

```
CARD: docs/NIGHT-CARD-N1-W-MAINPATH.md
PLAN: docs/PARALLEL-SPRINT-PLAN.md BINDING-v2
TRACK: W
DEPLOY: YES（夜末允许）
DATE: 2026-07-30 夜
```

## 给 Codex：整段执行（连续约 6h）

```text
# Codex 夜卡 N1 · 6h · W 主路径 P0 · 允许部署

## 依据
- docs/PARALLEL-SPRINT-PLAN.md（BINDING-v2）
- docs/NIGHT-CARD-N1-W-MAINPATH.md
- docs/ONEFLOW.md
- 业主：跳过计划二审；今晚跑 N1；非 Skill 夜（N2）

## 使命（做完即停）
主路径 6 步全 Y：
1 首页发起任务
2 执行中状态
3 右栏产物/预览
4 S7 待确认横幅
5 文件打开、下载、历史
6 项目内发起任务并见资产
并清除主路径范围内的：刷新闪黑、假按钮、404、白屏。
产出/更新：docs/WORKBUDDY-SCREEN-MATRIX.md 主路径行 + 截图路径。
main=prod + ## DEPLOYED。

## HARD
- 仅 juanwan99/pico · 禁止写 edu-cloud
- 禁 PROXY=1 · 禁公网 18765/27017/8080 · 禁打印 key
- 不自 PASS 产品终局 · 不升 v1.3
- 一夜只做 Track W；不做 Skill 大改、不做 M5、不做全面像素
- OneFlow：CANDIDATE → CI 绿 → 合 main → 生产对齐 → DEPLOYED
- 生产 /opt/pico · https://pico.aivia.asia
- 演示 teacher@example.com / pico-demo-123
- LEASES：见下；勿改 Skill 核 / edu_adapter

## LEASES（本卡）
可写：
- apps/librechat/client/** 主路径相关（Workbench、Chat 布局/闪黑、ResultPanel 行为若断）
- docs/WORKBUDDY-SCREEN-MATRIX.md、docs/WORKBUDDY-INTERACTION-MATRIX.md（可新建）
- docs/PIXEL-DIFF.md 仅主路径行
- screenshots/** 或 output/playwright/**
慎写/串行：ChangeConfirmBanner 仅修显示回归；data-provider/pico/api.ts 除非主路径必需
禁止：CapabilityHub 大改成 Skill 商店、services/orchestrator Skill 注入、edu_*

## 时间盒
### H0–H0.5 对齐
```bash
git fetch origin
git checkout main && git pull --ff-only
git checkout -B grok/pico-w-mainpath origin/main
git rev-parse HEAD
```
PR 描述写：LEASES=W per NIGHT-CARD-N1

### H0.5–H1 点通表
手点或 Playwright 记 6 步断点；列「闪黑/假按钮/404」清单。

### H1–H4 修复
按清单修主路径；保持 API 行为；最小 diff。
已知方向：刷新闪黑、任务态、右栏、S7 横幅可见、下载打开、项目工作台任务。

### H4–H5 矩阵 + 截图
新建或更新 SCREEN-MATRIX：主路径每步一行（1280 + 390）；缺参考标 NO_REF。
截图写入 screenshots/ 或 output/；矩阵里填路径。

### H5–H5.5 PR + CI
```bash
# 测：能跑则
# pytest 相关；librechat 构建若你改了 client
push · PR → main · CANDIDATE + 40字 SHA
CI 绿后合 main
```

### H5.5–H6 生产 + 冒烟
```bash
cd /opt/pico && git fetch && git checkout main && git pull --ff-only
# 改了 librechat → rebuild librechat；仅文档可不 rebuild
# health.git_sha == main
```
浏览器 6 步全 Y；SELFTEST 能跑则跑；ports 抽查；## DEPLOYED

## 强制验收
- [ ] 主路径 1–6 全 Y
- [ ] 无主路径假按钮/404/闪黑（已知项）
- [ ] 矩阵主路径行存在
- [ ] main SHA == health.git_sha
- [ ] 未写 edu · 未做 Skill 体系 · 未宣称像素 100%

## 停止条件
- 6 步全 Y 且已 DEPLOYED → 停
- 或 6h 满：必须 push + CANDIDATE + 精确接手点（勿半套无测上生产）

## 结束报告（必须贴出）
```
## N1 夜 6h 结果
- hours used:
- base main SHA:
- after main SHA:
- PR:
- CI / merged:
- LEASES respected: Y/N
- 主路径 1–6:
- 闪黑/假按钮/404:
- matrix path:
- screenshots:
- production health.git_sha:
- smoke / selftest:
- rebuild: api? librechat?
- blockers / 接手:
- 声明: 未写 edu · 未 Skill 大改 · 未自 PASS 终局
```

立即开始，连续执行。
```

## 业主今晚 checklist

1. 约开跑前把上面 fenced 块全文给 Codex  
2. 不要同时开 N2/S 轨写代码  
3. 结束看报告 10 行；丢给总管深审  
4. Skill ADR 调查留给 N0 尾或 N2 日前间，**不堵 N1**
