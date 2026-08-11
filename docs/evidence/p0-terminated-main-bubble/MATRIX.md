# MATRIX · T-P0-TERMINATED-MAIN-BUBBLE (#458)

```text
DATE: 2026-08-11
执行: Grok
公网 tip: bbe59f67ed507bfe126a44cb3e6a6c9ef4a0df20
部署: YES · #457 · prod-update on pico-prod
代码: PR #457 MERGED bbe59f67…（本卡无新增 fix PR）
CLAIM-WB: NO
```

| ID | 场景 | 结果 | 路径 | tip | 自读图要点 |
|----|------|------|------|-----|------------|
| **S1 部署** | tip 离开 502e1f6… | **PASS** | tip API + health | bbe59f67… | health.git_sha exact · true_pi_binary=true · ui_login=200 |
| **V1** | 主区失败文案 | **PASS** | [v1-fail-human/](./v1-fail-human/) | bbe59f67… | 主区中文「服务维护或重启…侧栏失败说明与主区应一致」· **无** Something went wrong · **无** 裸 terminated · 有「重新运行」 |
| **V2** | 侧栏 vs 主区 | **PASS** | 同 V1 帧 | bbe59f67… | 侧栏失败红字中文 · 顶栏失败+重新运行 · 主区同义中文；残影「正在准备…」标签仍可见但**不遮挡**失败终态（黄债 Y-prep 不挡） |
| **V3** | 孟德尔 HTML 新对话 | **PASS** | [v3-mendel/](./v3-mendel/) | bbe59f67… | 成功 · 芯片 · V3 打开人页「孟德尔遗传简释」· human_page=true |
| **V4** | 390 | **PASS** | v3-mendel/V2-final-390.png · v1-fail-human/V2-final-390.png | bbe59f67… | 可用 |

## 出口自检

- [x] tip 含 #457（`bbe59f67…`）
- [x] V1 主区无人话英文 terminated / Something went wrong
- [x] V2 失败中文一致 · 重新运行可达
- [x] V3 孟德尔类 HTML 成功可开
- [x] 证据本目录 · L1 将贴 #458
- [x] CLAIM-WB: NO
- [ ] 主管 L2 READY

## 黄债（不挡本卡 READY）

| ID | 说明 |
|----|------|
| **Y-prep** | 失败会话主列 Deepseek 头下仍可能残留「正在准备…」字样；失败气泡/顶栏/侧栏已是中文终态，未永久盖住失败 |
| **Y-mono** | visual-gate monologue 启发式假阳（题面含「系统侧」）· 人读为准 |

审查必须 **读图**；只读本表 = 审查无效。
