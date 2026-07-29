/**
 * Proxy Pico ledger API. Browser → LibreChat (JWT required) → Pico loopback.
 * HARD: never expose unauthenticated; never trust client-supplied upstream URL.
 */
const express = require('express');
const { logger } = require('~/config');
const { requireJwtAuth } = require('~/server/middleware');

const router = express.Router();
router.use(requireJwtAuth);

const ID_RE = /^[A-Za-z0-9_-]{1,128}$/;

function picoBase() {
  const raw = process.env.OPENAI_REVERSE_PROXY || process.env.PICO_API_BASE || 'http://127.0.0.1:18765/v1';
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

async function proxy(req, res, path) {
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
    const text = await r.text();
    res.status(r.status);
    const ct = r.headers.get('content-type');
    if (ct) {
      res.setHeader('Content-Type', ct);
    }
    res.send(text);
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
router.get('/v1/workspaces', (req, res) => proxy(req, res, '/v1/workspaces'));
router.post('/v1/workspaces', (req, res) => proxy(req, res, '/v1/workspaces'));
router.delete('/v1/workspaces/:id', (req, res) => {
  try {
    assertId(req.params.id, 'id');
    return proxy(req, res, `/v1/workspaces/${req.params.id}`);
  } catch (e) {
    return res.status(400).json({ error: 'bad_request', message: e.message });
  }
});

module.exports = router;
