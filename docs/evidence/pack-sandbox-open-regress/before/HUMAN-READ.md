# T-SANDBOX-OPEN-REGRESS · 公网 before

```text
tip: de6cbe01ce05d270df46760578ef9838b5f7f649
公网: https://pico.aivia.asia
拍法: 登录后真点 · 非 CSS 假帧
CLAIM-WB: NO
Word 不当失败现场
```

## S1 `打开 https://example.com` · `S1-example-before.png`

右栏最后因 run 终态撑开。模型只做了 `web_fetch`，中间是摘抄，不是立刻点火 sidecar。栏开之后 `ResultPanel` 才读到 URL 意图，画面是一小块 Example Domain。老师要等跑完。

## S1b `打开浏览器` · `S1b-open-browser-before.png`

这次模型碰巧调了 `sandbox_browser_open`，所以有 Example Domain。前端 `detectOpenWebsiteIntent('打开浏览器')` 现网是 `null`，不能当稳定路径。

## S1c `打开腾讯官网` · `S1c-tencent-before.png`

失败现场。模型 `web_fetch` 写了一篇官网摘要。右栏因终态撑开，但是 **「沙箱还没有打开窗口」**。没有 URL，intent 不点火，sidecar 没打。

## S2 `打开一份 Word` · `S2-word-before.png`

基线：LibreOffice Writer 真窗口，有标尺/正文。本卡不修 Writer。

## 调查结论

1. ChatView `resultOpen` 默认 false。ResultPanel 不挂 = 不会 `openWebsiteInPane`。
2. `detectOpenWebsiteIntent` 只认明文 URL/主机名。「打开浏览器」「打开腾讯官网」返回 null。
3. run `succeeded` 会无条件开栏 → 腾讯这条变成空沙箱；「你好」也会误开。
4. Word 走 Writer，不要动。

帧哈希见 `report.json`。
