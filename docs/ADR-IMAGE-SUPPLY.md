# ADR · 出图供应链（Gemini · New API · Pico 熔断）

```text
DOC: docs/ADR-IMAGE-SUPPLY.md
ID: ADR-IMAGE-SUPPLY
DATE: 2026-08-29
STATUS: Proposed · 等业主一句「架构锁定」
CLAIM-WB: 不改签（已 YES · 本 ADR 不代签）
REPO: juanwan99/pico ONLY
LAW: docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md
北极星: docs/DIRECTION-NOW.md §0-star · 用法 = Grok
现况: docs/STATE-NOW.md · 本 ADR 是出图接线真源，不是在飞卡
卡: #778 T-GEMINI-IMAGE-CHAIN · 同域禁止第二张 stamp-ok
```

---

## 0. 一句话

```text
三个 Gemini 号先放进 New API 渠道组（轮询 · 等权 · 每渠道 RPM）。
Pico 只打一个网关 URL + 现在一个 token；429/401 换 token 是熔断，不是 Google 轮询核。
百号以后加 New API 渠道 / 出口机，不在 Pico 堆一百把钥。
```

PR 三问：

| 问 | 答 |
|----|----|
| 适配哪段？ | 老师 `generate_image` → New API `generateContent` |
| 上游是谁？ | New API（业主机）+ Google Gemini 官方 generateContent |
| 升级只改适配层？ | 加号 / 加 RPM / 换出口 = 只改 New API；Pico 仍是 URL + token + 人话失败 |

---

## 1. 三层（不许倒）

```text
老师（LibreChat）
  generate_image          ← 唯一出图动词；进程内一次一张
        │
        ▼
Pico 薄适配               ← 本仓只许这一层变代码
  PICO_IMAGE_GATEWAY_URL
  PICO_IMAGE_GATEWAY_KEY     （现在 1 把）
  PICO_IMAGE_GATEWAY_KEYS    （熔断备件，不是三号矩阵）
  失败：出图通道繁忙 / 拒绝 · 不编像素
        │  Authorization: Bearer <New API token>
        ▼
New API                   ← 农场真源（轮询 / 权重 / RPM 住这里）
  组：gemini-image
  现在：3 个 Gemini 渠道 = 3 个 Google 号
  以后：加渠道，不改 Pico
        │
        ▼
Google Gemini generateContent
  Pico 看不见号、cookie、出口 IP
```

| 层 | 现在（三账号） | 以后（百号） |
|----|----------------|--------------|
| **号** | 3 把 Gemini API key，各进 New API 一条渠道 | 继续加渠道；按出口机分组 |
| **组** | 一个渠道组 · 轮询 · 权重 1/1/1 · 每渠道 RPM | 多组；组内仍轮询 |
| **槽** | Pico **1** 个 New API token 打这一组 | 每台 New API / 每个出口 **1** 个 token，不是每号 1 个 Pico 密钥 |
| **锁** | Pico 进程内一次一张图 | 仍一次一张；并行打三号 = 像农场，禁止 |

聊天脑仍是 AIProxy OpenAI（`gpt-5.6-sol`）。出图不打 AIProxy `…/gemini`。经验 §34。

---

## 2. 三个 Google AI Pro 怎么用

**Pro 网页套餐 ≠ Pico 出图配额。** 官方：[Google AI Plans](https://ai.google.dev/gemini-api/docs/google-ai-plans) — 订阅加的是 AI Studio **网页**额度；用 API key 打外部应用（New API / Pico）是另一套账，按 Gemini API Free / Cloud Billing 走。

| 这三号买到的 | Pico 能用的 |
|--------------|-------------|
| gemini.google.com / App 里更高出图次数 | **不能**接到老师课。禁 cookie / 网页套餐反代 |
| AI Studio 网页 Playground 更高额度 | **不能**被 New API 消耗 |
| 三个独立 Google 身份 | **能**：每号一把 **API key** → New API 三条渠道 |

**正确用法（每号做一遍，钥不进 git/Issue）：**

1. 三个账号各开一个浏览器配置，登录 [Google AI Studio](https://aistudio.google.com)。
2. 该号下 **Create API key**（Gemini Developer API）。不要导出登录 cookie。
3. New API 加渠道：类型 **Gemini / Google Gemini（API key）**，不是「Gemini 网页 / cookie」。一把 key 一条渠道。三号同一组。
4. Pico 仍只填一把 New API token。老师出图走 `generateContent`。

**Pro 还干什么：** 你自己在 Gemini 网页 / AI Studio 里画、试模型。那条路的额度不会流进 pico.aivia.asia。

**用量 / 速率：New API 统控，Pico 不自研限流核。** 三渠道同一组：轮询、等权、每渠道 RPM/RPD 宁低。Pico 只熔断。New API **不能变出** Google 定价页上不存在的免费张数。

**官方价目（2026-08-29 查 [pricing](https://ai.google.dev/gemini-api/docs/pricing) · [billing](https://ai.google.dev/gemini-api/docs/billing) · [rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)）：**

| 问 | 官方结论 |
|----|----------|
| 不开 Billing，Pico 现网 `gemini-3.1-flash-image` 有没有免费张？ | **没有。** 定价表 Free Tier = **Not available**。论坛实锤 429 `GenerateRequestsPerDayPerProjectPerModel-FreeTier` **limit: 0**。不是「额度很小」，是免费档配额指标就是 0。 |
| 开了 Billing 有没有赠送免费出图？ | **没有。** 开 Billing = 付费档，**从第 1 张起按张计费**。付费档变高的是 RPM/RPD **上限**（能买多少张），不是赠送张。付费里写的每月 5000 次免费是 **Search grounding**，不是出图。2026-03-02 后 Cloud **$300 Welcome credit 不能付 Gemini API**。 |
| 一张图多少钱？（现网模型 Standard 1K） | 图输出约 **$0.067/张**（1120 token × $60/百万）。另加提示词输入 **$0.50/百万 token**（课堂一句提示通常远小于 1 美分）。Batch 半价。更便宜的付费出图：`gemini-3.1-flash-lite-image` 约 **$0.034/张**、`gemini-2.5-flash-image` **$0.039/张**——同样 **无免费档**。 |

课堂粗算（只算图输出、1K）：100 张 ≈ $6.7；1000 张 ≈ $67。三号只是三份速率桶，**不会把单价砍成三分之一**。

开 Billing 常见还要 **预存至少 $10**。用 spend cap 硬顶，不要只设预算邮件。Tier 1 账单封顶默认 $250/月（Billing 账户级）。

**无免费 API ≠ 走登录反代。** 账户 cookie / 网页套餐反代 / New API「Gemini 网页」渠道 **不是退路**（ToS、风控、cookie 过期、Pico 法禁止自研第二图核）。正路只剩：① API key + Billing + New API 限速（课堂百张约数美元）；② 换更便宜的官方出图模型（仍付费）；③ 老师课先不出这张模型，人话失败、不编像素。禁止第四条。

**实测仍建议：** 每把 key 不开 Billing 打一张。预期 429 limit 0；若偶发 200，以你的项目为准（官方不保证）。

不是再买第四份网页 Pro，也不是 cookie。

---

## 3. 现在就做（三账号 · 机上，不进 git）

Google 钥、New API token **禁止**进仓 / Issue / PR。只在 New API 管理台和主机 `.env`。

1. 三个 Gemini 号，各一把 **API key**（不是网页套餐 cookie）。
2. New API：三条 **Gemini** 渠道，一条渠道一把 key。
3. 三条进**同一组**。策略：轮询（或等权）。每渠道单独 RPM/RPD（由 New API 统控，宁低）。不要在 Pico 再做一套限流核。
4. 若管理台有「失败试下一条渠道」：打开。这样一次 Pico 请求里，号 A 429 会换号 B，Pico 不必持三把 token。
5. Pico 主机：`PICO_IMAGE_GATEWAY_URL` + **一把** 能打该组的 New API token。模型现网认 `gemini-3.1-flash-image`，走 `POST …/v1beta/models/{model}:generateContent`。
6. **不要**把 `GEMINI_API_KEY` 当生产主路（那会从 ECS 直连 Google，风控更差）。
7. 不要为「凑满三槽」再写 `KEY_1`/`KEY_2`/`KEY_3`。Pico 数的是 **New API token 把数**，不是 Gemini 号数。一把 token + 三条渠道 = 架构已满三号。

`PICO_IMAGE_GATEWAY_KEYS` 留给：第二台 New API、出口拆分、或一把 token 整组烧穿时的备件。三账号阶段可以空。

---

## 4. Pico 熔断（已有 · 不再加厚）

仓内只允许：

- 一个网关 URL
- 少量 New API token（逗号列表）
- 429/401 立刻换下一把 token；每把默认间隔 2s
- 全忙 → 人话「出图通道繁忙」，不编 png
- health 只报 `image_gateway_key_count`（把数），**不报** Gemini 号数、不报密钥

禁止（违法 · 与网页套餐反代同级）：

- Pico 里轮询 Google 钥 / 把 `GEMINI_API_KEY_*` 当产品矩阵
- Pico 代理池、住宅 IP、cookie 农场
- Pico 当 Google 限流内核（RPM/权重/优先级）
- 硅基流动出图
- 无图还标成功

一把 Pico token 不够三号 **不算薄、不算失败**。号在 New API。Pico 0 把 token 才 fail-closed。

---

## 5. 出口 IP（现在不做 · 以后不进 Pico）

三号共一台 New API、一个 NAT：Google 看见「三把钥、一个出口」。这是小团队常态，不是农场。**现在不拆 IP。**

百号仍共一个出口时，才像农场。拆法：

```text
New API 机 A + NAT A  ← 一组号
New API 机 B + NAT B  ← 另一组号
Pico 仍只认 1～几个 URL/token
```

Pico 永远不知道某次请求打了哪一个 Google IP。出口是 New API 运维，不是编排核。

---

## 6. 失败怎么说（老师面）

| 情况 | 老师看见 |
|------|----------|
| 组内换号成功 | 一张图（不知道换过号） |
| 三号都 429 / 组配额尽 | 出图通道繁忙 · 请稍后再试 · 不能编造图片 |
| 网关未接 / 0 token | 出图尚未接通 |
| 余额类（如 New API 1113） | 拒绝 · 不空转重试 |

---

## 7. 若 New API 不能「组内换渠道」

少数面板一次请求 429 就直接回客户端、不试同组下一条。那时才用 **备选接线**（仍不是 Google 轮询核）：

- 三条渠道各绑一个 New API token（或三个只含一条渠道的组）
- Pico `PICO_IMAGE_GATEWAY_KEYS` 填这三把 **New API token**
- 429/401 换下一把

先确认管理台有没有「失败重试其他渠道」。有则走第 3 节默认；没有再启用本备选。不要两种同时当真源。

---

## 8. 锁定句（业主回这一行即可）

```text
架构锁定：三号在 New API 一组；Pico 一把 token；用量/速率只认 New API；默认不开 Billing；出口以后再拆。
```

改选时只准改第 7 节备选，不准在 Pico 建 IP/cookie/Google 钥农场。
