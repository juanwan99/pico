/**
 * Proxy Pico ledger API. Browser → LibreChat (JWT required) → Pico loopback.
 * HARD: ledger/task/artifact paths require JWT; never trust client-supplied upstream URL.
 * Exception (G4 tip observability): GET /api/pico/tip is public and returns only
 * {ok, git_sha, service} — no membership, canary, or secret fields.
 */
const express = require('express');
const { logger } = require('~/config');
const { requireJwtAuth } = require('~/server/middleware');

const router = express.Router();

const ID_RE = /^[A-Za-z0-9_-]{1,128}$/;
const SHA_RE = /^[0-9a-fA-F]{40}$/;

function picoBase() {
  const raw =
    process.env.OPENAI_REVERSE_PROXY || process.env.PICO_API_BASE || 'http://127.0.0.1:18765/v1';
  const base = raw.replace(/\/v1\/?$/, '');
  // only loopback / private env host — block accidental open proxy
  try {
    const u = new URL(base.includes('://') ? base : `http://${base}`);
    const host = u.hostname;
    if (!['127.0.0.1', 'localhost', '::1'].includes(host) && !host.endsWith('.local')) {
      // allow explicit PICO_API_BASE override for compose networks
      if (!process.env.PICO_API_BASE) {
        logger.warn(`[pico proxy] refusing non-local upstream host=${host}`);
        return 'http://127.0.0.1:18765';
      }
    }
    return `${u.protocol}//${u.host}`;
  } catch {
    return 'http://127.0.0.1:18765';
  }
}

/**
 * Public tip probe (no JWT). Minimal build identity for delivery cards / ops.
 * Full health JSON remains JWT-gated at /api/pico/health.
 */
router.get('/tip', async (_req, res) => {
  try {
    const r = await fetch(`${picoBase()}/health`);
    const j = await r.json();
    const rawSha = typeof j.git_sha === 'string' ? j.git_sha : null;
    // E2: only a full 40-char hex SHA is tip truth; invalid/short → null (never no-op pass-through).
    const gitSha = rawSha && SHA_RE.test(rawSha) ? rawSha : null;
    res.status(r.status).json({
      ok: j.ok === true && Boolean(gitSha),
      git_sha: gitSha,
      service: typeof j.service === 'string' ? j.service : 'pico-api',
    });
  } catch (e) {
    res.status(502).json({ ok: false, error: 'upstream_unavailable' });
  }
});

// All remaining ledger routes require an authenticated product session.
router.use(requireJwtAuth);

function picoKey() {
  return process.env.PICO_OPENAI_PROXY_KEY || process.env.OPENAI_API_KEY || 'sk-pico-dev';
}

function membershipFromReq(req) {
  const id = req.user?.id?.toString?.() || req.user?._id?.toString?.() || '';
  // sanitize for header
  return id.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 128) || 'anonymous';
}

function assertId(param, name) {
  if (!param || !ID_RE.test(param)) {
    const err = new Error(`invalid ${name}`);
    err.status = 400;
    throw err;
  }
  return param;
}

async function proxy(req, res, path, options = {}) {
  const { binary = false, allowDownload = false } = options;
  const qsIdx = req.originalUrl.indexOf('?');
  const qs = qsIdx >= 0 ? req.originalUrl.slice(qsIdx) : '';
  // only forward known safe query keys
  let safeQs = '';
  if (qs) {
    const sp = new URLSearchParams(qs.slice(1));
    const out = new URLSearchParams();
    if (sp.has('conversation_id')) {
      const cid = sp.get('conversation_id') || '';
      if (ID_RE.test(cid) || /^[A-Za-z0-9._:-]{1,128}$/.test(cid)) {
        out.set('conversation_id', cid);
      }
    }
    if (sp.has('task_id')) {
      const taskId = sp.get('task_id') || '';
      if (ID_RE.test(taskId)) {
        out.set('task_id', taskId);
      }
    }
    if (['proposed', 'confirmed', 'rejected'].includes(sp.get('status'))) {
      out.set('status', sp.get('status'));
    }
    if (allowDownload && ['1', 'true'].includes(sp.get('download'))) {
      out.set('download', 'true');
    }
    const s = out.toString();
    safeQs = s ? `?${s}` : '';
  }
  const target = `${picoBase()}${path}${safeQs}`;
  try {
    const headers = {
      Authorization: `Bearer ${picoKey()}`,
      Accept: 'application/json',
      'X-Pico-Membership-Id': membershipFromReq(req),
    };
    if (req.headers['content-type']) {
      headers['Content-Type'] = req.headers['content-type'];
    }
    if (req.headers['x-conversation-id'] && ID_RE.test(String(req.headers['x-conversation-id']))) {
      headers['X-Conversation-Id'] = String(req.headers['x-conversation-id']);
    }
    const init = { method: req.method, headers };
    if (req.method !== 'GET' && req.method !== 'HEAD' && req.body && Object.keys(req.body).length) {
      init.body = JSON.stringify(req.body);
      headers['Content-Type'] = 'application/json';
    }
    const r = await fetch(target, init);
    const body = binary ? Buffer.from(await r.arrayBuffer()) : await r.text();
    res.status(r.status);
    const ct = r.headers.get('content-type');
    if (ct) {
      res.setHeader('Content-Type', ct);
    }
    const disposition = r.headers.get('content-disposition');
    if (disposition) {
      res.setHeader('Content-Disposition', disposition);
    }
    const contentTypeOptions = r.headers.get('x-content-type-options');
    if (contentTypeOptions) {
      res.setHeader('X-Content-Type-Options', contentTypeOptions);
    }
    res.send(body);
  } catch (err) {
    logger.error('[pico proxy]', err);
    const code = err.status || 502;
    res.status(code).json({
      error: code === 400 ? 'bad_request' : 'pico_upstream_unavailable',
      message: String(err.message || err),
    });
  }
}

router.get('/health', async (req, res) => {
  try {
    const r = await fetch(`${picoBase()}/health`);
    const j = await r.json();
    res.status(r.status).json({ ...j, membership: membershipFromReq(req) });
  } catch (e) {
    res.status(502).json({ ok: false, error: String(e.message || e) });
  }
});

router.get('/v1/tasks', (req, res) => proxy(req, res, '/v1/tasks'));
router.get('/v1/tasks/:taskId', (req, res) => {
  try {
    assertId(req.params.taskId, 'taskId');
    return proxy(req, res, `/v1/tasks/${req.params.taskId}`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.get('/v1/tasks/:taskId/runs', (req, res) => {
  try {
    assertId(req.params.taskId, 'taskId');
    return proxy(req, res, `/v1/tasks/${req.params.taskId}/runs`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.get('/v1/runs/:runId', (req, res) => {
  try {
    assertId(req.params.runId, 'runId');
    return proxy(req, res, `/v1/runs/${req.params.runId}`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.get('/v1/runs/:runId/events', (req, res) => {
  try {
    assertId(req.params.runId, 'runId');
    return proxy(req, res, `/v1/runs/${req.params.runId}/events`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.post('/v1/runs/:runId/cancel', (req, res) => {
  try {
    assertId(req.params.runId, 'runId');
    return proxy(req, res, `/v1/runs/${req.params.runId}/cancel`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.post('/v1/tasks/:taskId/cancel-active', (req, res) => {
  try {
    assertId(req.params.taskId, 'taskId');
    return proxy(req, res, `/v1/tasks/${req.params.taskId}/cancel-active`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.post('/v1/runs/:runId/retry', (req, res) => {
  try {
    assertId(req.params.runId, 'runId');
    return proxy(req, res, `/v1/runs/${req.params.runId}/retry`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.get('/v1/artifacts/:artifactId/content', (req, res) => {
  try {
    assertId(req.params.artifactId, 'artifactId');
    return proxy(req, res, `/v1/artifacts/${req.params.artifactId}/content`, {
      binary: true,
      allowDownload: true,
    });
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.get('/v1/workspaces', (req, res) => proxy(req, res, '/v1/workspaces'));
router.get('/v1/skills/catalog', (req, res) => proxy(req, res, '/v1/skills/catalog'));
router.post('/v1/workspaces', (req, res) => proxy(req, res, '/v1/workspaces'));
router.delete('/v1/workspaces/:id', (req, res) => {
  try {
    assertId(req.params.id, 'id');
    return proxy(req, res, `/v1/workspaces/${req.params.id}`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});

router.post('/v1/tasks/rebind-conversation', (req, res) =>
  proxy(req, res, '/v1/tasks/rebind-conversation'),
);

router.get('/v1/automations', (req, res) => proxy(req, res, '/v1/automations'));
router.post('/v1/automations', (req, res) => proxy(req, res, '/v1/automations'));
router.post('/v1/automations/:id/run', (req, res) => {
  try {
    assertId(req.params.id, 'id');
    return proxy(req, res, `/v1/automations/${req.params.id}/run`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.post('/v1/automations/:id/enable', (req, res) => {
  try {
    assertId(req.params.id, 'id');
    return proxy(req, res, `/v1/automations/${req.params.id}/enable`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.post('/v1/automations/:id/disable', (req, res) => {
  try {
    assertId(req.params.id, 'id');
    return proxy(req, res, `/v1/automations/${req.params.id}/disable`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.delete('/v1/automations/:id', (req, res) => {
  try {
    assertId(req.params.id, 'id');
    return proxy(req, res, `/v1/automations/${req.params.id}`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});

router.get('/v1/changes', (req, res) => proxy(req, res, '/v1/changes'));
router.post('/v1/changes', (req, res) => proxy(req, res, '/v1/changes'));
router.get('/v1/changes/:id', (req, res) => {
  try {
    assertId(req.params.id, 'id');
    return proxy(req, res, `/v1/changes/${req.params.id}`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.post('/v1/changes/:id/confirm', (req, res) => {
  try {
    assertId(req.params.id, 'id');
    return proxy(req, res, `/v1/changes/${req.params.id}/confirm`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.post('/v1/changes/:id/reject', (req, res) => {
  try {
    assertId(req.params.id, 'id');
    return proxy(req, res, `/v1/changes/${req.params.id}/reject`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});

router.post('/v1/sandbox/sessions', (req, res) => {
  const url = typeof req.body?.url === 'string' ? req.body.url.trim() : '';
  if (!url || url.length > 2048) {
    return res.status(400).json({ error: 'bad_request', message: 'url required' });
  }
  return proxy(req, res, '/v1/sandbox/sessions');
});
router.get('/v1/sandbox/sessions/:sessionId', (req, res) => {
  try {
    assertId(req.params.sessionId, 'sessionId');
    return proxy(req, res, `/v1/sandbox/sessions/${req.params.sessionId}`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.get('/v1/sandbox/sessions/:sessionId/screenshot', (req, res) => {
  try {
    assertId(req.params.sessionId, 'sessionId');
    return proxy(req, res, `/v1/sandbox/sessions/${req.params.sessionId}/screenshot`, {
      binary: true,
    });
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});
router.post('/v1/sandbox/sessions/:sessionId/input', (req, res) => {
  try {
    assertId(req.params.sessionId, 'sessionId');
    // Do not log req.body — may contain a password typed in the result pane.
    return proxy(req, res, `/v1/sandbox/sessions/${req.params.sessionId}/input`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});

// R5: teacher self-read wrong paths → human 404 (not opaque Express default).
router.use((req, res) => {
  res.status(404).json({
    error: 'not_found',
    message:
      '未知 Pico 路径。教师常用：/api/pico/tip（公网 tip）、/api/pico/health、/api/pico/v1/tasks、' +
      '/api/pico/v1/runs/{id}、/api/pico/v1/artifacts/{id}/content?download=true。' +
      '除 /tip 外需登录 JWT；公网 SPA /health 只返回 OK，不是 Pico 账本 tip。',
    user_message:
      '找不到该接口。请从工作台结果区打开产物，或使用 /api/pico/v1/artifacts/{id}/content。',
  });
});

module.exports = router;
