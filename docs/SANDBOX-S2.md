# SANDBOX-S2 · 同页光栅 / 截图证据

```
DOC: docs/SANDBOX-S2.md
STATUS: BINDING · T-HYGIENE-SEARCH-UX-SANDBOX-S2 (#513)
REPO: juanwan99/pico ONLY
CLAIM-WB: NO
EXTENDS: docs/SANDBOX-S1.md（S1 仍有效；本页只升「看见」一档）
NOT: cloud PC · E2B-as-only-done · B3 代登 · host Chrome on product ports · 自研微 VM
```

> **S2 相对 S1：** 老师在隔离工作区写一页 HTML 之后，`sandbox_preview_inspect` 仍回 **title / h1 / `seen=true`**，并且对 **本次 Run 的同一份 HTML** 产出 **真实 PNG 光栅**（可打开的像素证据，不是改后缀的文本）。  
> 真核仍是上游 Pi harness。本档只做进程级看页光栅、账本产物、隔离单测加固。不是一校一机。

与 [#505](https://github.com/juanwan99/pico/issues/505) 规划对齐；计量仍走 [#506](https://github.com/juanwan99/pico/issues/506) `kind=sandbox`。**不改** [#507](https://github.com/juanwan99/pico/issues/507) `web_search` / `web_fetch` 主路（仅 UX 展示来源）。

---

## 1. 隔离键（同 S1）

```text
isolation_key = school_id + membership_id + run_id
```

工作区目录、`safe_segment`、耐久产物按账号过滤：跨账号读仍 **404 / `artifact.not_found`**。  
S2 额外单测：绝对路径、NUL、规范化后的 `..`、符号链接逃出隔离根 → `sandbox.path_denied`。

---

## 2. 看页（S2）

网关工具仍是 `sandbox_preview_inspect`（不新造第二核）：

| 项 | 合同 |
|----|------|
| 入参 | `artifact_id` 或本次 `preview_url` |
| 出参 | `title` · `h1` · `seen=true` · `screenshot` / `raster`（`artifact_id`、`download_path`、`mime=image/png`、`byte_size`） |
| 像素 | 对 **工作区 / 账本里这一次 HTML** 做无头光栅（file 内容或内存）；PNG 魔数必须是真图 |
| 打开 | 老师用已有 `GET /v1/artifacts/{id}/content` 打开 PNG |
| 失败 | 光栅失败 **不得**打断主路径；解析成功则仍回 title/h1 |
| 进程 | 隔离子进程或同进程纯函数光栅；**禁止**对公网/内网建连 |

非法 URL 仍走 `web_guard`：`http://127.0.0.1:18765/health` → `web.denied`。不抓取任意公网站（那是 #507 `web_fetch`）。

---

## 3. 登录 / 教务（本档边界）

```text
B2 登录 = 人在环（human-in-the-loop）
  本档做到：预览画面/截图回模型 + 合同写清「登录以后怎么做」
  完整扫码登微信 / 教务自动填表 = OUT（#505 未书面放行）

教务 / 微信扫码：默认拒绝
B3 代登：OUT（禁止代老师登录任何站点）
```

S2 **不**实现站点登录、cookie 注入、扫码中转。需要登录才能「看见」的页：人在环打开预览，系统只光栅 **已在本次工作区的 HTML**。

---

## 4. 明确禁止

- 在宿主机占用产品/调试浏览器端口起 Chrome（S1/S2 源码与运行均不得去绑那些端口）
- 对 `pico.aivia.asia` 管理面或任意公网做 inspect 抓取
- 自研微 VM 内核、特权 Docker、宿主机 bash 逃逸
- 以 E2B 采购/租户作为 **唯一** 完成条件（无租户也须用进程内光栅完成看页）
- 把文本改后缀当成 PNG

Chromium / Playwright 若将来放进 pico-api 镜像：必须隔离进程、不得占上述端口、不得当 SSRF 出口。当前实现用进程内/子进程 **真 PNG 光栅**（Pillow 或等价编码器），不依赖宿主机浏览器。

---

## 5. 用量

同 S1：`kind=sandbox` · `source=sandbox` · tokens 空 + `tokens_unknown=1`。  
`extra`：`duration_ms`、`workspace_id` 或 `artifact_id`（HTML 和/或截图 id）。禁止钱字段。  
`record_usage_event` 永不抛进主路径。见 [`docs/USAGE-LEDGER.md`](./USAGE-LEDGER.md) §5。

---

## 6. 验收对照

1. 同 Run HTML inspect → title/h1 + 可打开的 PNG（魔数 `\x89PNG`）
2. 跨账号截图/预览 → 404 / `artifact.not_found`
3. `127.0.0.1:18765` inspect → `web.denied`
4. 绝对路径 / NUL / `..` / 外逃 symlink → 拒绝
5. `CLAIM-WB-DEGREE-WEB: NO` · B3 未做 · 教务默认拒绝
