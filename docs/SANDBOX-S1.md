# SANDBOX-S1 · 隔离工作区 + 看见自己的页

```
DOC: docs/SANDBOX-S1.md
STATUS: BINDING · T-SANDBOX-S1-ISOLATE-PREVIEW (#508)
REPO: juanwan99/pico ONLY
CLAIM-WB: NO
NOT: cloud PC · E2B · B3 代登 · host Chrome on 8080/18088 · 自研微 VM
```

> **S1 最小闭环：** 老师在隔离工作区写一页 HTML → 结果区/短 TTL 预览可打开 → 系统抽取 title/h1（或等价「看见」证据）回给模型 → 可再改第二版。  
> 真核仍是上游 Pi harness；本卡只做进程级隔离、账本门闩、预览验真。不是一校一机。

与 [#505](https://github.com/juanwan99/pico/issues/505) 规划对齐；计量走 [#506](https://github.com/juanwan99/pico/issues/506) `kind=sandbox`。**不改** [#507](https://github.com/juanwan99/pico/issues/507) `web_search` / `web_fetch` 主路。

---

## 1. 隔离键

```text
isolation_key = school_id + membership_id + run_id
```

| 段 | Pico 名 | 说明 |
|----|---------|------|
| 校 | `principal.school_id` | 租户 |
| 人 | `principal.membership_id` | 账号（任务卡口中的 user_id） |
| 次 | `run_id`（无 Run 时 `_norun`） | 一次办事；并发 Run 不共用工作区目录 |

**耐久产物账本**（`ArtifactRow`）仍按 `school_id + membership_id` 过滤：跨账号读失败（404 / `artifact.not_found`）。`run_id` 绑在行上，供本次预览/看页使用。

**进程级工作区目录**（可选落盘，非微 VM）：

```text
$PICO_SANDBOX_ROOT / {school_id} / {membership_id} / {run_id} / <safe_filename>
```

默认 `PICO_SANDBOX_ROOT` = `{tmpdir}/pico-sandbox-s1`。段名经 `safe_segment`：拒绝 `.` `..` `/` `\` 控制字符。跨账号路径永不重叠。

返回给模型的 `workspace_id` 是隔离键的短哈希（不回显 raw school/membership）。

---

## 2. 禁访列表（工作区路径 + 看页）

工作区读写 **禁止** 指向：

- 父路径 / 绝对路径 / 符号链接逃出隔离根
- `/etc` `/proc` `/sys` `/root` `/home` 宿主机目录
- 文件名像密钥：`.env` `id_rsa` `credentials.json` `*.pem`（写入拒绝）
- 宿主机 bash、特权 Docker、占用 **8080 / 18088** 起 Chrome

看页工具 **禁止** HTTP 抓取：

- 任意公网站（那是 #507 `web_fetch`）
- 内网 / 环回 / 链路本地 / 云 metadata（复用 `web_guard`）
- `pico.aivia.asia` 管理面、`127.0.0.1`、`localhost`、pico-api 端口 **18765**
- **例外：** URL 的 path 是 **本次租户/账号** 的 `/v1/artifacts/{id}/content` 预览（可带短 TTL `exp`+`sig`）。此时只读 Pico 账本，**不**对目标主机建连。

---

## 3. 超时 / 体积

| 操作 | 上限 |
|------|------|
| workspace 读/写/list | 8s（`asyncio.wait_for`） |
| 文本内容 | 200_000 字符；UTF-8 ≤ 256_000 字节 |
| 看页 HTML | 同上；超时杀掉解析 |
| 可选轻 exec | 5s；仅隔离目录内 ast.parse / HTML 解析；禁止 `import os/subprocess` 与 bash |

超限 → `workspace.timeout` / `tool.invalid_arguments`，不落宿主机。

---

## 4. 预览（可证伪）

HTML 产物返回：

- `preview_path` = `GET /v1/artifacts/{id}/content`（已有结果区打开方式；需本人 JWT）
- `preview_url` = 同上 + `preview=1&exp=&sig=`（短 TTL，默认 15 分钟；HMAC 绑 school+membership+run+artifact）
- 另一账号 JWT 打开 → **404**（现有 `get_artifact_for_principal`）
- 签名不能把 B 变成 A：验签用调用者身份；错签/过期 → 拒绝

不新造 LibreChat 门脸。`?preview=1` 且本人打开 HTML 时，API 可用 `text/html` + CSP sandbox，便于结果区当页打开。

---

## 5. B0 看页

网关工具 `sandbox_preview_inspect`：

- 入参：`artifact_id` 或 `preview_url`（本次预览）
- 出参：`title`、`h1`、`seen=true`（无头 Chrome、不占 8080/18088）
- 文本回给模型，证明「看见了这页」
- 非法 URL 走 `web_guard` 拒绝，不抓取

**S2 升档**（[#513](https://github.com/juanwan99/pico/issues/513) / [#516](https://github.com/juanwan99/pico/issues/516) 段 B）：同工具对本次 HTML 另产 PNG 光栅；公开站登录画面走独立 `pico-sandbox` sidecar（人在环 B2）。合同见 [`SANDBOX-S2.md`](./SANDBOX-S2.md)。S1 行为保持。

---

## 6. 用量

`kind=sandbox` · `source=sandbox` · tokens 可空 + `tokens_unknown=1`。  
`extra`：`duration_ms`、`workspace_id` 或 `artifact_id`。禁止钱字段。  
`record_usage_event` 永不抛进主路径。见 `docs/USAGE-LEDGER.md` §5。

---

## 7. 可选轻 exec

解释器/构建只在隔离目录：超时杀掉。  
**禁止** bash 出工作区、宿主机 shell、特权 Docker。S1 不自研微 VM（LAW-NO-SELF-BUILD）。

---

## 8. 验收对照

1. 跨校 / 跨 membership 读工作区拒绝（单测 + `/v1/tools/invoke`）
2. 账号 A 的预览/产物，账号 B → 404
3. 同 Run HTML 看页得到 title/h1；`http://127.0.0.1:18765/health` 拒绝
4. sandbox 用量事件 `billing: false`、无 money keys
5. 8080 未回潮 · `CLAIM-WB-DEGREE-WEB: NO`
