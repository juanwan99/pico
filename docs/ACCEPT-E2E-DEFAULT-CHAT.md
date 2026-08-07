# ACCEPT · T-E2E-DEFAULT-CHAT

```text
RULE: E2E-DEFAULT 任一红 = 整包不得 PASS
      仅 EXCELLENT 晋级小任务
```

## 等级

| EXCELLENT | 公网默认路径达标 + 证据 |
| PASS_WEAK / FAIL | 禁止晋级 |

## 一票否决

- 未跑 E2E-DEFAULT 或 D5 失败
- 默认仍是坏 kimi-*
- 只改用户偏好、清缓存才可用（新用户默认仍坏）
- 仅 API/loopback
- 自签 CLAIM-WB=YES

## 分条

| ID | EXCELLENT |
|----|-----------|
| E0 | 根因写明（日志字段无密钥）+ 与业主截图一致复现 |
| E1 | 新用户/无痕默认模型 ∈ 可用 DeepSeek 或声明集合；配置进仓或 prod 可审计 |
| E2 | 默认路径流式成功；密钥问题已修 |
| E3 | UI 不显示误导性唯一 Kimi 绿标（或与真实模型名一致） |
| E4 | D1–D8 全 PASS · 截图/文字证据 |
| E5 | 默认路径交件非空文件 UI 可下 |
| E6 | 默认路径 42 无假文件 |
| E7 | 故意失败中文 + 可再试 |
| E8 | health pi-agent；交件 NL 纪律不回退 |
| E9 | Issue 证据齐 · 请业主同路径复测模板 |

## 包末

```text
E2E_DEFAULT_CHAT: PASS ⇔ E0–E9 全 EXCELLENT 且 D1–D8 全绿
CLAIM-WB-DEGREE-WEB: NO 直至业主复测书面
```
