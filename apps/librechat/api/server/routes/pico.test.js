const express = require('express');
const request = require('supertest');

jest.mock('~/server/middleware', () => ({
  requireJwtAuth: (req, _res, next) => {
    req.user = global.__PICO_USER || { id: 'member-123' };
    next();
  },
}));

const router = require('./pico');

describe('Pico proxy routes', () => {
  let app;

  beforeEach(() => {
    app = express();
    app.use(express.json());
    app.use('/api/pico', router);
    global.fetch = jest.fn().mockResolvedValue({
      status: 201,
      headers: { get: () => 'application/json' },
      text: async () => JSON.stringify({ id: 'task-1' }),
    });
  });

  afterEach(() => {
    delete global.fetch;
    delete global.__PICO_USER;
  });

  it('sends edu membership as joint school:member header', async () => {
    global.__PICO_USER = {
      id: 'mongo-user',
      eduId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      eduSchoolId: '627bcf3a-a9a8-4047-afcc-3d4878e2a7af',
    };
    await request(app).get('/api/pico/v1/tasks');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/tasks',
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-Pico-Membership-Id':
            '627bcf3a-a9a8-4047-afcc-3d4878e2a7af:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
        }),
      }),
    );
  });

  it('exposes public tip probe with minimal fields only', async () => {
    const sha = '5a900f69906630c8ad3843b371909eecc998ac4e';
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      json: async () => ({
        ok: true,
        service: 'pico-api',
        git_sha: sha,
        pi_agent_canary_membership_count: 99,
      }),
    });
    const response = await request(app).get('/api/pico/tip');
    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      ok: true,
      git_sha: sha,
      service: 'pico-api',
    });
    expect(response.body.pi_agent_canary_membership_count).toBeUndefined();
    expect(response.body.membership).toBeUndefined();
    expect(global.fetch).toHaveBeenCalledWith('http://127.0.0.1:18765/health');
  });

  it('proxies public HTML pages without JWT membership header', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      headers: {
        get: (name) =>
          ({
            'content-type': 'text/html; charset=utf-8',
            'content-security-policy': "default-src 'none'",
          })[name] || null,
      },
      arrayBuffer: async () => Buffer.from('<html>ok</html>'),
      text: async () => '<html>ok</html>',
    });
    const response = await request(app).get('/api/pico/p/pubTestPage01');
    expect(response.status).toBe(200);
    expect(response.headers['content-security-policy']).toBe("default-src 'none'");
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/p/pubTestPage01',
      expect.objectContaining({
        headers: expect.not.objectContaining({
          'X-Pico-Membership-Id': expect.anything(),
        }),
      }),
    );
  });

  it('serves HTML 404 for a short public page id instead of JSON not_found', async () => {
    const response = await request(app).get('/api/pico/p/abc');
    expect(response.status).toBe(404);
    expect(response.headers['content-type']).toMatch(/text\/html/);
    expect(response.text).toContain('This public page is not available');
    expect(response.body.error).toBeUndefined();
  });

  it('mounts short /p/:id without JWT membership header', async () => {
    const root = express();
    root.use(express.json());
    root.use('/p', router.publicRoot);
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      headers: {
        get: (name) =>
          ({
            'content-type': 'text/html; charset=utf-8',
            'content-security-policy': "default-src 'none'",
          })[name] || null,
      },
      arrayBuffer: async () => Buffer.from('<html>ok</html>'),
      text: async () => '<html>ok</html>',
    });
    const response = await request(root).get('/p/pubTestPage01');
    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/p/pubTestPage01',
      expect.objectContaining({
        headers: expect.not.objectContaining({
          'X-Pico-Membership-Id': expect.anything(),
        }),
      }),
    );
  });

  it('proxies public collect POST without JWT membership header', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      headers: { get: () => 'application/json' },
      text: async () => JSON.stringify({ ok: true, id: 'entry-1' }),
    });
    const response = await request(app)
      .post('/api/pico/p/pubTestPage01/collect')
      .send({ n: 'alice' });
    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/p/pubTestPage01/collect',
      expect.objectContaining({
        method: 'POST',
        headers: expect.not.objectContaining({
          'X-Pico-Membership-Id': expect.anything(),
        }),
      }),
    );
  });

  it.each(['unknown', 'abc', '5a900f69906630c8ad3843b371909eecc998ac4', 'not-a-sha', ''])(
    'rejects non-40-hex git_sha as tip truth (%s)',
    async (badSha) => {
      global.fetch = jest.fn().mockResolvedValue({
        status: 200,
        json: async () => ({
          ok: true,
          service: 'pico-api',
          git_sha: badSha,
        }),
      });
      const response = await request(app).get('/api/pico/tip');
      expect(response.status).toBe(200);
      expect(response.body.git_sha).toBeNull();
      expect(response.body.ok).toBe(false);
      expect(response.body.service).toBe('pico-api');
    },
  );

  it('forwards automation run-once requests to Pico API', async () => {
    const response = await request(app).post('/api/pico/v1/automations/automation-1/run');

    expect(response.status).toBe(201);
    expect(response.body).toEqual({ id: 'task-1' });
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/automations/automation-1/run',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'X-Pico-Membership-Id': 'member-123',
        }),
      }),
    );
  });

  it('rejects invalid automation ids without calling Pico API', async () => {
    const response = await request(app).post('/api/pico/v1/automations/bad.id/run');

    expect(response.status).toBe(400);
    expect(response.body).toEqual({ error: 'bad_request', message: 'invalid id' });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('forwards my-files folder create to Pico API', async () => {
    const response = await request(app)
      .post('/api/pico/v1/my/folders')
      .send({ name: '备课' });

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/my/folders',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: '备课' }),
      }),
    );
  });

  it('forwards my-files folder list to Pico API', async () => {
    const response = await request(app).get('/api/pico/v1/my/folders');
    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/my/folders',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('forwards my-files folder rename to Pico API', async () => {
    const response = await request(app)
      .patch('/api/pico/v1/my/folders/fold-1')
      .send({ name: '备课' });
    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/my/folders/fold-1',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ name: '备课' }),
      }),
    );
  });

  it('forwards run event requests to Pico API', async () => {
    const response = await request(app).get('/api/pico/v1/runs/run-1/events');

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/runs/run-1/events',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'X-Pico-Membership-Id': 'member-123',
        }),
      }),
    );
  });

  it('rejects invalid run ids for event requests', async () => {
    const response = await request(app).get('/api/pico/v1/runs/bad.id/events');

    expect(response.status).toBe(400);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('forwards run cancellation requests to Pico API', async () => {
    const response = await request(app).post('/api/pico/v1/runs/run-1/cancel');

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/runs/run-1/cancel',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'X-Pico-Membership-Id': 'member-123',
        }),
      }),
    );
  });

  it('rejects invalid run ids for cancellation requests', async () => {
    const response = await request(app).post('/api/pico/v1/runs/bad.id/cancel');

    expect(response.status).toBe(400);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('forwards failed run retry requests to Pico API', async () => {
    const response = await request(app).post('/api/pico/v1/runs/run-1/retry');

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/runs/run-1/retry',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'X-Pico-Membership-Id': 'member-123',
        }),
      }),
    );
  });

  it('rejects invalid run ids for retry requests', async () => {
    const response = await request(app).post('/api/pico/v1/runs/bad.id/retry');

    expect(response.status).toBe(400);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('forwards ask-answer to Pico API', async () => {
    const response = await request(app)
      .post('/api/pico/v1/runs/run-1/ask-answer')
      .send({ answer: '解释一下' });

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/runs/run-1/ask-answer',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ answer: '解释一下' }),
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'X-Pico-Membership-Id': 'member-123',
        }),
      }),
    );
  });

  it('forwards the read-only skill catalog request to Pico API', async () => {
    const response = await request(app).get('/api/pico/v1/skills/catalog');

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/skills/catalog',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          Authorization: expect.stringMatching(/^Bearer /),
          'X-Pico-Membership-Id': 'member-123',
        }),
      }),
    );
  });

  it.each([
    ['inline', '', 'inline; filename="result.txt"'],
    ['download', '?download=true&unsafe=secret', 'attachment; filename="result.txt"'],
  ])('proxies artifact bytes and safe headers for %s', async (_mode, query, disposition) => {
    const bytes = Buffer.from([0, 1, 2, 255]);
    global.fetch.mockResolvedValueOnce({
      status: 200,
      headers: {
        get: (name) =>
          ({
            'content-type': 'application/octet-stream',
            'content-disposition': disposition,
            'x-content-type-options': 'nosniff',
          })[name],
      },
      arrayBuffer: async () => bytes,
    });

    const response = await request(app).get(`/api/pico/v1/artifacts/artifact-1/content${query}`);

    expect(response.status).toBe(200);
    expect(response.body).toEqual(bytes);
    expect(response.headers['content-type']).toMatch(/^application\/octet-stream/);
    expect(response.headers['content-disposition']).toBe(disposition);
    expect(response.headers['x-content-type-options']).toBe('nosniff');
    expect(global.fetch).toHaveBeenCalledWith(
      `http://127.0.0.1:18765/v1/artifacts/artifact-1/content${query ? '?download=true' : ''}`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          'X-Pico-Membership-Id': 'member-123',
        }),
      }),
    );
  });

  it('forwards preview=1 so Office content-box HTML is not stripped to a zip', async () => {
    const html = Buffer.from(
      '<!doctype html><html><body><article class="page">页</article></body></html>',
    );
    global.fetch.mockResolvedValueOnce({
      status: 200,
      headers: {
        get: (name) =>
          ({
            'content-type': 'text/html; charset=utf-8',
            'content-disposition': 'inline; filename="doc.html"',
            'x-content-type-options': 'nosniff',
            'x-pico-preview': 'office-content-box',
            'content-security-policy': "default-src 'none'; img-src data:",
          })[name],
      },
      arrayBuffer: async () => html,
    });

    const response = await request(app).get(
      '/api/pico/v1/artifacts/artifact-1/content?preview=1&unsafe=secret',
    );

    expect(response.status).toBe(200);
    expect(response.headers['content-type']).toMatch(/text\/html/);
    expect(response.headers['x-pico-preview']).toBe('office-content-box');
    expect(response.headers['content-security-policy']).toMatch(/default-src 'none'/);
    expect(response.text).toContain('class="page"');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/artifacts/artifact-1/content?preview=1',
      expect.objectContaining({ method: 'GET' }),
    );
    const upstreamUrl = global.fetch.mock.calls[0][0];
    expect(upstreamUrl).not.toContain('download');
    expect(upstreamUrl).not.toContain('unsafe');
  });

  it('forwards mine=true when listing my artifacts', async () => {
    await request(app).get('/api/pico/v1/artifacts?mine=true&unsafe=drop');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/artifacts?mine=true',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('rejects invalid artifact ids without calling Pico API', async () => {
    const response = await request(app).get('/api/pico/v1/artifacts/bad.id/content');

    expect(response.status).toBe(400);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('forwards only supported filters when listing task changes', async () => {
    const response = await request(app).get(
      '/api/pico/v1/changes?task_id=task-1&status=proposed&unsafe=secret',
    );

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/changes?task_id=task-1&status=proposed',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          'X-Pico-Membership-Id': 'member-123',
        }),
      }),
    );
  });

  it.each(['confirm', 'reject'])('forwards change %s requests to Pico API', async (action) => {
    const response = await request(app).post(`/api/pico/v1/changes/change-1/${action}`);

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      `http://127.0.0.1:18765/v1/changes/change-1/${action}`,
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'X-Pico-Membership-Id': 'member-123',
        }),
      }),
    );
  });

  it.each(['confirm', 'reject'])(
    'rejects invalid change ids for %s without calling Pico API',
    async (action) => {
      const response = await request(app).post(`/api/pico/v1/changes/bad.id/${action}`);

      expect(response.status).toBe(400);
      expect(global.fetch).not.toHaveBeenCalled();
    },
  );

  it('proxies POST /v1/sandbox/sessions for result-pane open', async () => {
    const response = await request(app)
      .post('/api/pico/v1/sandbox/sessions')
      .send({ url: 'https://example.com/' });

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/sandbox/sessions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ url: 'https://example.com/' }),
      }),
    );
  });

  it('rejects empty sandbox open url without calling Pico API', async () => {
    const response = await request(app).post('/api/pico/v1/sandbox/sessions').send({ url: '  ' });
    expect(response.status).toBe(400);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('proxies POST /v1/sandbox/sessions for Writer open', async () => {
    const response = await request(app)
      .post('/api/pico/v1/sandbox/sessions')
      .send({ kind: 'writer', filename: '课堂笔记.docx' });

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/sandbox/sessions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ kind: 'writer', filename: '课堂笔记.docx' }),
      }),
    );
  });

  it('proxies POST /v1/sandbox/sessions for files desk', async () => {
    const response = await request(app)
      .post('/api/pico/v1/sandbox/sessions')
      .send({ kind: 'files' });

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/sandbox/sessions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ kind: 'files' }),
      }),
    );
  });

  it('proxies DELETE sandbox session without wiping owner disk', async () => {
    const response = await request(app).delete(
      '/api/pico/v1/sandbox/sessions/sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
    );
    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/sandbox/sessions/sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('proxies owner disk list', async () => {
    const response = await request(app).get('/api/pico/v1/sandbox/disk');
    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/sandbox/disk',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('proxies sandbox session meta for the result pane', async () => {
    const response = await request(app).get(
      '/api/pico/v1/sandbox/sessions/sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
    );

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/sandbox/sessions/sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          'X-Pico-Membership-Id': 'member-123',
        }),
      }),
    );
  });

  it('proxies sandbox screenshot bytes', async () => {
    const bytes = Buffer.from([0x89, 0x50, 0x4e, 0x47]);
    global.fetch.mockResolvedValueOnce({
      status: 200,
      headers: { get: (name) => (name === 'content-type' ? 'image/png' : null) },
      arrayBuffer: async () => bytes,
    });
    const response = await request(app).get(
      '/api/pico/v1/sandbox/sessions/sbox_aaaaaaaaaaaaaaaaaaaaaaaa/screenshot',
    );
    expect(response.status).toBe(200);
    expect(response.body).toEqual(bytes);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/sandbox/sessions/sbox_aaaaaaaaaaaaaaaaaaaaaaaa/screenshot',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('forwards pane input JSON without inventing a second path', async () => {
    const response = await request(app)
      .post('/api/pico/v1/sandbox/sessions/sbox_aaaaaaaaaaaaaaaaaaaaaaaa/input')
      .send({ click_x: 12, click_y: 40 });

    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/sandbox/sessions/sbox_aaaaaaaaaaaaaaaaaaaaaaaa/input',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ click_x: 12, click_y: 40 }),
      }),
    );
  });

  it('returns human 404 for unknown teacher self-read paths', async () => {
    const response = await request(app).get('/api/pico/v1/artifacts/artifact-1/download');

    expect(response.status).toBe(404);
    expect(response.body.message).toMatch(/content|产物|路径|Pico/i);
    expect(response.body.user_message).toBeTruthy();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('proxies school material search with membership header', async () => {
    global.__PICO_USER = {
      id: 'mongo-user',
      eduId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      eduSchoolId: '627bcf3a-a9a8-4047-afcc-3d4878e2a7af',
    };
    const response = await request(app).get('/api/pico/v1/edu/materials').query({ q: '课时' });
    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/edu/materials?q=%E8%AF%BE%E6%97%B6',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          'X-Pico-Membership-Id':
            '627bcf3a-a9a8-4047-afcc-3d4878e2a7af:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
        }),
      }),
    );
  });

  it('forwards field_id when listing a venue\'s documents', async () => {
    const response = await request(app)
      .get('/api/pico/v1/edu/materials')
      .query({ q: '课时', field_id: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee' });
    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/edu/materials?q=%E8%AF%BE%E6%97%B6&field_id=aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('proxies named school material ids for this conversation', async () => {
    const response = await request(app)
      .put('/api/pico/v1/edu/named')
      .send({ conversation_id: 'c1', ids: ['aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'] });
    expect(response.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/edu/named',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          conversation_id: 'c1',
          ids: ['aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'],
        }),
      }),
    );
  });

  it('proxies points quote and settle without extra query keys', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      headers: { get: () => 'application/json' },
      text: async () => JSON.stringify({ phase: 'quote', points: '0.120', wallet: false }),
    });
    const quoted = await request(app)
      .post('/api/pico/v1/usage/points/quote')
      .send({ input_chars: 80 });
    expect(quoted.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/usage/points/quote',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ input_chars: 80 }),
      }),
    );

    await request(app).get('/api/pico/v1/usage/points?run_id=run_abc-1');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/usage/points?run_id=run_abc-1',
      expect.objectContaining({ method: 'GET' }),
    );

    await request(app).get('/api/pico/v1/usage/points?conversation_id=c-1');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/usage/points?conversation_id=c-1',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('forbids teacher role from the gateway admin snapshot', async () => {
    global.__PICO_USER = { id: 'member-123', role: 'USER' };
    const response = await request(app).get('/api/pico/v1/admin/gateway');
    expect(response.status).toBe(403);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('proxies gateway admin snapshot for ADMIN', async () => {
    global.__PICO_USER = { id: 'admin-1', role: 'ADMIN' };
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      headers: { get: () => 'application/json' },
      text: async () => JSON.stringify({ ok: true, sub2api_is_frontend: false }),
    });
    const response = await request(app).get('/api/pico/v1/admin/gateway');
    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/admin/gateway',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('forbids teacher role from gateway account soft actions', async () => {
    global.__PICO_USER = { id: 'member-123', role: 'USER' };
    const response = await request(app).post('/api/pico/v1/admin/gateway/accounts/9/refresh');
    expect(response.status).toBe(403);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('proxies allowlisted soft actions for ADMIN and rejects unknown verbs', async () => {
    global.__PICO_USER = { id: 'admin-1', role: 'ADMIN' };
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      headers: { get: () => 'application/json' },
      text: async () => JSON.stringify({ ok: true, message: '已交给上游。' }),
    });
    const ok = await request(app).post('/api/pico/v1/admin/gateway/accounts/9/refresh');
    expect(ok.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/admin/gateway/accounts/9/refresh',
      expect.objectContaining({ method: 'POST' }),
    );
    const badVerb = await request(app).post(
      '/api/pico/v1/admin/gateway/accounts/9/apply-oauth-credentials',
    );
    expect(badVerb.status).toBe(400);
    const badId = await request(app).post('/api/pico/v1/admin/gateway/accounts/0/refresh');
    expect(badId.status).toBe(400);
  });

  it('forwards memory list and delete to Pico API', async () => {
    const listed = await request(app).get('/api/pico/v1/memory');
    expect(listed.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/memory',
      expect.objectContaining({ method: 'GET' }),
    );

    const deleted = await request(app).delete('/api/pico/v1/memory?name=MEMORY.md');
    expect(deleted.status).toBe(201);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:18765/v1/memory?name=MEMORY.md',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});
