# Codex：生产热更新提示词

将下方代码块整段交给 Codex（可 SSH/宝塔）。完整边界见 `docs/CODEX-VPS-INVESTIGATION.md`。

```text
目标：在 139.196.147.40 /opt/pico 热更新 Git 分支 grok/pico-preview-librechat-p0，
验收 https://pico.aivia.asia 登录+真聊。禁止重装/换壳/PROXY=1/自 PASS。

cd /opt/pico && bash scripts/prod-update.sh
# 登录坏：bash scripts/vps-fix-login.sh
# 本机：curl health 18765；login API；S1 chat 演示OK
# 浏览器：https://pico.aivia.asia/login teacher@example.com / <redacted-demo-password>
报告：SHA、compose ps、health、login、S1、浏览器 Y/N。不合 main。
```
