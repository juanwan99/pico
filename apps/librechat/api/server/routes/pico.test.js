const express = require('express');
const request = require('supertest');

jest.mock('~/server/middleware', () => ({
  requireJwtAuth: (req, _res, next) => {
    req.user = { id: 'member-123' };
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
  });

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

  it('returns human 404 for unknown teacher self-read paths', async () => {
    const response = await request(app).get('/api/pico/v1/artifacts/artifact-1/download');

    expect(response.status).toBe(404);
    expect(response.body.message).toMatch(/content|产物|路径|Pico/i);
    expect(response.body.user_message).toBeTruthy();
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
