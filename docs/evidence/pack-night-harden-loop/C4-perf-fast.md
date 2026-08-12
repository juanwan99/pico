# C4 快速档真跑（并列，不覆盖 C1 烟测）

| 项 | 值 |
|----|----|
| 时间 | 2026-08-13 ~07:18 Asia/Shanghai |
| 路径 | ECS loopback `127.0.0.1:18765/v1/chat/completions` |
| model | `pico-fast` |
| membership | `harden-continue-503` |
| wall_s | **2.408** |
| run_id / id | `chatcmpl-17401fe5d8d44efb94c9fdd2` |
| tip PRODUCT | `f4dcbfcb5f2fbbe178c94d60fed8884f8abc02a6` |
| 提示 | 用一句话说明牛顿第二定律 F=ma 的含义。只回一句。 |

说明：与 #499 / C1 烟测分行并列；**不编造 % 提升**。key 取自运行中容器 env（`.env` 文件曾 401，以容器为准）。
