/**
 * pico#1318: a steer during a pico turn goes straight into the running Pi turn.
 *
 * The pico model call is one long stream with no LibreChat tool batch, so the
 * stock PostToolBatch drain would only fire after the turn — the words would
 * wait and come back as a new message. While a pico call streams, its
 * AgentClient registers a forwarder here; the steer route pokes it after the
 * 202. Pico refuses (409) when the turn is not live: the steer stays queued and
 * the stock run-end path sends it as the next message. Same process only.
 */
const { logger } = require('@librechat/data-schemas');
const {
  picoBase,
  picoKey,
  membershipFromReq,
  conversationHeader,
} = require('~/server/services/Files/picoOfficeIngest');

/** @type {Map<string, () => Promise<void>>} */
const forwarders = new Map();

/** @returns {() => void} unregister */
function registerPicoSteer(streamId, forward) {
  if (!streamId) {
    return () => {};
  }
  forwarders.set(streamId, forward);
  return () => {
    if (forwarders.get(streamId) === forward) {
      forwarders.delete(streamId);
    }
  };
}

async function forwardPicoSteers(streamId) {
  const forward = forwarders.get(streamId);
  if (!forward) {
    return;
  }
  try {
    await forward();
  } catch (error) {
    logger.warn(`[picoSteer] forward failed for ${streamId}: ${error?.message || error}`);
  }
}

/** POST the steer to pico. True only when Pi took it into the running turn. */
async function postPicoSteer({ req, conversationId, text, fetchImpl = fetch }) {
  const convo = conversationHeader(conversationId);
  if (!convo || !text) {
    return false;
  }
  try {
    const res = await fetchImpl(`${picoBase()}/v1/chat/steer`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        Authorization: `Bearer ${picoKey()}`,
        'X-Pico-Membership-Id': membershipFromReq(req),
        'X-Conversation-Id': convo,
      },
      body: JSON.stringify({ text }),
      signal: AbortSignal.timeout(15000),
    });
    return res.status === 202;
  } catch (error) {
    logger.warn(`[picoSteer] pico steer unreachable: ${error?.message || error}`);
    return false;
  }
}

/**
 * Drain the run's steer queue and offer each steer to pico in order. Taken →
 * `apply` (inline steer part + on_steer_applied). The first refusal (or a steer
 * with files — pico steers are text only) and everything after it go back on
 * the queue in order (ahead of steers that arrived meanwhile) for the stock
 * run-end path.
 */
async function deliverQueuedSteers({ steering, streamId, jobCreatedAt, post, apply }) {
  const steers = await steering.drain(streamId, jobCreatedAt);
  const missed = [];
  for (const item of steers) {
    const took = missed.length === 0 && !(item.files?.length > 0) && (await post(item.text));
    if (took) {
      await apply(item);
    } else {
      missed.push(item);
    }
  }
  if (missed.length === 0) {
    return;
  }
  // The store only appends: steers sent while we were posting sit in the
  // queue already, so take them back out and put everything back in order.
  const later = await steering.drain(streamId, jobCreatedAt);
  for (const item of [...missed, ...later]) {
    const depth = await steering.enqueue(streamId, item);
    if (typeof depth !== 'number' || depth < 1) {
      logger.warn(`[picoSteer] steer not requeued for ${streamId}: ${depth}`);
    }
  }
}

module.exports = { registerPicoSteer, forwardPicoSteers, postPicoSteer, deliverQueuedSteers };
