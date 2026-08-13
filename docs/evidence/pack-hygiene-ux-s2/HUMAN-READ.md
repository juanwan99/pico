# pack-hygiene-ux-s2 · 人眼帧（待公网装 tip 后补）

本目录在合入 PR 时 **只有说明、没有 PNG**。假图不进仓。

执行者在 **public deploy 且 `health.git_sha` 对上候选 SHA** 之后，把真 PNG（各 >20KB）放到本目录：

| 帧文件（建议名） | 人要看见什么 |
|------------------|--------------|
| `search-sources.png` | 公网一题搜索后，结果区或主过程至少 1 个 **可点来源链接** |
| `search-miss.png` | 未检索时诚实文案 **未检索到可用来源**（没有编造的 URL） |
| `preview-open.png` | 生成的 HTML 页能打开（结果区/成品条） |
| `inspect-seen.png` | inspect 后过程可见 title/h1，并有截图/光栅可打开 |
| `v390.png` | 视口宽约 390 至少 1 帧 |

```text
CLAIM-WB-DEGREE-WEB: NO
不要在本 PR 用生产站截图冒充已验收
```
