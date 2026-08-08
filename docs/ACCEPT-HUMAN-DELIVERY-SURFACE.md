# ACCEPT · T-HUMAN-DELIVERY-SURFACE

```text
STATUS: BINDING 验收尺子
PARENT: docs/PLAN-HUMAN-DELIVERY-SURFACE.md
CLAIM-WB: NO
```

## 一票否决（交付类）

| ID | 门 | FAIL 若 |
|----|-----|---------|
| A1 | 主聊天回复 | 出现 Artifact ID / L0·L1 字段名 / verification_level / 全量 HTML 源码墙 |
| A2 | 下载 | 公网登录 UI **结果区**无以**文件名**为主的下载芯片，或点下载拿不到文件 |
| A3 | 打开 | 下载后本机打开不可用（源码墙 HTML / 空文件） |
| A4 | 审查 | 仅 API 冒烟、无 UI 下载路径却写 PASS |

## 通过图像

```text
用户提示完成
  → 主回复：人包（文件名 + 用途 + 打开方式）
  → 右侧结果区：可下载文件（N）· 文件名 · 【下载】【打开】
  → 本机打开能用
机审 / verify / delivery.summary 仅在事件与 API，默认不进主气泡
```

## 审查纠正（相对旧尺子）

| 旧 | 新 |
|----|-----|
| API 冒烟可过部署/交付卡 | **UI 下载路径**为交付类卡必选项 |
| 执行窗本机打开 = 人类 Y | 仅当 **公网登录 UI**（或业主）路径算人类交付 Y |
| 机审字段出现无所谓 | 主回复机审字段 = **体验 FAIL** |

## 回归题（人类视角）

1. 孟德尔（或同构课件）HTML：UI 下载 + 打开见 UI  
2. 隐式多文件：≥2 下载芯片，主文无 ID  
3. 闲聊：无产物芯片、无机审表  
4. 负例：若模型贴源码，服务端剥离后仍可下载  

```text
HUMAN_DELIVERY_SURFACE: PASS ⇔ A1–A4 + 回归
CLAIM-WB: NO
```
