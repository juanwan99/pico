import assert from 'node:assert/strict';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import { measurePane, measureRound, watchPane } from './p-sandbox-latency.mjs';

const currentUrl = 'http://pico.test/api/pico/v1/sandbox/sessions/current';
const headers = { authorization: 'Bearer test-teacher' };

function mockRound(t, { desks = 0, waitingAsk = false, deleteStatus = 200 } = {}) {
  const calls = [];
  const stop = {
    async evaluateAll(click) {
      click(waitingAsk ? [{ click: () => calls.push('stop') }] : []);
    },
    async waitFor(options) {
      assert.deepEqual(options, { state: 'detached', timeout: 30000 });
      calls.push('stop detached');
      waitingAsk = false;
    },
  };
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(url, currentUrl);
    assert.deepEqual(init.headers, headers);
    const method = init.method ?? 'GET';
    calls.push(method);
    if (method === 'GET') {
      return desks ? Response.json({ ok: true }) : Response.json({
        detail: { code: 'sandbox.session_not_found' },
      }, { status: 404 });
    }
    assert.equal(method, 'DELETE');
    assert.equal(waitingAsk, false);
    if (deleteStatus === 200) desks--;
    return Response.json({}, { status: deleteStatus });
  });
  return {
    calls,
    openDesks(count) {
      calls.push('measure');
      desks = count;
    },
    options: {
      currentUrl,
      headers,
      page: {
        getByTestId(id) {
          assert.equal(id, 'task-stop-button');
          return stop;
        },
      },
      prepare: async () => calls.push('new chat'),
      onRetry: (attempt) => calls.push(`retry ${attempt}`),
    },
  };
}

async function fixtureFailure({ timeout } = {}) {
  const window = {
    fetch: async () => Response.json({ detail: { code: 'sandbox.fetch_failed' } }, { status: 400 }),
  };
  runInNewContext(`(${watchPane.toString()})({})`, {
    window,
    document: { addEventListener() {}, createElement: () => ({ getContext() {} }) },
    MutationObserver: class { observe() {} },
  });
  if (!timeout) {
    const response = await window.fetch('/api/pico/v1/sandbox/sessions', { method: 'POST' });
    assert.equal((await response.json()).detail.code, 'sandbox.fetch_failed');
  }
  await measurePane({
    locator() {},
    async waitForFunction(predicate, _arg, options) {
      assert.equal(options.timeout, 60000);
      if (timeout) throw timeout;
      const result = runInNewContext(`(${predicate.toString()})()`, { window });
      assert.equal(result, 'fetch_failed');
      return { jsonValue: async () => result };
    },
  }, null, {});
}

test('round deletes both desks through current until GET returns 404', async (t) => {
  const { calls, openDesks, options } = mockRound(t);
  const measured = await measureRound({ ...options, measure: async () => {
    openDesks(2);
    return 'result';
  } });
  assert.equal(measured, 'result');
  assert.deepEqual(calls, [
    'GET', 'new chat', 'measure', 'stop detached', 'GET', 'DELETE', 'GET', 'DELETE', 'GET',
  ]);
});

test('round stops the task waiting for ask_user before deleting desks', async (t) => {
  const { calls, openDesks, options } = mockRound(t, { waitingAsk: true });
  await measureRound({ ...options, measure: async () => openDesks(1) });
  assert.deepEqual(calls, [
    'GET', 'new chat', 'measure', 'stop', 'stop detached', 'GET', 'DELETE', 'GET',
  ]);
});

test('open failure and missing fixture retry after cleanup, at most three attempts', async (t) => {
  const { calls, openDesks, options } = mockRound(t);
  const timeout = Object.assign(new Error('fixture wait expired'), { name: 'TimeoutError' });
  let attempts = 0;
  await assert.rejects(measureRound({ ...options, measure: async () => {
    openDesks(1);
    attempts++;
    await fixtureFailure(attempts === 2 ? { timeout } : undefined);
  } }), /sandbox\.fetch_failed/);
  const attempt = ['GET', 'new chat', 'measure', 'stop detached', 'GET', 'DELETE', 'GET'];
  assert.deepEqual(calls, [...attempt, 'retry 1', ...attempt, 'retry 2', ...attempt]);
});

test('cleanup failure reports its own error and preserves the original measurement error', async (t) => {
  const { calls, openDesks, options } = mockRound(t, { deleteStatus: 503 });
  const log = t.mock.method(console, 'error', () => {});
  const timeout = Object.assign(new Error('fixture wait expired'), { name: 'TimeoutError' });
  const original = await fixtureFailure({ timeout }).catch((error) => error);
  assert.equal(original.cause, timeout);
  await assert.rejects(measureRound({ ...options, measure: async () => {
    openDesks(1);
    throw original;
  } }), (error) => error === original);
  assert.deepEqual(calls, ['GET', 'new chat', 'measure', 'stop detached', 'GET', 'DELETE']);
  assert.equal(log.mock.callCount(), 1);
  assert.match(log.mock.calls[0].arguments[1].message, /sandbox cleanup HTTP 503/);
});

test('preflight leaves an existing desk alone', async (t) => {
  const { calls, options } = mockRound(t, { desks: 1 });
  await assert.rejects(measureRound(options), /already has an open sandbox desk/);
  assert.deepEqual(calls, ['GET']);
});

test('cleanup fails if a sixth desk remains', async (t) => {
  const { calls, openDesks, options } = mockRound(t);
  await assert.rejects(measureRound({ ...options, measure: async () => openDesks(6) }), /after 5 deletes/);
  assert.equal(calls.filter((call) => call === 'DELETE').length, 5);
  assert.equal(calls.at(-1), 'GET');
});
