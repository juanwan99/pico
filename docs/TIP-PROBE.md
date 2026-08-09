# TIP 探针 · 交付卡可观测 tip

```text
STATUS: BINDING 运维约定
CLAIM-WB: NO
PARENT: T-CAP-DELIVERY-FOUNDATION · G4
```

## 约定路径（完整 40 位 git_sha）

| 通道 | 命令 / URL | 说明 |
|------|------------|------|
| **公网 tip（推荐）** | `curl -sS https://pico.aivia.asia/api/pico/tip` | 仅 `{ok, git_sha, service}`，**无需登录** |
| **内网 SSH（权威）** | `bash scripts/remote-health.sh [pico-prod]` | 生产 loopback `127.0.0.1:18765/health` |
| 登录后健康 | `GET /api/pico/health`（需 JWT） | 含 runtime/canary 摘要；勿当公网匿名口 |
| SPA `/health` | 返回纯文本 `OK` | **不是** tip；勿当 git_sha 源 |

## 回执模板（复制到执行卡）

```text
main tip: <40-char SHA from git rev-parse origin/main>
SOURCE_SHA: <deploy SHA>
live tip (public /api/pico/tip): <git_sha>
live tip (remote-health.sh): <git_sha>
三行是否对齐: 是|否
```

## 一票否决

- 仅 SPA `/health` 的 `OK` 写成 tip 对齐  
- 假 tip / 短 SHA / `unknown`  
- 把 canary membership 列表贴进 Issue  
