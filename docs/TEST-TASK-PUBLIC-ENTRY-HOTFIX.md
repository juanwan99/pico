# 测试 · T-PUBLIC-ENTRY-HOTFIX

```
MODE: 公网浏览器优先 · 禁仅 loopback PASS
```

| ID | 步骤 | PASS |
|----|------|------|
| E1 | 浏览器打开 https://pico.aivia.asia/login | 非 TLS 失败/非卡死 |
| E2 | 登录（演示账号） | 进入工作台 |
| E3 | 输入短句（如 你好）发送 | 有模型回复 |
| E4 | 失败时 | 中文人话（若失败） |
| E5 | 登录后 /api/pico/health 或等价 tip | 有 git_sha 可记 |
| E6 | 不要求六条全过 | 本卡只入口+短聊 |

```text
## TEST REPORT
PAIR: T-PUBLIC-ENTRY-HOTFIX
网络: 业主侧 / 执行侧
E1..E6:
verdict: PASS|FAIL
CLAIM-WB-DEGREE-WEB: NO
```
