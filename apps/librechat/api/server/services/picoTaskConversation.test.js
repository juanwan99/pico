const express = require('express');
const request = require('supertest');
const { EModelEndpoint, Constants } = require('librechat-data-provider');
const { version } = require('uuid');
const { getConvo, saveConvo, saveMessage } = require('~/models');

jest.mock('~/models', () => ({
  getConvo: jest.fn(),
  saveConvo: jest.fn(),
  saveMessage: jest.fn(),
}));

jest.mock('~/server/middleware', () => ({
  requireJwtAuth: (req, _res, next) => {
    req.user = { id: 'teacher-mongo', eduSchoolId: 'our-school', eduId: 'our-member' };
    next();
  },
}));

const router = require('../routes/pico');

const conversationId = '12345678-1234-4234-9234-123456789abc';
const runId = '12345678-1234-4234-9234-123456789def';
const mobile = {
  id: 'task-1',
  source: 'mobile',
  conversation_id: conversationId,
  title: '备课记录',
  latest_run: { id: runId, status: 'succeeded' },
};
const model = 'workbench-default-model';

describe('Pico mobile task conversations', () => {
  const app = express();
  app.use('/api/pico', router);
  const sync = () => request(app).post('/api/pico/task-conversations/sync');
  let conversations;
  let messages;
  const oldFetch = global.fetch;
  const oldModels = process.env.OPENAI_MODELS;

  function core({ tasks = [mobile], uploads = [] } = {}) {
    global.fetch = jest.fn(async (url) => {
      const { pathname, search } = new URL(url);
      const data = {
        '/v1/tasks': { tasks },
        [`/v1/tasks?conversation_id=${conversationId}`]: { tasks: [mobile, ...uploads] },
        [`/v1/runs/${runId}`]: { run: { id: runId, prompt: '整理备课记录' } },
        [`/v1/runs/${runId}/events`]: {
          events: [
            { type: 'message.final', payload: { text: '旧稿' } },
            { type: 'message.final', payload: { text: '备课记录已整理。' } },
            { type: 'run.status', payload: { status: 'succeeded' } },
          ],
        },
      }[pathname + search];
      if (!data) {
        throw new Error(`Unexpected core path ${pathname + search}`);
      }
      return { ok: true, json: async () => data };
    });
  }

  beforeEach(() => {
    process.env.OPENAI_MODELS = `${model},other-model`;
    conversations = new Map();
    messages = new Map();
    getConvo.mockImplementation(async (user, id) => conversations.get(`${user}:${id}`));
    saveMessage.mockImplementation(async ({ userId }, message) => {
      messages.set(`${userId}:${message.messageId}`, message);
      return message;
    });
    saveConvo.mockImplementation(async ({ userId }, conversation) => {
      conversations.set(`${userId}:${conversation.conversationId}`, conversation);
      return conversation;
    });
  });

  afterEach(() => {
    global.fetch = oldFetch;
    if (oldModels === undefined) {
      delete process.env.OPENAI_MODELS;
    } else {
      process.env.OPENAI_MODELS = oldModels;
    }
  });

  it('imports the final answer and original prompt with an attachment count, then skips repeats', async () => {
    core({
      uploads: [
        { title: 'edu-read · a.png', latest_run: null },
        { title: 'edu-read · b.jpg', latest_run: null },
      ],
    });
    await sync().expect(200, { created: 1 });

    const convo = conversations.get(`teacher-mongo:${conversationId}`);
    expect(convo).toEqual(
      expect.objectContaining({
        conversationId,
        title: mobile.title,
        endpoint: EModelEndpoint.openAI,
        model,
      }),
    );
    const [user, assistant] = Array.from(messages.values());
    expect(user).toMatchObject({
      conversationId,
      parentMessageId: Constants.NO_PARENT,
      isCreatedByUser: true,
      text: '整理备课记录\n\n（手机拍了 2 张照片）',
    });
    expect(assistant).toMatchObject({
      conversationId,
      parentMessageId: user.messageId,
      isCreatedByUser: false,
      text: '备课记录已整理。',
    });
    expect(version(user.messageId)).toBe(5);
    expect(version(assistant.messageId)).toBe(5);
    await sync().expect(200, { created: 0 });
    expect(saveConvo).toHaveBeenCalledTimes(1);
    expect(saveMessage).toHaveBeenCalledTimes(2);

    conversations.clear();
    await sync().expect(200, { created: 1 });
    expect(Array.from(messages.values())).toEqual([user, assistant]);
  });

  it('creates only one copy across two simultaneous requests and keeps another user separate', async () => {
    conversations.set(`other-user:${conversationId}`, { title: '别人的对话' });
    core();
    const responses = await Promise.all([sync().expect(200), sync().expect(200)]);
    expect(responses.map((res) => res.body.created).sort()).toEqual([0, 1]);
    expect(saveConvo).toHaveBeenCalledTimes(1);
    expect(saveMessage).toHaveBeenCalledTimes(2);
    expect(Array.from(messages.values())[0].text).toBe('整理备课记录');
    expect(conversations.get(`other-user:${conversationId}`).title).toBe('别人的对话');
  });

  it('skips running, failed, old, unbound and already opened tasks', async () => {
    conversations.set(`teacher-mongo:${conversationId}`, { title: '电脑改过的标题' });
    core({
      tasks: [
        mobile,
        { ...mobile, conversation_id: 'running', latest_run: { status: 'running' } },
        { ...mobile, conversation_id: 'failed', latest_run: { status: 'failed' } },
        { ...mobile, source: null, conversation_id: 'desktop' },
        { ...mobile, conversation_id: null },
      ],
    });
    await sync().expect(200, { created: 0 });
    expect(saveConvo).not.toHaveBeenCalled();
    expect(saveMessage).not.toHaveBeenCalled();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(conversations.get(`teacher-mongo:${conversationId}`).title).toBe('电脑改过的标题');
  });

  it('creates nothing when the membership has no tasks', async () => {
    core({ tasks: [] });
    await sync().expect(200, { created: 0 });
    expect(saveConvo).not.toHaveBeenCalled();
    expect(saveMessage).not.toHaveBeenCalled();
  });

  it('surfaces an unreachable core as a proxy failure', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('ECONNREFUSED'));
    await sync().expect(502, { error: 'pico_upstream_unavailable' });
    expect(saveConvo).not.toHaveBeenCalled();
  });

  it('can retry when the conversation save fails', async () => {
    core();
    saveConvo.mockResolvedValueOnce({ message: 'Error saving conversation' });
    await sync().expect(500);
    expect(conversations.size).toBe(0);
    await sync().expect(200, { created: 1 });
    expect(messages.size).toBe(2);
  });
});
