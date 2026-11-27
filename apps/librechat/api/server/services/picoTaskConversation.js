const mongoose = require('mongoose');
const { v5: uuidv5 } = require('uuid');
const { Constants, EModelEndpoint } = require('librechat-data-provider');
const { getOpenAIModels } = require('@librechat/api');
const { logger } = require('~/config');
const { getConvo, saveMessage } = require('~/models');

const endpoint = EModelEndpoint.openAI;

class PicoUpstreamError extends Error {}

async function readPico(base, headers, path) {
  try {
    const response = await fetch(`${base}${path}`, { headers });
    if (!response.ok) {
      throw new Error(`Pico returned HTTP ${response.status}`);
    }
    return await response.json();
  } catch (cause) {
    throw new PicoUpstreamError(`Pico task sync could not read ${path}`, { cause });
  }
}

async function importConversation(read, user, task, preferredModel) {
  const conversationId = task.conversation_id;
  const ctx = { userId: user.id };
  const batches = mongoose.connection.collection('pico_task_conversation_imports');
  const filter = { _id: JSON.stringify([user.id, conversationId]) };
  // A retry resumes the same run's message upserts even if Pico has run the task again.
  const { runId, completed } = await batches.findOneAndUpdate(
    filter,
    { $setOnInsert: { runId: task.latest_run.id } },
    { upsert: true, returnDocument: 'after' },
  );
  if (completed) {
    return false;
  }
  const complete = () => batches.updateOne(filter, { $set: { completed: true } });
  if (await getConvo(ctx.userId, conversationId)) {
    await complete();
    return false;
  }

  const [{ run }, { events }, { tasks: conversationTasks }, models] = await Promise.all([
    read(`/v1/runs/${runId}`),
    read(`/v1/runs/${runId}/events`),
    read(`/v1/tasks?conversation_id=${encodeURIComponent(conversationId)}`),
    getOpenAIModels({ user: user.id, userObject: user }),
  ]);
  const model = models.includes(preferredModel) ? preferredModel : models[0];
  const finalText = events.findLast((event) => event.type === 'message.final')?.payload.text;
  if (typeof finalText !== 'string') {
    throw new PicoUpstreamError(`Pico run ${runId} is missing its final answer`);
  }
  const photoCount = conversationTasks.filter(
    (row) => row.latest_run === null && row.title.startsWith('edu-read · '),
  ).length;
  const text = photoCount ? `${run.prompt}\n\n（手机拍了 ${photoCount} 张照片）` : run.prompt;
  const userMessageId = uuidv5(`${runId}:user`, uuidv5.URL);

  // Write the messages first so the sidebar only sees a complete conversation.
  const userMessage = await saveMessage(ctx, {
    conversationId,
    endpoint,
    messageId: userMessageId,
    parentMessageId: Constants.NO_PARENT,
    isCreatedByUser: true,
    sender: 'User',
    text,
  });
  const assistantMessage = await saveMessage(ctx, {
    conversationId,
    endpoint,
    model,
    messageId: uuidv5(`${runId}:assistant`, uuidv5.URL),
    parentMessageId: userMessageId,
    isCreatedByUser: false,
    sender: model,
    text: finalText,
  });
  if (!userMessage || !assistantMessage) {
    throw new Error(`Could not save messages for mobile task conversation ${conversationId}`);
  }
  // Match the entire unique index. saveConvo omits tenantId for accounts without a tenant.
  const saved = await mongoose.models.Conversation.updateOne(
    { conversationId, user: ctx.userId, tenantId: user.tenantId ?? null },
    {
      $setOnInsert: {
        title: task.title,
        endpoint,
        model,
        messages: [userMessage._id, assistantMessage._id],
        createdAt: new Date(`${task.created_at}Z`),
        updatedAt: new Date(`${run.ended_at}Z`),
      },
    },
    { upsert: true, timestamps: false },
  );
  await complete();
  return saved.upsertedCount === 1;
}

function syncTaskConversations(picoBase, picoHeaders) {
  return async (req, res) => {
    const base = picoBase();
    const headers = picoHeaders(req);
    const read = (path) => readPico(base, headers, path);
    let created = 0;
    try {
      const { tasks } = await read('/v1/tasks');
      for (const task of tasks) {
        if (
          task.source === 'mobile' &&
          task.conversation_id &&
          task.latest_run?.status === 'succeeded' &&
          (await importConversation(read, req.user, task, req.body?.model))
        ) {
          created++;
        }
      }
      res.json({ created });
    } catch (error) {
      logger.error('[pico task conversations sync]', error);
      const upstream = error instanceof PicoUpstreamError;
      res.status(upstream ? 502 : 500).json({
        error: upstream ? 'pico_upstream_unavailable' : 'pico_task_conversations_sync_failed',
        created,
      });
    }
  };
}

module.exports = syncTaskConversations;
