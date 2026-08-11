# M1 · Pico Web vs WorkBuddy 教程路径对比表

```text
DOC: docs/CLAIM-MATERIALS-2026-08/01-COMPARE-WB.md
DATE: 2026-08-11
终验 tip: 502e1f6fd5d3f5999b43303de91b16de1375f26a
尺子: docs/HANDOFF-WB-PI.md 六条 · docs/ACCEPT-WB-STYLE-W1-W5.md
CLAIM-WB: NO
```

> **判定口径（Web 行为，非桌面 1:1）**  
> - **不弱**：同维度达到教程级「派活→执行→交件→可改→诚实」  
> - **更强**：Web 登录即用 / 人页打开等相对桌面本地的优势（诚实写）  
> - **边界**：本期明确不做（桌面 workDir、连接器、Remotion 等）  
> - **弱**：证据显示明显短板（黄债维度）

WorkBuddy「教程级期望」= 开放自然语言派活、多步工具、真文件落盘、同会话改一版、完成态可见、HTML/产物可打开；**不**要求像素 1:1、桌面 exe、微信连接器、自研 MCP 栈。

---

## 对比总表

| 维度 | WorkBuddy 教程级期望 | Pico Web 现状（@ tip 502e1f6…） | 判定 | 证据（帧 / run / 路径） |
|------|----------------------|--------------------------------|------|------------------------|
| **开放派活** | 自然语言开干，不先锁场景卡 | 公网默认入口可直接发开放域题（番茄钟 / 项目包 / 市集表…） | **不弱** | `pack-final-matrix/six/1-open/` · `w1/` · MATRIX S1 EXCELLENT |
| **多步工具** | 真工具环，非单轮闲聊 | pi-true 默认 · 多 `write_file` / 步骤可见 | **不弱** | `six/3-multistep/` · `w5/` · MATRIX S3 · T0-env health pi-true |
| **真文件** | 产物可下可开 | 交付芯片 + 下载/打开；HTML human_page | **不弱** | `w1/V3-open-product.png` · `six/4-artifacts/` · `pack-ux-harden/u5-mendel/` |
| **可改一版** | 同会话跟进改价/改稿 | 菜单 v1→v2 改价+季节款 成功交付 | **不弱** | `six/5-edit/` · MATRIX S5 EXCELLENT |
| **完成态诚实** | 有件真成功、无件不假绿 | 交付题成功+芯片；边界/负例「暂无产物」 | **不弱** | `six/6-honest/` · `w3/` · `w4/` · `neg/under-deliver/` |
| **HTML 可玩** | 可运行小工具/互动页 | 番茄钟 25:00 人页可交互；孟德尔 HTML 可开 | **不弱**（Web 人页打开友好） | `w1/V3-open-product.png` · `human/A2-open/` · `pack-ux-harden/u5-mendel/` |
| **多文件包** | ≥3 文件联动办公/项目包 | W5=5 芯片联动；L1=8 芯片 a–h；U5 多文件≥3 | **不弱** | `w5/V2-final.png` · `long-or-session/` · `pack-ux-harden/u5-multifile/` |
| **人交付** | 主气泡人话 · 成品条 · 闲聊无假条 | A1–A4 PASS；闲聊「暂无产物」 | **不弱**（W5 气泡偏密=黄债见 M2） | `human/A1-bubble/` · `A2-open/` · `A3-chat/` · `A4-390/` · `pack-ux-harden/u5-chat/` |
| **失败/停止** | 失败可读 · 可停 | 失败中文人话+重新运行；双停止文案可辨 | **不弱** | `pack-ux-harden/u1-fail-human/` · `u2-dual-stop/` · `regress-u1u2/` · `RUN-DRAIN-AND-STOP.md` |
| **桌面 workDir / 本地 exe** | 桌面本机目录顶格 | **Web 浏览器登录** · 无本地 workDir 顶格 | **边界** | HANDOFF §1.2 明确不纳入本期 · LAW 禁自研壳 |
| **微信/企业连接器** | 连接器生态 | 本期不做连接器/MCP 铺开；边界题诚实拒假部署 | **边界** | DIRECTION-NOW · `w4/` · `neg/under-deliver/` |
| **工具广度** | 教程常见全工具面 | 真 Pi 薄桥 **7 工具白名单**（见 M2） | **边界**（非「弱到不能办事」；范围刻意收） | `TRUE-PI-BRIDGE-DUTIES.md` 七工具表 |
| **主气泡洁净（高压题）** | 交付说明优先人话 | 交付题大体洁净；W4 源码块 / W5 清单偏密 | **弱（局部）** | 黄债 Y-w4-src · Y-w5-dense · #448 主管 L2 |

---

## 六条硬标准（HANDOFF）对齐

| # | 标准 | Pico 证据摘要 | 判定 |
|---|------|---------------|------|
| 1 | 开放派活 | S1 / W1 开放域新表述 | 不弱 |
| 2 | 能力架可见 | S2 / W5 步骤与工具过程可感知 | 不弱 |
| 3 | 多步执行 | S3 / W5 多 write | 不弱 |
| 4 | 真产物 | S4 / W1 V3 人页 | 不弱 |
| 5 | 任务资产/改一版 | S5 同会话改价 | 不弱 |
| 6 | 完成态 | S6 有件成功；N1/W4 无件不假绿 | 不弱 |

MATRIX 真源：[`docs/evidence/pack-final-matrix/MATRIX.md`](../evidence/pack-final-matrix/MATRIX.md)

---

## 读图建议入口（业主 / 主管 5 分钟）

| 必看 | 路径 |
|------|------|
| HTML 打开 | `docs/evidence/pack-final-matrix/w1/V3-open-product.png` |
| 多文件芯片 | `docs/evidence/pack-final-matrix/w5/V2-final.png` |
| 改一版 | `docs/evidence/pack-final-matrix/six/5-edit/V2-final.png` |
| 边界诚实 | `docs/evidence/pack-final-matrix/w4/V2-final.png` |
| 负例不假绿 | `docs/evidence/pack-final-matrix/neg/under-deliver/V2-final.png` |
| 失败人话 | `docs/evidence/pack-ux-harden/u1-fail-human/V2-final.png` |

---

## 工程声明

```text
本表 = 工程装订对比 · 证据指针齐全
不等于 CLAIM-WB: YES
局部「弱/边界」已写入 M2，未藏
CLAIM-WB: NO
```
