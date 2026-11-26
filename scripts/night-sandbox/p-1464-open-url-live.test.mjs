import assert from 'node:assert/strict';
import test from 'node:test';
import { isSandboxOpen4xx, loginFailureDetails, roundAssertions } from './p-1464-open-url-live.mjs';

const sessions = 'https://pico.test/api/pico/v1/sandbox/sessions';

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
    targetHost: 'example.com',
    finalPane: { url: 'https://example.com/login', has_password_input: true },
    viewportVisible: true,
    reply: '平台异常：登录页正常打开。请在沙箱里输入账号密码。',
  }), {
    finished: 'PASS',
    sandbox_open_requests_settled: 'PASS',
    sandbox_open_4xx_at_most_one: 'PASS',
    sandbox_web_pane_shown: 'PASS',
    no_chrome_error: 'PASS',
    pane_stops_at_target_login: 'PASS',
    reply_stops_at_login: 'PASS',
  });
});

test('template round reports each observed failure and never passes an absent reply', () => {
  assert.deepEqual(roundAssertions('template', {
    finished: false,
    paneSeen: false,
    chromeErrorSeen: true,
    open4xx: 2,
    openRequestsSettled: false,
    reply: '平台异常，请稍后重试',
  }), {
    finished: 'FAIL',
    sandbox_open_requests_settled: 'FAIL',
    sandbox_open_4xx_at_most_one: 'FAIL',
    sandbox_web_pane_shown: 'FAIL',
    no_chrome_error: 'FAIL',
    pane_stops_at_target_login: 'FAIL',
    reply_stops_at_login: 'FAIL',
  });
  assert.equal(roundAssertions('template').reply_stops_at_login, 'FAIL');
  assert.equal(roundAssertions('template').sandbox_open_4xx_at_most_one, 'FAIL');
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
    '', 'ERR_NAME_NOT_RESOLVED', `${expected}。请稍后重试。`, `${expected}。不是你的问题写错。`,
  ]) {
    const wrongPane = roundAssertions('bad_address', { paneError: text, runCard: expected });
    assert.equal(wrongPane.pane_error_explains_dns, 'FAIL');
    assert.equal(wrongPane.run_card_explains_dns, 'PASS');
    const wrongCard = roundAssertions('bad_address', { paneError: expected, runCard: text });
    assert.equal(wrongCard.pane_error_explains_dns, 'PASS');
    assert.equal(wrongCard.run_card_explains_dns, 'FAIL');
  }
});
