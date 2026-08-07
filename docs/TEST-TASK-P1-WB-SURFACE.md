# 测试任务 · T-P1-WB-SURFACE

```
TYPE: TEST
PAIR: T-P1-WB-SURFACE · docs/DAY-TASK-P1-WB-SURFACE.md
EXEC: SOLO 执行窗内点验
MODE: 开放域 + 真 UI；禁 aivia 固定卷冒充
```

## 前置

- [ ] ## DEPLOYED 且 `default_runtime=pi-agent`
- [ ] 已登录公网工作台

## 用例

| ID | 步骤 | PASS |
|----|------|------|
| P1-T1 | health.git_sha = DEPLOYED tip | 对齐 |
| P1-T2 | default_runtime=pi-agent · scope=all | 不回退 Kimi |
| P1-T3 | 登录工作台 | 进壳 |
| P1-T4 | **交件题**（当场拟）：如「生成一页可下载的年级会一页纸议程（md/docx 任一）」 | 非空成功 |
| P1-T5 | Artifact 区可见；下载或打开成功 | 真文件 |
| P1-T6 | 短答题不硬塞假文件 | 诚实 |
| P1-T7 | 前台 **≥3** Skill/能力入口可见（截图或列表） | ≥3 |
| P1-T8 | 点选其中 1 个后派活；run/请求含 skill 绑定或等价 | 非假按钮 |
| P1-T9 | **同会话**第二轮：「把议程改成 10 分钟版 / 更短」 | 有改动痕迹 |
| P1-T10 | 过程或时间线可见（step/tool/状态） | 至少一类 |
| P1-T11 | 停止仍可用（回归） | OK/N/A |
| P1-T12 | 18765/27017 不公网裸露 | 关 |

## 报告（贴载体 Issue）

```text
## TEST REPORT
PAIR: T-P1-WB-SURFACE
MODE: SOLO
SHA:
日期:

| ID | 结果 | 备注 |
|----|------|------|
| P1-T1 | | |
| P1-T2 | | |
| P1-T3 | | |
| P1-T4 | | 题干摘要： |
| P1-T5 | | 文件名/大小： |
| P1-T6 | | |
| P1-T7 | | 列出 3 个名字： |
| P1-T8 | | skill= |
| P1-T9 | | |
| P1-T10 | | |
| P1-T11 | | |
| P1-T12 | | |

三行:
SHA: …
artifact: OK/FAIL
skills: n= / chat-revise: OK/FAIL
stop: OK/FAIL/N/A

verdict: PASS / FAIL
CLAIM-WB-DEGREE-WEB: NO
```
