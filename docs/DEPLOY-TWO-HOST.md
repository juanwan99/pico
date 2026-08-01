# 双机部署：写代码 ECS（跳板）+ Pico 生产机

```
DOC: docs/DEPLOY-TWO-HOST.md
STATUS: BINDING 运维约定
DATE: 2026-07-30
```

## 1. 角色

| 主机 | 用途 | 标志 |
|------|------|------|
| **dev-ecs**（写代码 / Codex 常驻） | clone、改代码、测、开 PR | 有源码；通常无公网 Pico 的 8080/18765 |
| **pico-prod**（生产） | `/opt/pico`、docker、nginx、`pico.aivia.asia` | `curl 127.0.0.1:18765/health` 有 JSON |

代码只经 **GitHub main** 流向生产。dev-ecs **不**再起一套公网 Pico 冒充生产。

## 2. 拓扑（dev-ecs 当跳板）

```text
Codex @ dev-ecs  --git push/PR-->  GitHub main
Codex @ dev-ecs  --ssh pico-prod-->  /opt/pico pull + rebuild + DEPLOYED
```

业主选择：写代码 ECS 作 SSH 跳板，同一 Codex 兼顾开发与部署。

## 3. 一次性配置

### 3.1 生产机 pico-prod

- 路径：`/opt/pico` → 远程 `juanwan99/pico`
- 用户可 `git pull` + `docker compose`
- 安全组：优先仅允许 **dev-ecs 内网 IP** 访问 22

### 3.2 dev-ecs 上 `~/.ssh/config`

```sshconfig
Host pico-prod
  HostName REPLACE_PICO_PROD_IP
  User REPLACE_DEPLOY_USER
  IdentityFile ~/.ssh/pico_prod_deploy
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
  ServerAliveInterval 30
  ServerAliveCountMax 3
```

（若需再跳：加 `ProxyJump other-host`。）

### 3.3 自检（在 dev-ecs）

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 pico-prod \
  'hostname; test -d /opt/pico && echo HAS_PICO; curl -sS --max-time 3 http://127.0.0.1:18765/health | head -c 240'
```

成功：`HAS_PICO` + health JSON。失败则停，禁止假 DEPLOYED。

### 3.4 密钥

- 独立部署密钥，只授权 pico-prod
- 权限 600；勿把 API key 放进 ssh 配置

## 4. 开发 + 部署环

1. Codex@dev-ecs：实现 → PR → CANDIDATE  
2. CI 绿 → 总管审查 → 总管合 main  
3. Codex@dev-ecs：ssh pico-prod 执行 pull/rebuild  
4. 公网冒烟 + PR 评论 `## DEPLOYED`  

## 5. 部署命令模板（dev-ecs 上）

```bash
PICO_DEPLOY_SHA="${PICO_DEPLOY_SHA:?set full 40-character main SHA}"

ssh -o BatchMode=yes pico-prod "set -euo pipefail
cd /opt/pico
if [ -x scripts/prod-update.sh ]; then
  PICO_DEPLOY_SHA=$PICO_DEPLOY_SHA bash scripts/prod-update.sh
else
  echo 'BLOCKED: exact-SHA deploy script missing' >&2
  exit 2
fi
curl -sS --max-time 5 http://127.0.0.1:18765/health
ss -lntp | grep -E '18765|8080|27017' || true
"
curl -sS -o /dev/null -w 'public_login=%{http_code}\n' https://pico.aivia.asia/login
```

评论：

```text
## DEPLOYED
- via: dev-ecs jump → pico-prod
- main SHA:
- health.git_sha:
- smoke:
```

## 6. 禁止

- 在 dev-ecs 创建 `/opt/pico` 当公网生产  
- 无 ssh 通写 DEPLOYED  
- 部署时改业务代码（生产只 pull）  
- PROXY=1；18765/27017/8080 绑公网  
- 与 edu 目录混用乱 cd  

## 7. 故障

| 现象 | 处理 |
|------|------|
| dev 无 /opt/pico、本机 8080 拒绝 | 正常；ssh pico-prod |
| ssh 超时 | 安全组/IP/密钥 |
| 认证后 session 挂 | ForceCommand / keys 里 command= |
| health 旧 SHA | 打错机或未 rebuild |

## 8. RACI

- 写入可同时 dev 编码 + jump 部署  
- 总管合 main 并核对 DEPLOYED  
- 交接只走 GitHub  
