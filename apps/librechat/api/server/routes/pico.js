/**
 * Proxy Pico ledger API (Task/Run/Artifact/Workspace) so the browser only talks to LibreChat.
 * Upstream: OPENAI_REVERSE_PROXY host (default http://127.0.0.1:18765)
 */
const express = require('express');
const { logger } = require('~/config');

const router = express.Router();

function picoBase() {
  const raw = process.env.OPENAI_REVERSE_PROXY || process.env.PICO_API_BASE || 'http://127.0.0.1:18765/v1';
  // strip trailing /v1
  return raw.replace(/\/v1\/?$/, '');
}

function picoKey() {
  return (
    process.env.PICO_OPENAI_PROXY_KEY ||
    process.env.OPENAI_API_KEY ||
    'sk-pico-dev'
  );
}

async function proxy(req, res, path) {
  const url = `${picoBase()}${path}${req.url.includes('?') ? '' : ''}`;
  // req.url is path after mount when using router; rebuild with query
  const qs = req.originalUrl.includes('?') ? req.originalUrl.slice(req.originalUrl.indexOf('?')) : '';
  const target = `${picoBase()}${path}${qs}`;
  try {
    const headers = {
      Authorization: `Bearer ${picoKey()}`,
      Accept: 'application/json',
    };
    if (req.headers['content-type']) {
      headers['Content-Type'] = req.headers['content-type'];
    }
    if (req.headers['x-conversation-id']) {
      headers['X-Conversation-Id'] = req.headers['x-conversation-id'];
    }
    if (req.headers['x-workspace-id']) {
      headers['X-Workspace-Id'] = req.headers['x-workspace-id'];
    }
    const init = {
      method: req.method,
      headers,
    };
    if (req.method !== 'GET' && req.method !== 'HEAD' && req.body) {
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
    res.status(502).json({ error: 'pico_upstream_unavailable', message: String(err.message || err) });
  }
}

router.get('/health', async (req, res) => {
  try {
    const r = await fetch(`${picoBase()}/health`);
    const j = await r.json();
    res.status(r.status).json(j);
  } catch (e) {
    res.status(502).json({ ok: false, error: String(e.message || e) });
  }
});

router.get('/v1/tasks', (req, res) => proxy(req, res, '/v1/tasks'));
router.get('/v1/tasks/:taskId', (req, res) => proxy(req, res, `/v1/tasks/${req.params.taskId}`));
router.get('/v1/tasks/:taskId/runs', (req, res) =>
  proxy(req, res, `/v1/tasks/${req.params.taskId}/runs`),
);
router.get('/v1/runs/:runId', (req, res) => proxy(req, res, `/v1/runs/${req.params.runId}`));
router.get('/v1/workspaces', (req, res) => proxy(req, res, '/v1/workspaces'));
router.post('/v1/workspaces', (req, res) => proxy(req, res, '/v1/workspaces'));
router.delete('/v1/workspaces/:id', (req, res) =>
  proxy(req, res, `/v1/workspaces/${req.params.id}`),
);

module.exports = router;
