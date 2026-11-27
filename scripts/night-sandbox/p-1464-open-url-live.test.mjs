import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import test from 'node:test';
import * as live from './p-1464-open-url-live.mjs';

const {
  classifyPaneRequest,
  closeDesks,
  isSandboxOpen4xx,
  loginFailureDetails,
  roundAssertions,
  runRound,
  templateTargetHost,
  waitForAiBrowserOpens,
} = live;

const sessions = 'https://pico.test/api/pico/v1/sandbox/sessions';
const currentUrl = `${sessions}/current`;
const headers = { authorization: 'Bearer test-teacher' };

test('reads the target host from the open instruction in a long template', () => {
  const template = '先参考 https://example.org。\n打开 https://example.com/home。未登录就停在登录页。';
  assert.equal(templateTargetHost(template), 'example.com');
});

test('classifies browser pane requests without keeping the URL or query', () => {
  const sessionId = 'sbox_123';
  const desk = `${sessions}/${sessionId}`;
  assert.deepEqual(classifyPaneRequest(`${desk}/stream?ack=1`), {
    session_id: sessionId, kind: 'stream',
  });
  for (const endpoint of ['png', 'screenshot']) {
    assert.deepEqual(classifyPaneRequest(`${desk}/${endpoint}`), {
      session_id: sessionId, kind: 'png',
    });
  }
  assert.deepEqual(classifyPaneRequest(`${currentUrl}/png`), {
    session_id: null, kind: 'current/png',
  });
  for (const url of [desk, `${desk}/input`, 'https://pico.test/api/files/report.png']) {
    assert.equal(classifyPaneRequest(url), null);
  }
});

test('counts AI opens from the conversation ledger without counting tool results', async (t) => {
  const responses = new Map([
    ['https://pico.test/api/pico/v1/tasks?conversation_id=chat_1', {
      tasks: [{ latest_run: { id: 'run_1', status: 'succeeded' } }],
    }],
    ['https://pico.test/api/pico/v1/runs/run_1/events', {
      events: [
        { type: 'tool.call', payload: { tool: 'sandbox_browser_open', call_id: 'open_1' } },
        { type: 'tool.result', payload: { tool: 'sandbox_browser_open', call_id: 'open_1', ok: true } },
        { type: 'tool.call', payload: { tool: 'sandbox_browser_act' } },
      ],
    }],
  ]);
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.deepEqual(init.headers, headers);
    assert.ok(responses.has(url));
    return Response.json(responses.get(url));
  });
  assert.equal(await waitForAiBrowserOpens('https://pico.test', 'chat_1', headers), 1);
});

test('a failed round drains the AI and browser opens before the desk is closed', {
  timeout: 3000,
}, async (t) => {
  const base = 'https://pico.test';
  const page = new EventEmitter();
  const failure = new Error('Pane observation failed');
  const round = { assertions: roundAssertions('template') };
  const browserRequest = { method: () => 'POST', url: () => sessions };
  const stream = {
    method: () => 'GET',
    url: () => `${sessions}/sbox_123/stream?ack=1`,
    timing: () => ({ responseStart: 123.4 }),
  };
  const png = {
    method: () => 'GET',
    url: () => `${currentUrl}/png`,
    failure: () => ({ errorText: 'net::ERR_FAILED' }),
  };
  t.signal.addEventListener('abort', () => page.emit('requestfinished', browserRequest), { once: true });
  const chatRequest = {
    method: () => 'POST',
    url: () => base + '/api/agents/chat/Pico',
    response: async () => ({
      ok: () => true,
      json: async () => ({ conversationId: 'chat_1' }),
    }),
  };
  const input = {
    count: async () => 1,
    first: () => input,
    waitFor: async () => {},
    click: async () => {},
    fill: async () => {},
  };
  const send = {
    count: async () => 1,
    first: () => send,
    click: async () => {
      page.emit('request', chatRequest);
      page.emit('requestfinished', chatRequest);
      page.emit('request', stream);
      page.emit('response', { request: () => stream, url: stream.url, status: () => 200 });
      page.emit('request', png);
      page.emit('requestfailed', png);
    },
  };
  Object.assign(page, {
    goto: async () => {},
    waitForTimeout: async () => {},
    evaluate: async () => ({ firstFrameMs: null }),
    locator: () => input,
    getByTestId: () => page,
    getByRole: (_role, { name }) => name.test('发送') ? send : { count: async () => 0 },
    waitForFunction: async () => { throw failure; },
  });
  let eventReads = 0;
  const methods = [];
  const call = { type: 'tool.call', payload: { tool: 'sandbox_browser_open', call_id: 'open_1' } };
  const result = { type: 'tool.result', payload: { ...call.payload, ok: false } };
  const earlierResult = { type: 'tool.result', payload: { ...call.payload, call_id: 'old_open' } };
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    if (url.endsWith('/tasks?conversation_id=chat_1')) {
      return Response.json({ tasks: [{ latest_run: { id: 'run_1', status: 'failed' } }] });
    }
    if (url.endsWith('/runs/run_1/events')) {
      eventReads++;
      assert.ok(eventReads <= 2);
      if (eventReads === 1) {
        page.emit('request', browserRequest);
        return Response.json({ events: [earlierResult, call] });
      }
      setImmediate(() => {
        methods.push('browser response');
        page.emit('requestfinished', browserRequest);
      });
      return Response.json({ events: [earlierResult, call, result] });
    }
    assert.equal(url, currentUrl);
    assert.equal(eventReads, 2);
    methods.push(init.method ?? 'GET');
    return methods.length < 4
      ? Response.json({ ok: true })
      : Response.json({ detail: { code: 'sandbox.session_not_found' } }, { status: 404 });
  });
  await assert.rejects(
    runRound(page, base, '', 'template', '打开 https://example.com', round, 'example.com', headers),
    failure,
  );
  assert.equal(round.ai_browser_opens, 1);
  assert.equal(round.assertions.sandbox_open_requests_settled, 'PASS');
  assert.equal(round.first_frame_ms, null);
  assert.equal(round.pane_requests.length, 2);
  const [streamEvidence, pngEvidence] = round.pane_requests;
  assert.deepEqual(streamEvidence, {
    session_id: 'sbox_123', kind: 'stream', status: 200, failure: null, response_headers_ms: 123,
  });
  assert.deepEqual(pngEvidence, {
    session_id: null, kind: 'current/png', status: null, failure: 'net::ERR_FAILED', response_headers_ms: null,
  });
  assert.equal(await closeDesks(currentUrl, headers), 404);
  assert.deepEqual(methods, ['browser response', 'GET', 'DELETE', 'GET']);
});

test('cleans up every current desk and confirms the final GET returns 404', async (t) => {
  let desks = 2;
  const methods = [];
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(url, currentUrl);
    assert.deepEqual(init.headers, headers);
    const method = init.method ?? 'GET';
    methods.push(method);
    if (method === 'DELETE') desks--;
    return method === 'GET' && desks === 0
      ? Response.json({ detail: { code: 'sandbox.session_not_found' } }, { status: 404 })
      : Response.json({ ok: true });
  });
  assert.equal(await closeDesks(currentUrl, headers), 404);
  assert.deepEqual(methods, ['GET', 'DELETE', 'GET', 'DELETE', 'GET']);
  methods.length = 0;
  assert.equal(await closeDesks(currentUrl, headers), 404);
  assert.deepEqual(methods, ['GET']);
});

test('cleanup reports unexpected GET and failed DELETE', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => Response.json({}, { status: 404 }));
  await assert.rejects(closeDesks(currentUrl, headers), /sandbox current HTTP 404/);
  fetch.mock.mockImplementation(async (_url, init) => init.method === 'DELETE'
    ? Response.json({}, { status: 503 })
    : Response.json({ ok: true }));
  await assert.rejects(closeDesks(currentUrl, headers), /sandbox cleanup HTTP 503/);
});

test('counts only 4xx responses to sandbox session creation', () => {
  const responses = [
    ['POST', sessions, 400],
    ['POST', `${sessions}?source=chat`, 499],
    ['POST', sessions, 399],
    ['POST', sessions, 500],
    ['GET', sessions, 404],
    ['POST', `${sessions}/sbox_123/input`, 400],
    ['POST', 'https://pico.test/api/chat', 400],
  ];
  assert.equal(responses.filter((response) => isSandboxOpen4xx(...response)).length, 2);
});

test('template round passes with a pane, a completed reply, and no browser error', () => {
  assert.deepEqual(roundAssertions('template', {
    finished: true,
    paneSeen: true,
    chromeErrorSeen: false,
    open4xx: 0,
    openRequestsSettled: true,
    browserOpens: 0,
    aiBrowserOpens: 1,
    targetHost: 'example.com',
    finalPane: { url: 'https://example.com/login', has_password_input: true },
    viewportVisible: true,
    reply: '平台异常：登录页正常打开。请在沙箱里输入账号密码。',
  }), {
    finished: 'PASS',
    sandbox_open_requests_settled: 'PASS',
    sandbox_open_4xx_at_most_one: 'PASS',
    no_browser_shortcut: 'PASS',
    ai_opens_once: 'PASS',
    sandbox_web_pane_shown: 'PASS',
    no_chrome_error: 'PASS',
    pane_stops_at_target_login: 'PASS',
    reply_stops_at_login: 'PASS',
  });
});

test('same-chat reopen requires both a visible viewport and a successful stream for a different desk', () => {
  const round = 'same_chat_close_reopen';
  const oldSessionId = 'sbox_old';
  const newStream = { session_id: 'sbox_new', kind: 'stream', status: 200 };
  const observed = {
    finished: true, openRequestsSettled: true, open4xx: 0, browserOpens: 0, aiBrowserOpens: 1,
    paneSeen: true, chromeErrorSeen: false, oldSessionId, viewportVisible: true,
    viewportSessionId: newStream.session_id,
    paneRequests: [newStream], targetHost: 'example.com',
    finalPane: { url: 'https://example.com/home', has_password_input: false },
    reply: '页面已经打开。',
  };
  const assertions = roundAssertions(round, observed);
  assert.equal(assertions.new_stream_after_close, 'PASS');
  assert.ok(Object.values(assertions).every((status) => status === 'PASS'));
  for (const override of [
    { oldSessionId: undefined },
    { viewportVisible: false },
    { viewportSessionId: oldSessionId },
    { viewportSessionId: 'sbox_other' },
    { paneRequests: [] },
    { paneRequests: [{ ...newStream, session_id: oldSessionId }] },
    { paneRequests: [{ ...newStream, status: 404 }] },
    { paneRequests: [{ ...newStream, status: null }] },
    { paneRequests: [{ ...newStream, kind: 'png' }] },
  ]) {
    assert.equal(roundAssertions(round, { ...observed, ...override }).new_stream_after_close, 'FAIL');
  }
});

test('template round reports each observed failure and never passes an absent reply', () => {
  assert.deepEqual(roundAssertions('template', {
    finished: false,
    paneSeen: false,
    chromeErrorSeen: true,
    open4xx: 2,
    openRequestsSettled: false,
    browserOpens: 2,
    aiBrowserOpens: 0,
    reply: '平台异常，请稍后重试',
  }), {
    finished: 'FAIL',
    sandbox_open_requests_settled: 'FAIL',
    sandbox_open_4xx_at_most_one: 'FAIL',
    no_browser_shortcut: 'FAIL',
    ai_opens_once: 'FAIL',
    sandbox_web_pane_shown: 'FAIL',
    no_chrome_error: 'FAIL',
    pane_stops_at_target_login: 'FAIL',
    reply_stops_at_login: 'FAIL',
  });
  assert.equal(roundAssertions('template').reply_stops_at_login, 'FAIL');
  assert.equal(roundAssertions('template').sandbox_open_4xx_at_most_one, 'FAIL');
});

test('template rejects a successful shortcut POST or repeated AI opens', () => {
  const assertions = roundAssertions('template', { open4xx: 0, browserOpens: 1, aiBrowserOpens: 2 });
  assert.equal(assertions.sandbox_open_4xx_at_most_one, 'PASS');
  assert.equal(assertions.no_browser_shortcut, 'FAIL');
  assert.equal(assertions.ai_opens_once, 'FAIL');
  assert.equal(roundAssertions('template').no_browser_shortcut, 'FAIL');
  assert.equal(roundAssertions('template').ai_opens_once, 'FAIL');
});

test('template round rejects replies that say the login page failed', () => {
  for (const reply of [
    '登录页打不开', '无法访问登录页', '登录时到了异常页', '未能打开登录页', '无法打开登录页',
  ]) {
    assert.equal(roundAssertions('template', { reply }).reply_stops_at_login, 'FAIL');
  }
});

test('template round requires the final pane to show a password field on the target host', () => {
  for (const finalPane of [
    undefined,
    { url: 'https://other.example.com/login', has_password_input: true },
    { url: 'https://example.com/home', has_password_input: false },
  ]) {
    const assertions = roundAssertions('template', {
      targetHost: 'example.com', finalPane, viewportVisible: true,
    });
    assert.equal(assertions.pane_stops_at_target_login, 'FAIL');
  }
  assert.equal(roundAssertions('template', {
    targetHost: 'example.com',
    finalPane: { url: 'https://example.com/login', has_password_input: true },
    viewportVisible: false,
  }).pane_stops_at_target_login, 'FAIL');
});

test('reports missing drill credentials or login HTTP status without raw errors', () => {
  assert.deepEqual(loginFailureDetails(new Error(
    'Set ACCEPT_PASSWORD_DRILL_T701, EDU_ACCEPT_PASSWORD or EDU_SMOKE_PASSWORD.',
  )), { reason: 'missing_password' });
  for (const service of ['edu login', 'edu web-ticket', 'Pico edu session refresh']) {
    assert.deepEqual(loginFailureDetails(new Error(`${service} HTTP 401`)), {
      reason: 'http_error', http_status: 401,
    });
  }
  assert.deepEqual(loginFailureDetails(new Error('Pico edu SSO did not reach /c/new.'), 503), {
    reason: 'http_error', http_status: 503,
  });
  assert.deepEqual(loginFailureDetails(new Error('private login context')), {});
});

test('bad address round accepts the DNS reason from either the assistant or the pane', () => {
  const { dns_error_shown, sandbox_open_4xx_at_most_one } = roundAssertions('bad_address', {
    finished: true, open4xx: 1, reply: '域名解析不到',
  });
  assert.equal(dns_error_shown, 'PASS');
  assert.equal(sandbox_open_4xx_at_most_one, 'PASS');
  assert.equal(roundAssertions('bad_address', {
    paneError: 'ERR_NAME_NOT_RESOLVED',
  }).dns_error_shown, 'PASS');
  assert.equal(roundAssertions('bad_address', {
    reply: '平台异常', paneError: '打开网页失败，请稍后重试',
  }).dns_error_shown, 'FAIL');
  assert.equal(roundAssertions('bad_address', { open4xx: 2 }).sandbox_open_4xx_at_most_one, 'FAIL');
});

test('bad address round requires the DNS explanation independently in the pane and run card', () => {
  const expected = '页面打开失败：无法解析域名（ERR_NAME_NOT_RESOLVED）';
  const assertions = roundAssertions('bad_address', { paneError: expected, runCard: expected });
  assert.equal(assertions.pane_error_explains_dns, 'PASS');
  assert.equal(assertions.run_card_explains_dns, 'PASS');

  for (const text of [
    '', 'ERR_NAME_NOT_RESOLVED', '正在解析域名', `${expected}。请稍后重试。`,
    `${expected}。不是你的问题写错。`,
  ]) {
    const wrongPane = roundAssertions('bad_address', { paneError: text, runCard: expected });
    assert.equal(wrongPane.pane_error_explains_dns, 'FAIL');
    assert.equal(wrongPane.run_card_explains_dns, 'PASS');
    const wrongCard = roundAssertions('bad_address', { paneError: expected, runCard: text });
    assert.equal(wrongCard.pane_error_explains_dns, 'PASS');
    assert.equal(wrongCard.run_card_explains_dns, 'FAIL');
  }
});
