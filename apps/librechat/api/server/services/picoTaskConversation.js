const { v5: uuidv5 } = require('uuid');
const { Constants, EModelEndpoint } = require('librechat-data-provider');
const { getOpenAIModels } = require('@librechat/api');
const { logger } = require('~/config');
const { getConvo, saveConvo, saveMessage } = require('~/models');

const importsInProgress = new Map();
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

async function importConversation(read, user, task) {
  const {
    conversation_id: conversationId,
    latest_run: { id: runId },
  } = task;
  const ctx = { userId: user.id };
  if (await getConvo(ctx.userId, conversationId)) {
    return false;
  }

  const [{ run }, { events }, { tasks: conversationTasks }, [model]] = await Promise.all([
    read(`/v1/runs/${runId}`),
    read(`/v1/runs/${runId}/events`),
    read(`/v1/tasks?conversation_id=${encodeURIComponent(conversationId)}`),
    getOpenAIModels({ user: user.id, userObject: user }),
  ]);
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
  const saved = await saveConvo(ctx, { conversationId, title: task.title, endpoint, model });
  if (saved?.conversationId !== conversationId) {
    throw new Error(`Could not save mobile task conversation ${conversationId}`);
  }
  return true;
}

async function syncConversation(read, user, task) {
  const key = `${user.id}:${task.conversation_id}`;
  const pending = importsInProgress.get(key);
  if (pending) {
    await pending;
    return false;
  }

  const importing = importConversation(read, user, task);
  importsInProgress.set(key, importing);
  try {
    return await importing;
  } finally {
    importsInProgress.delete(key);
  }
}

function syncTaskConversations(picoBase, picoHeaders) {
  return async (req, res) => {
    const base = picoBase();
    const headers = picoHeaders(req);
    const read = (path) => readPico(base, headers, path);
    try {
      const { tasks } = await read('/v1/tasks');
      let created = 0;
      for (const task of tasks) {
        if (
          task.source === 'mobile' &&
          task.conversation_id &&
          task.latest_run?.status === 'succeeded' &&
          (await syncConversation(read, req.user, task))
        ) {
          created++;
        }
      }
      res.json({ created });
    } catch (error) {
      logger.error('[pico task conversations sync]', error);
      if (error instanceof PicoUpstreamError) {
        return res.status(502).json({ error: 'pico_upstream_unavailable' });
      }
      res.status(500).json({ error: 'pico_task_conversations_sync_failed' });
    }
  };
}

module.exports = syncTaskConversations;
