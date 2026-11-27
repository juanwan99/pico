const express = require('express');
const request = require('supertest');
const { EModelEndpoint, Constants } = require('librechat-data-provider');
const { getOpenAIModels } = require('@librechat/api');
const mongoose = require('mongoose');
const { version } = require('uuid');
const { getConvo, saveMessage } = require('~/models');

jest.mock('@librechat/api', () => ({ getOpenAIModels: jest.fn() }), { virtual: true });

jest.mock('~/models', () => ({
  getConvo: jest.fn(),
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
const retryId = '12345678-1234-4234-9234-123456789eee';
const olderConversationId = '12345678-1234-4234-9234-123456789ccc';
const olderRunId = '12345678-1234-4234-9234-123456789ddd';
const mobile = {
  id: 'task-1',
  source: 'mobile',
  conversation_id: conversationId,
  title: '备课记录',
  created_at: '2026-11-27T08:15:00',
  latest_run: { id: runId, status: 'succeeded' },
};
const olderMobile = {
  ...mobile,
  id: 'task-0',
  conversation_id: olderConversationId,
  created_at: '2026-11-26T08:15:00',
  latest_run: { id: olderRunId, status: 'succeeded' },
};
const model = 'workbench-default-model';

describe('Pico mobile task conversations', () => {
  const app = express();
  app.use(express.json());
  app.use('/api/pico', router);
  const sync = (body = {}) => request(app).post('/api/pico/task-conversations/sync').send(body);
  let conversations;
  const updateConvo = jest.fn();
  let messages;
  const oldFetch = global.fetch;

  function core({ tasks = [mobile], uploads = [], olderEventsAvailable = true } = {}) {
    global.fetch = jest.fn(async (url) => {
      const { pathname, search } = new URL(url);
      const data = {
        '/v1/tasks': { tasks },
        [`/v1/tasks?conversation_id=${conversationId}`]: { tasks: [mobile, ...uploads] },
        [`/v1/tasks?conversation_id=${olderConversationId}`]: { tasks: [olderMobile] },
        [`/v1/runs/${runId}`]: {
          run: { id: runId, prompt: '整理备课记录', ended_at: '2026-11-27T08:30:00' },
        },
        [`/v1/runs/${retryId}`]: {
          run: { id: retryId, prompt: '整理备课记录', ended_at: '2026-11-27T08:45:00' },
        },
        [`/v1/runs/${olderRunId}`]: {
          run: { id: olderRunId, prompt: '整理昨天的记录', ended_at: '2026-11-26T08:30:00' },
        },
        [`/v1/runs/${olderRunId}/events`]: olderEventsAvailable
          ? { events: [{ type: 'message.final', payload: { text: '昨天的记录已整理。' } }] }
          : undefined,
        [`/v1/runs/${retryId}/events`]: {
          events: [{ type: 'message.final', payload: { text: '重跑结果' } }],
        },
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
    getOpenAIModels.mockResolvedValue([model, 'other-model']);
    conversations = new Map();
    mongoose.models.Conversation = { updateOne: updateConvo };
    messages = new Map();
    const batches = new Map();
    jest.spyOn(mongoose.connection, 'collection').mockReturnValue({
      findOneAndUpdate: async ({ _id }, { $setOnInsert }) => {
        if (!batches.has(_id)) {
          batches.set(_id, $setOnInsert);
        }
        return { ...batches.get(_id) };
      },
      updateOne: async ({ _id }, { $set }) => Object.assign(batches.get(_id), $set),
    });
    getConvo.mockImplementation(async (user, id) => conversations.get(`${user}:${id}`));
    saveMessage.mockImplementation(async ({ userId }, message) => {
      const saved = { ...message, _id: message.messageId };
      messages.set(`${userId}:${message.messageId}`, saved);
      return saved;
    });
    updateConvo.mockImplementation(async (key, { $setOnInsert }) => {
      expect(key).toEqual({
        conversationId: expect.any(String),
        user: 'teacher-mongo',
        tenantId: null,
      });
      const id = `${key.user}:${key.conversationId}`;
      if (conversations.has(id)) {
        return { upsertedCount: 0 };
      }
      conversations.set(id, { ...key, ...$setOnInsert });
      return { upsertedCount: 1 };
    });
  });

  afterEach(() => {
    global.fetch = oldFetch;
    delete mongoose.models.Conversation;
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
    expect(convo.messages).toEqual([user._id, assistant._id]);
    await sync().expect(200, { created: 0 });
    expect(updateConvo).toHaveBeenCalledTimes(1);
    expect(saveMessage).toHaveBeenCalledTimes(2);

    conversations.clear();
    messages.clear();
    await sync().expect(200, { created: 0 });
    expect(messages.size).toBe(0);
  });

  it('creates only one copy across two simultaneous requests and keeps another user separate', async () => {
    conversations.set(`other-user:${conversationId}`, { title: '别人的对话' });
    core();
    let bothWriting;
    const barrier = new Promise((resolve) => {
      bothWriting = resolve;
    });
    let writes = 0;
    const arrive = async () => {
      if (++writes === 2) {
        bothWriting();
      }
      await barrier;
    };
    const upsert = updateConvo.getMockImplementation();
    updateConvo.mockImplementation(async (...args) => {
      await arrive();
      return upsert(...args);
    });

    await Promise.all([sync().expect(200), sync().expect(200)]);
    expect(updateConvo).toHaveBeenCalledTimes(2);
    expect(updateConvo.mock.calls[0][2]).toEqual({ upsert: true, timestamps: false });
    expect(conversations.size).toBe(2);
    expect(conversations.has(`teacher-mongo:${conversationId}`)).toBe(true);
    expect(messages.size).toBe(2);
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
    expect(updateConvo).not.toHaveBeenCalled();
    expect(saveMessage).not.toHaveBeenCalled();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(conversations.get(`teacher-mongo:${conversationId}`).title).toBe('电脑改过的标题');
  });

  it('creates nothing when the membership has no tasks', async () => {
    core({ tasks: [] });
    await sync().expect(200, { created: 0 });
    expect(updateConvo).not.toHaveBeenCalled();
    expect(saveMessage).not.toHaveBeenCalled();
  });

  it('surfaces an unreachable core as a proxy failure', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('ECONNREFUSED'));
    await sync().expect(502, { error: 'pico_upstream_unavailable', created: 0 });
    expect(updateConvo).not.toHaveBeenCalled();
  });

  it('reports conversations already created when a later run cannot be read', async () => {
    core({ tasks: [mobile, olderMobile], olderEventsAvailable: false });
    await sync().expect(502, { error: 'pico_upstream_unavailable', created: 1 });
    expect(conversations.has(`teacher-mongo:${conversationId}`)).toBe(true);
    expect(conversations.size).toBe(1);
    core({ tasks: [mobile, olderMobile] });
    await sync().expect(200, { created: 1 });
    expect(conversations.size).toBe(2);
    expect(messages.size).toBe(4);
  });

  it('preserves the ledger UTC dates for conversations imported together', async () => {
    core({ tasks: [mobile, olderMobile] });
    await sync().expect(200, { created: 2 });
    expect(conversations.get(`teacher-mongo:${conversationId}`)).toMatchObject({
      createdAt: new Date('2026-11-27T08:15:00Z'),
      updatedAt: new Date('2026-11-27T08:30:00Z'),
    });
    expect(conversations.get(`teacher-mongo:${olderConversationId}`)).toMatchObject({
      createdAt: new Date('2026-11-26T08:15:00Z'),
      updatedAt: new Date('2026-11-26T08:30:00Z'),
    });
  });

  it('resumes the original import when a newer run succeeds after a failed save', async () => {
    core();
    updateConvo.mockRejectedValueOnce(new Error('Error saving conversation'));
    await sync().expect(500);
    expect(conversations.size).toBe(0);
    core({ tasks: [{ ...mobile, latest_run: { id: retryId, status: 'succeeded' } }] });
    await sync().expect(200, { created: 1 });
    expect(messages.size).toBe(2);
    expect(Array.from(messages.values()).at(-1).text).toBe('备课记录已整理。');
  });

  it('uses the configured model selected for new desktop conversations', async () => {
    core();
    await sync({ model: 'other-model' }).expect(200, { created: 1 });
    expect(conversations.get(`teacher-mongo:${conversationId}`).model).toBe('other-model');
  });
});
