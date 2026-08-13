# SANDBOX-S2 · 强于 S1 的隔离 + 人在环 B2 真浏览器

```
DOC: docs/SANDBOX-S2.md
STATUS: BINDING · T-SANDBOX-B2-REAL-BROWSER (#522) · 继承 #516 sidecar · B2 = sidecar Chromium
REPO: juanwan99/pico ONLY
CLAIM-WB: NO
EXTENDS: docs/SANDBOX-S1.md（S1 仍有效：工作区 + 同页 inspect/光栅）
NOT: cloud PC · E2B-as-only-done · B3 代登 · host Chrome on 8080/18088
     自研微 VM 内核 · 一校一机 · privileged Docker · 宿主机 bash 逃逸
     httpx 抓 HTML 再 S2 光栅冒充 B2 画面
```

> **S2 相对 S1：**  
> 1. **自己的页**（S1 保留）：`sandbox_preview_inspect` 仍回 title / h1 / `seen=true`，并对本次 Run HTML 产出真 PNG 光栅。  
> 2. **强于应用层 S1 的隔离：** 浏览器/出网执行面是独立 sidecar 进程 `pico-sandbox`（compose 服务），不是 pico-api、也不是 LibreChat。容器：非特权、`cap_drop: ALL`、`no-new-privileges`、非 root、独立 pid/user/net ns（gVisor 等价档；**不是**自研微 VM 内核）。  
> 3. **B2 人在环 = sidecar 内真 Chromium：** 老师看见的像素来自 Playwright/Chromium **viewport 截图**（或等价直播），不是 `_screen_html` / `pico-b2-banner` 合成页。点击/输入作用于 DOM。微信/教务**不是**过关条件；站点禁自动化则人话失败。禁止 B3 聊天贴密码代登。会话 Cookie 只在 sidecar 内存/tmpfs profile，随 destroy/TTL 死，不写宿主机家目录。  
> 真核仍是上游 Pi harness。本档只做接线、白名单、账本、门闩、人包、门脸。上游浏览器 = Playwright Chromium；升级浏览器只改 sidecar 镜像。

与 [#505](https://github.com/juanwan99/pico/issues/505) 规划对齐；计量仍走 [#506](https://github.com/juanwan99/pico/issues/506) `kind=sandbox`。**不改** [#507](https://github.com/juanwan99/pico/issues/507) `web_search` / `web_fetch` 主路。

E2B / Firecracker / 租用微 VM 都是**可选上游**，不是唯一完成路径。无供应商账号时，本仓 **sidecar 自带 Chromium**（Docker 用户/网络命名空间 + `web_guard` 出网过滤）。

---

## 1. 隔离键（同 S1）

```text
isolation_key = school_id + membership_id + run_id
```

工作区目录、`safe_segment`、耐久产物按账号过滤：跨账号读仍 **404 / `artifact.not_found`**。  
B2 会话同键：跨账号 `GET /v1/sandbox/sessions/{id}/view` → **404 / `sandbox.session_not_found`**。

S1 路径单测仍有效：绝对路径、NUL、规范化后的 `..`、符号链接逃出隔离根 → `sandbox.path_denied`。

---

## 2. 强隔离（sidecar · 强于 S1 应用层）

| 层 | S1（仍保留） | S2 本档 |
|----|----------------|---------|
| 进程 | pico-api 内工作区目录 + 光栅子进程 | **`pico-sandbox` 独立容器/进程**；pico-api 只做薄 HTTP 客户端 |
| 用户 | 与 API 同 uid | 非 root（uid 65532）；`cap_drop: [ALL]`；`no-new-privileges` |
| 网络 | 应用层 `web_guard` | **独立 net ns**（非 `network_mode: host`）+ 同一套 `web_guard` 用户态出网过滤 |
| 内核 | 非微 VM | **不是**自研微 VM；gVisor/user ns 为等价档；禁止特权 Docker |
| B2 画面 | （无） | **Playwright/Chromium 真页面**；禁止 httpx+S2 光栅当 B2 完成 |

出网默认拒绝（复用 `web_guard`，即使没有 iptables/`NET_ADMIN`）：

- `10.0.0.0/8`、`127.0.0.0/8`、链路本地、`169.254.169.254` 云 metadata
- pico-api 端口 **18765**、产品 UI **8080 / 18088**（worker **不得绑定**这两口）
- 管理域 `pico.aivia.asia`

Compose：`docker-compose.host.yml` 服务 `pico-sandbox`。pico-api 经 `PICO_SANDBOX_URL`（host 部署为 `http://127.0.0.1:18767`）访问。侧车只把 18767 发到 loopback，**不**发布 8080/18088。

Chromium / Playwright **装进 sidecar 镜像**，无头 + viewport 截图。profile / `HOME` 指向容器 `/tmp`（compose tmpfs）。抓 HTML 再光栅 **不是** B2 完成条件。升级浏览器只改 sidecar，不改 Pi 真核。禁止宿主机 Chrome、禁止特权 Docker。

---

## 3. 看页（S1/S2 光栅 · 自己的 HTML）

网关工具仍是 `sandbox_preview_inspect`（不新造第二核）：

| 项 | 合同 |
|----|------|
| 入参 | `artifact_id` 或本次 `preview_url` |
| 出参 | `title` · `h1` · `seen=true` · `screenshot` / `raster` |
| 像素 | 对 **工作区 / 账本里这一次 HTML** 做无头光栅；PNG 魔数必须是真图 |
| 打开 | 老师用已有 `GET /v1/artifacts/{id}/content` 打开 PNG |
| 失败 | 光栅失败 **不得**打断主路径 |
| 进程 | 隔离子进程或同进程纯函数光栅；**禁止**对公网/内网建连 |

非法 URL 仍走 `web_guard`：`http://127.0.0.1:18765/health` → `web.denied`。

S1 光栅 **不是** B2 登录画面。B2 不得把公网 HTML 包进 `pico-b2-banner` 再光栅。

---

## 4. B2 人在环登录（公开站 · 真 Chromium）

```text
B2 登录 = 人在环（human-in-the-loop）+ sidecar Chromium
  老师看见隔离浏览器 viewport（截图 / view 页）
  点 viewport = mouse.click 进真 DOM；输入 = keyboard 进焦点控件
  禁止在聊天里发送密码（B3 OUT）
  会话 Cookie 只在 sidecar 内存 / tmpfs profile
  默认随 destroy / TTL 销毁（无耐久 Cookie 回宿主机家目录）

教务 / 微信扫码：不是必须过关
  站点禁自动化 → 人话失败（sandbox.site_blocks_automation）
  演示目标：example.com 或其它公开页（点链接后 URL/title 变）
  不把微信/教务登录成功写进完成条件
```

| 项 | 合同 |
|----|------|
| 工具 | `sandbox_browser_open`（url）· `sandbox_browser_screenshot`（session_id） |
| 引擎 | Playwright Chromium（sidecar）；`engine=playwright-chromium` |
| 画面 | 已认证 `GET /v1/sandbox/sessions/{id}/view` 展示 **Chromium viewport PNG** + 文案「请在此画面自行登录，不要在聊天里发送密码」 |
| 输入 | view 页把点击/输入转发进隔离 Chromium；密码字段不进 Event/日志/聊天/模型回显 |
| 证伪 | 点站内链接后 title/url 变化；合成横幅页（只改字幕）不得当完成 |
| 失败 | 内网/18765 → `web.denied`；微信/教务禁自动化 → 人话；侧车未起 / 无 Chromium → `sandbox.unavailable` |

`apply_input` 成功文案只描述真实 Chromium 路径，禁止再用合成光栅文案假装点击进了浏览器。

---

## 5. 明确禁止

- 特权 Docker、宿主机 bash 逃逸、自研微 VM 内核
- 在宿主机或 sidecar **占用 8080 / 18088** 起 Chrome
- 以 E2B 采购作为 **唯一** 完成条件（无账号必须 sidecar 自带 Chromium）
- B3 代登、聊天收集密码、把 Cookie 写进 Pico 账本当长期会话
- 用 httpx 抓 HTML + S2 光栅 / `pico-b2-banner` 冒充 B2 完成
- 改 #507 搜主路 · CLAIM-WB YES · #498 edu 嵌入 · #170 Kimi

---

## 6. 用量

`kind=sandbox` · `source=sandbox` · tokens 空 + `tokens_unknown=1`。  
`extra`：`duration_ms`、`workspace_id` 或 `session_id` / `artifact_id`。禁止钱字段。  
`record_usage_event` 永不抛进主路径。见 [`docs/USAGE-LEDGER.md`](./USAGE-LEDGER.md) §5。

---

## 7. 验收对照

1. 同 Run HTML inspect → title/h1 + 可打开的 PNG（魔数 `\x89PNG`）—— S1 保留
2. 跨账号截图/预览/B2 会话 → 404
3. `127.0.0.1:18765` inspect 与 browser_open → `web.denied`（另：10/8、169.254、`pico.aivia.asia`）
4. sidecar / worker **不绑定** 8080 或 18088；执行面不是 LibreChat 进程
5. B2 view 含人在环文案；像素来自 Chromium viewport；微信/教务不作为必须成功
6. 公开站点内点击后 URL/title 变化；合成横幅路径已删除
7. `CLAIM-WB-DEGREE-WEB: NO` · B3 未做
