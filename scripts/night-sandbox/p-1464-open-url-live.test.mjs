import assert from 'node:assert/strict';
import test from 'node:test';
import { isSandboxOpen4xx, roundAssertions } from './p-1464-open-url-live.mjs';

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
    reply: '请在沙箱里输入账号密码',
  }), {
    finished: 'PASS',
    sandbox_open_4xx_at_most_one: 'PASS',
    sandbox_web_pane_shown: 'PASS',
    no_chrome_error: 'PASS',
    reply_without_platform_error: 'PASS',
  });
});

test('template round reports each observed failure and never passes an absent reply', () => {
  assert.deepEqual(roundAssertions('template', {
    finished: false,
    paneSeen: false,
    chromeErrorSeen: true,
    open4xx: 2,
    reply: '平台异常，请稍后重试',
  }), {
    finished: 'FAIL',
    sandbox_open_4xx_at_most_one: 'FAIL',
    sandbox_web_pane_shown: 'FAIL',
    no_chrome_error: 'FAIL',
    reply_without_platform_error: 'FAIL',
  });
  assert.equal(roundAssertions('template').reply_without_platform_error, 'FAIL');
  assert.equal(roundAssertions('template').sandbox_open_4xx_at_most_one, 'FAIL');
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
