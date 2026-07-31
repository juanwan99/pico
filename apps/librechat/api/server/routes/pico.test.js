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
});
