# C0 baseline · human read（post-502）

tip: `0b3bfa2a50dda498cb8a372c2f6d65d1956a4a56` · `https://pico.aivia.asia` · 2026-08-12

1. 公网入口恢复：`pico.aivia.asia` 不再 502；nginx → `127.0.0.1:18088`，LibreChat 不再与 edu-core-bff 争用 `8080`（EADDRINUSE 重启环已消除）。
2. 登录页：Pico 品牌登录壳正常渲染，邮箱登录表单可见，无 nginx 502/空白页。
3. 登录后主区：教师任务列表（tasklist）加载完成，侧栏会话/任务行可读，无「服务维护」失败条。
4. 健康：`/api/pico/health` loopback `git_sha` 与 tip `0b3bfa2a50dda498cb8a372c2f6d65d1956a4a56` 一致。
5. 本 PR 目标：把 live 已用的 `18088` 钉进 `docker-compose.host.yml`，防止下次 deploy 回写 `PORT=8080` 再炸公网。
