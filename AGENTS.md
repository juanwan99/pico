# Pico agent rules

协作流程只认正本 `$AGENT_POLICY_ROOT/TASK-POLICY.md`（默认 `/home/liang/agent-policy`），本文只写在 pico 里怎么写代码。

```text
最高: 禁止自搞一套体系。禁止做重体系。只对成熟上游做薄适配，桥变厚=违法（docs/LAW-NO-SELF-BUILD-THIN-ADAPTER.md）
发版: 发版目录只有 /opt/pico：PICO_DEPLOY_SHA=<40位> bash /opt/pico/scripts/prod-update.sh（合了就部，docs 也部）
      /home/ops/pico 不是发版目录，禁止从它 compose/build（#1186）。tip: curl -fsS https://pico.aivia.asia/api/pico/tip
```

## 写法

- `services/api/app/`：FastAPI，一个功能一个文件、各带 `router`；新路由在 `main.py` import + `app.include_router`。整组要登录写 `APIRouter(dependencies=[Depends(require_person)])`（例 `edu_school.py`）。
- `services/orchestrator/pico_orchestrator/`：模型、真 Pi（`true_pi/`）、办公（`office/`）、用量钩子。Pi 看到的工具说明在 `services/true_pi_bridge/pico-gateway-tools.ts` + `agent_assets/system.md`。
- 库：SQLAlchemy async + sqlite，表在 `db.py`；没有 alembic，加列写进 `_migrate_sqlite_sync`。
- 配置：`settings.py` `get_settings()`（lru_cache，字段名大写即环境变量）；测试改环境要 `get_settings.cache_clear()` 并把 `db._engine` / `db._Session` 置 None。
- 日志 `logger = logging.getLogger(__name__)`；报错 `HTTPException(detail={"code","message"})`。
- 测：`make install` 后 `pytest -q tests/unit/<文件>`；CI 另跑 `ruff check services tests scripts`（行宽 100）、`scripts/catch_guard.py`、`tests/security`、`tests/integration`。

## 现成函数（先找这些，别另写）

| 要做的 | 用 |
|---|---|
| 鉴权 / 计费方 | `app/auth.py` `require_scope` `require_person` `require_service_token` `payer_for` `enforce_feature` |
| 记账（唯一 AI 账） | `app/usage_ledger.py` `record_usage_event`（不抛错）`emit_llm_usage_after_run` `enforce_allowance` `export_usage_events`；工具用量 `usage_hook.emit_*_usage`；token 解析 `usage_parse.parse_usage_blob` |
| 调模型 | `provider.py` `resolve_provider` `call_once` `stream_chat` `thinking_extra_body`；备用链 `brain_ha.brain_candidates`；重试 `upstream.race` / `worth_retry`；带图换模型 `vision.vision_model_for_images` |
| 解析模型 JSON | `packages/exam-answer-extract/extract.py` `strip_fence` `parse_json_array`；读卷入口 `extract_pages` |
| 给老师看的报错 | `teacher_text.teacher_safe` `user_errors.user_message_for_error`；脱敏 `redact.redact_tenant_payload` |
| 文件 / 办公 | `app/artifact_store.py` `LedgerArtifactStore`；`office/sandbox_lib.run_office_lib_source_async` |
| 出网 / 本机判断 | `web_guard.assert_public_http_url`（防 SSRF）；`app/loopback.request_on_loopback_socket` |
| 真 Pi / edu | `true_pi/client.TruePiRpcClient`（单测用 `FakeTransport`）；`edu_adapter.list_classes` |

## 常见坑（详见 docs/EXPERIENCE.md 对应条）

- 模型只走 New API（`127.0.0.1:3000/v1`），不直连厂牌；Responses 必须 `stream:true`（§34）。现网主力与备用链看 §51 / §110。
- Gemini 3.x 走 Vertex `global`，`us-central1` 会 404（§99）；思考档位走 `extra_body.google.thinking_config`（§109）。
- token 拿不到记 unknown，不按字数估；edu 只拉 export（§36）。测试花的也是现网钥（§105）。
- 改 Python 里的工具说明 Pi 看不见，要改 `pico-gateway-tools.ts` / SYSTEM.md（§14 / §31）。
- `LedgerArtifactStore.read` 要传 `title=`（§30）；办公测试用 `PICO_OFFICE_URL=embedded`，生产禁用（§48）。
- git SHA 不当 Docker build-arg（§15）；同机只能一个 prod-update（flock，§97）；生产容器不继承宿主代理（§96）。
- 吞错：`catch_guard.py` 挡新改行里的空 except / 不记原因就 return·continue；确有理由行尾写 `# swallow-ok: <原因>`。

## E2E 过门登记（`ap-check` 机读，格式固定，每条独占一行）

命中下列路径的 PR，回执附 `E2E: <命令> → <结果> @<环境>`；`prod-update` 末尾跑同一条冒烟，失败即部署失败（#1095）。

E2E-PATHS: services/api/app/ scripts/prod-update.sh scripts/prod-update.impl.sh scripts/e2e-smoke.sh scripts/apply-gateway-nginx.sh docker-compose.host.yml Dockerfile.pico-api.true-pi Dockerfile.pico-api librechat.yaml .github/workflows/
E2E-SMOKE: bash scripts/e2e-smoke.sh --prod

制卡解析（edu-core#3703）：改了读卷提示词或读法（`packages/exam-answer-extract/`、`services/api/app/exam_answer_extract.py`）或换读卷模型，先起本 PR 临时栈，在 edu-core 跑十份固定真卷回归 `bash scripts/exam-card-parse-regress.sh --pico <临时栈地址>`（自己 `export PICO_EDU_ISS` / `PICO_EDU_JWT_SECRET`），合入发版后再跑 `--prod`。回执写 `E2E: bash scripts/exam-card-parse-regress.sh --pico <url> → PASS（对 n，已知未修 k，新错 0） @<环境>`；有新错先修，修不了不合。样卷在 edu-core `apps/bff/src/modules/exam/fixtures/card-parse-regress/`。
