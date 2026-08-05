# Pico 全球 Product PASS 合同

```text
STATUS: BINDING definition
ENGINEERING_COMPLETE_IS_NOT_PRODUCT_PASS: true
DEFAULT: PRODUCT PASS NOT CLAIMED
```

## 1. 范围

“全球”指所有已授权学校租户的教师主路径：登录、创建并运行任务、查看过程、停止或重试、打开和下载产物、在 390px 与桌面宽度继续操作。范围同时包含租户隔离、账本一致性、Kimi-only 多步运行和生产运维；不包含 edu-cloud、实验模型或未发布 persona。

## 2. 必过门禁

| 门禁 | 完成证据 |
|---|---|
| 登录与鉴权 | 错密拒绝；授权账号进入工作台；无跨租户读取 |
| 任务闭环 | 创建→运行→唯一终态；in-flight cancel 后 cancelled sticky；重试不脏账本 |
| 产物 | 至少一种真实文件非空，记录 SHA-256，并从结果区打开和下载 |
| 移动端 | 390px 主控件普通点击成功，禁止 `force` 或 pointer-events 绕过 |
| 编排 | 默认 multi-step 为 Kimi Agent；树中无 transitional loop；非 Kimi 路径 fail-closed |
| 可靠性 | CI 绿；生产 health `git_sha` 等于签字 SHA；登录/health 长窗无未解释 5xx |
| 安全运维 | secrets 不进日志/Issue；限流与轮换演练有脱敏记录；回滚使用旧 tip redeploy |

任何 P0 FAIL、缺证或仅靠文档推断都不得签 PASS。

## 3. 证据与角色

- 写入窗提供 CANDIDATE、完整 SHA、CI 与 evidence map，`VERDICT_AUTHORITY: NONE`。
- 部署窗提供真实 `DEPLOYED` 和 exact health SHA。
- 独立验证窗使用已登录浏览器提供 TEST REPORT、run/conversation 指纹和必要截图；不得回显凭据或原始敏感 ID。
- 总管汇总门禁；只有业主可用下述句式最终 ACCEPT。

```text
OWNER ACCEPT: GLOBAL PRODUCT PASS @ <40-char production SHA>
```

## 4. 禁止项

禁止用 ENGINEERING complete 代替全球 PASS，禁止恢复 loop、dual-run、Pi/DeepSeek 默认、假 DEPLOYED、红 CI 合并、打印密钥或把 edu-cloud 纳入 Pico 交付。

## 5. ENGINEERING complete 边界

Orchestration ENGINEERING complete 只表示代码和生产证据证明：Kimi-only multi-step、无 transitional loop、非 Kimi fail-closed、Wire/session/账本/cancel/产物路径完整。它不证明所有 persona、浏览器、学校或长窗可靠性，因而 **不等于 Product PASS**。

## 6. 本阶段执行子集

#295 只冻结本合同定义，并执行其任务卡 A、D、E、F、G、H 所列抽测；全球 Product PASS 全集另开 STAGE，由独立验证和业主签字。默认状态保持 **PRODUCT PASS NOT CLAIMED**。
