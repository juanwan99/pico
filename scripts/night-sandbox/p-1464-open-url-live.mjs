#!/usr/bin/env node
/**
 * Set ACCEPT_PASSWORD_DRILL_T701 (or EDU_ACCEPT_PASSWORD / EDU_SMOKE_PASSWORD).
 * Put the original template with the drill account line in a file outside the repo.
 * Node 22: node scripts/night-sandbox/p-1464-open-url-live.mjs --template ~/.secrets/pico-1464.txt
 */
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { detectOpenWebsiteIntent } from '../../apps/librechat/client/src/utils/picoOpenInPane.ts';
import { ROOT, goNewChat, loadPlaywright, loginWithEdu, sendPrompt, shot, writeJson } from './lib.mjs';

const STOP = '[data-testid="stop-generation-button"], [data-testid="task-stop-button"]';
const ROUND_TIMEOUT = 6 * 60 * 1000;
const ROUNDS = [
  'template', 'bad_address',
  'template_no_preopen_1', 'template_no_preopen_2', 'template_no_preopen_3', 'template_no_preopen_4',
];

export function templateTargetHost(template) {
  const url = template.match(/(?:打开|\bopen\b)\s*(?:(?:一下|下)\s*)?(https?:\/\/[^\s。！，、；：？]+)/i)?.[1];
  const target = url && detectOpenWebsiteIntent(url);
  return target ? new URL(target).hostname : null;
}

function isSandboxOpen(method, url) {
  return method === 'POST' && new URL(url).pathname.endsWith('/sandbox/sessions');
}

export function isSandboxOpen4xx(method, url, status) {
  return status >= 400 && status < 500 && isSandboxOpen(method, url);
}

function isPaneMetadata(request) {
  return request.method() === 'GET' &&
    /\/sandbox\/sessions\/sbox_[^/]+$/.test(new URL(request.url()).pathname);
}

async function readPicoJson(url, headers, signal) {
  const response = await fetch(url, { headers, signal });
  if (!response.ok) throw new Error(`Pico ledger HTTP ${response.status}`);
  return response.json();
}

export async function waitForAiBrowserOpens(base, conversationId, headers, signal) {
  const params = new URLSearchParams({ conversation_id: conversationId });
  for (;;) {
    const { tasks } = await readPicoJson(`${base}/api/pico/v1/tasks?${params}`, headers, signal);
    const run = tasks[0]?.latest_run;
    if (['succeeded', 'failed', 'cancelled'].includes(run?.status)) {
      const { events } = await readPicoJson(
        `${base}/api/pico/v1/runs/${run.id}/events`, headers, signal,
      );
      const opens = events.filter(({ payload }) => payload.tool === 'sandbox_browser_open');
      const calls = opens.filter(({ type }) => type === 'tool.call');
      const returned = new Set(opens.filter(({ type }) => type === 'tool.result')
        .map(({ payload }) => payload.call_id));
      if (calls.every(({ payload }) => returned.has(payload.call_id))) return calls.length;
    }
    await delay(250, undefined, { signal });
  }
}

export async function closeDesks(currentUrl, headers) {
  for (;;) {
    const current = await fetch(currentUrl, { headers });
    if (current.status === 404 && (await current.json()).detail?.code === 'sandbox.session_not_found') {
      return current.status;
    }
    if (!current.ok) throw new Error(`sandbox current HTTP ${current.status}`);
    const closed = await fetch(currentUrl, { method: 'DELETE', headers });
    if (!closed.ok) throw new Error(`sandbox cleanup HTTP ${closed.status}`);
  }
}

export function loginFailureDetails(error, ssoStatus) {
  if (/^Set ACCEPT_PASSWORD_[A-Z0-9_]+, EDU_ACCEPT_PASSWORD or EDU_SMOKE_PASSWORD\.$/.test(error.message)) {
    return { reason: 'missing_password' };
  }
  const http = /^(?:edu login|edu web-ticket|Pico edu session refresh) HTTP (\d{3})$/.exec(error.message);
  const status = http ? Number(http[1]) : ssoStatus;
  return status ? { reason: 'http_error', http_status: status } : {};
}

export function roundAssertions(round, {
  finished, paneSeen, chromeErrorSeen, open4xx, openRequestsSettled,
  browserOpens, aiBrowserOpens,
  targetHost, finalPane, viewportVisible, reply = '', paneError = '', runCard = '',
} = {}) {
  const assertions = {
    finished,
    sandbox_open_requests_settled: openRequestsSettled,
    sandbox_open_4xx_at_most_one: Number.isInteger(open4xx) && open4xx <= 1,
  };
  if (round !== 'bad_address') {
    assertions.no_browser_shortcut = browserOpens === 0;
    assertions.ai_opens_once = aiBrowserOpens === 1;
    assertions.sandbox_web_pane_shown = paneSeen;
    assertions.no_chrome_error = chromeErrorSeen === false;
    const url = URL.parse(finalPane?.url ?? '');
    assertions.pane_stops_at_target_login = viewportVisible && Boolean(targetHost) &&
      url?.hostname === targetHost && finalPane?.has_password_input === true;
    assertions.reply_stops_at_login = reply.includes('登录') &&
      !/未能打开|无法打开|打不开|无法访问|异常页/.test(reply);
  } else {
    const dns = /解析|ERR_NAME_NOT_RESOLVED/i;
    const showsDnsReason = (text) => text.includes('无法解析') && !/请稍后重试|不是你的问题写错/.test(text);
    assertions.dns_error_shown = dns.test(reply) || dns.test(paneError);
    assertions.pane_error_explains_dns = showsDnsReason(paneError);
    assertions.run_card_explains_dns = showsDnsReason(runCard);
  }
  return Object.fromEntries(Object.entries(assertions).map(([name, passed]) => [
    name, passed ? 'PASS' : 'FAIL',
  ]));
}

function watchRound(stopSelector) {
  const watch = { stopSeen: false, paneSeen: false, chromeErrorSeen: false };
  function sample() {
    watch.stopSeen ||= Boolean(document.querySelector(stopSelector));
    const pane = document.querySelector('[data-testid="sandbox-web-pane"]');
    watch.paneSeen ||= Boolean(pane?.checkVisibility({ visibilityProperty: true }));
    watch.chromeErrorSeen ||= /chrome-error/i.test(document.body.innerText);
  }
  const observer = new MutationObserver(sample);
  observer.observe(document.body, { subtree: true, childList: true, characterData: true });
  window.picoOpenUrlWatch = { watch, sample, observer };
  sample();
}

export async function runRound(page, base, out, round, prompt, result, targetHost, headers) {
  const isTemplate = round !== 'bad_address';
  result.assertions.sandbox_open_requests_settled = 'PASS';
  await goNewChat(page, base);
  if (round.startsWith('template_no_preopen_')) {
    result.sandbox_before_send_status = await closeDesks(
      `${base}/api/pico/v1/sandbox/sessions/current`, headers,
    );
  }
  await page.evaluate(watchRound, STOP);
  let open4xx = 0;
  let browserOpens = 0;
  let chatRequest;
  let onRequestsDrained;
  const pendingRequests = new Set();
  const metadataRequests = [];
  const onRequest = (request) => {
    const method = request.method();
    const url = request.url();
    if (isSandboxOpen(method, url)) {
      browserOpens++;
      pendingRequests.add(request);
    } else if (method === 'POST' && /^\/api\/agents\/chat(?:\/|$)/.test(new URL(url).pathname)) {
      chatRequest = request;
      pendingRequests.add(request);
    }
  };
  const onResponse = (response) => {
    if (isSandboxOpen4xx(response.request().method(), response.url(), response.status())) {
      open4xx++;
    }
  };
  const onRequestDone = (request) => {
    if (pendingRequests.delete(request) && !pendingRequests.size) onRequestsDrained?.();
  };
  const onRequestFinished = (request) => {
    if (isTemplate &&
      (isPaneMetadata(request) || isSandboxOpen(request.method(), request.url()))) {
      metadataRequests.push(request);
    }
    onRequestDone(request);
  };
  async function waitForRequests(deadline) {
    while (pendingRequests.size) {
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(
          () => reject(new Error('Sandbox round requests did not return')),
          Math.max(1, deadline - performance.now()),
        );
        onRequestsDrained = () => {
          clearTimeout(timeout);
          resolve();
        };
      });
    }
  }
  page.on('request', onRequest);
  page.on('response', onResponse);
  page.on('requestfinished', onRequestFinished);
  page.on('requestfailed', onRequestDone);

  let finished = false;
  let finalPane;
  let observed;
  let drainDeadline;
  let aiOpensSettled = false;
  const deadline = performance.now() + ROUND_TIMEOUT;
  const remaining = () => Math.max(1, deadline - performance.now());
  result.assertions.sandbox_open_requests_settled = 'FAIL';
  try {
    try {
      await sendPrompt(page, prompt);
      await page.waitForFunction(
        (stop) => window.picoOpenUrlWatch.watch.stopSeen && !document.querySelector(stop),
        STOP,
        { timeout: remaining() },
      );
      finished = true;

      const pane = page.getByTestId('sandbox-web-pane');
      if (isTemplate) {
        await pane.getByTestId('sandbox-web-viewport').waitFor({ timeout: remaining() });
        // Take a fresh metadata sample from the visible pane after the turn.
        const samplingStarted = Date.now();
        const request = await page.waitForEvent('requestfinished', {
          predicate: (request) => !pendingRequests.size && isPaneMetadata(request) &&
            request.timing().startTime >= samplingStarted,
          timeout: remaining(),
        });
        const response = await request.response();
        if (response.ok()) finalPane = await response.json();
      } else {
        const assistant = page.locator('.agent-turn').last();
        await assistant.locator('button[data-testid="pico-thinking-chain"][aria-expanded="false"]')
          .click({ timeout: remaining() });
        await page.getByTestId('artifact-action-error').waitFor({ timeout: remaining() });
        await assistant.getByTestId('pico-thinking-chain-body')
          .filter({ hasText: /解析|ERR_|页面打开失败|未能完成|工具没完成|请稍后重试|不是你的问题写错/ })
          .waitFor({ timeout: remaining() });
      }
    } catch (error) {
      if (error.name !== 'TimeoutError') throw error;
      result.error = error.name;
    } finally {
      // Let the run return its tool results before any cancellation can hide them.
      drainDeadline = performance.now() + ROUND_TIMEOUT;
      await waitForRequests(drainDeadline);
      const chatResponse = await chatRequest?.response();
      if (chatResponse?.ok()) {
        const { conversationId } = await chatResponse.json();
        const signal = AbortSignal.timeout(Math.max(1, Math.ceil(drainDeadline - performance.now())));
        result.ai_browser_opens = await waitForAiBrowserOpens(base, conversationId, headers, signal);
      }
      await waitForRequests(drainDeadline);
      aiOpensSettled = true;
    }

    observed = await page.evaluate(() => {
      const { watch, sample, observer } = window.picoOpenUrlWatch;
      sample();
      observer.disconnect();
      const assistant = Array.from(document.querySelectorAll('.agent-turn')).at(-1);
      const reply = Array.from(
        assistant?.querySelectorAll('.message-content') ?? [],
        (part) => part.innerText,
      ).join('\n');
      const paneError = document.querySelector('[data-testid="artifact-action-error"]')?.innerText;
      const runCard = assistant?.querySelector('[data-testid="pico-thinking-chain-body"]')?.innerText;
      const viewport = document.querySelector(
        '[data-testid="sandbox-web-pane"] [data-testid="sandbox-web-viewport"]',
      );
      return {
        paneSeen: watch.paneSeen,
        chromeErrorSeen: watch.chromeErrorSeen,
        viewportVisible: Boolean(viewport?.checkVisibility({ visibilityProperty: true })),
        reply,
        paneError,
        runCard,
      };
    });
  } finally {
    try {
      if (aiOpensSettled) {
        await waitForRequests(drainDeadline);
        result.assertions.sandbox_open_requests_settled = 'PASS';
      }
    } finally {
      page.off('request', onRequest);
      page.off('response', onResponse);
      page.off('requestfinished', onRequestFinished);
      page.off('requestfailed', onRequestDone);
    }
  }
  const metadata = await Promise.all(metadataRequests.map(async (request) => {
    const response = await request.response();
    return response.ok() ? response.json() : null;
  }));
  observed.chromeErrorSeen ||= metadata.some((meta) => /^chrome-error:/i.test(meta?.url ?? ''));
  result.sandbox_open_4xx = open4xx;
  result.browser_open_posts = browserOpens;
  result.assertions = roundAssertions(round, {
    ...observed,
    finished,
    open4xx,
    browserOpens,
    aiBrowserOpens: result.ai_browser_opens,
    openRequestsSettled: result.assertions.sandbox_open_requests_settled === 'PASS',
    targetHost,
    finalPane,
  });

  // Capture the right rail alone so the user's template stays out of the images.
  const file = path.join(out, `${round}.png`);
  const panel = page.getByTestId('result-panel');
  const shotTarget = isTemplate ? panel : page;
  if (!isTemplate || await panel.isVisible()) {
    result.screenshot = (await shot(shotTarget, file, { allowSmall: true })).filePath;
  }
}

async function main() {
  const { values: args } = parseArgs({
    options: {
      base: { type: 'string', default: 'https://pico.aivia.asia' },
      template: { type: 'string' },
      out: { type: 'string', default: path.join(ROOT, '.gpt-out', 'p-1464-open-url-live') },
    },
  });
  const out = path.resolve(args.out);
  const report = { card: 1464, verdict: 'FAIL', sessions_current_status: null, rounds: {} };
  for (const round of ROUNDS) {
    report.rounds[round] = { assertions: roundAssertions(round), sandbox_open_4xx: null, screenshot: null };
  }
  let stage = 'read_template';
  let ssoStatus;
  try {
    if (!args.template) throw new Error('--template is required');
    const template = await readFile(args.template, 'utf8');
    const targetHost = templateTargetHost(template);
    if (!targetHost) throw new Error('Template has no target website');
    const base = new URL(args.base).origin;
    const currentUrl = `${base}/api/pico/v1/sandbox/sessions/current`;
    stage = 'launch_browser';
    const { chromium } = loadPlaywright();
    const browser = await chromium.launch({
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    let headers;
    let opensSettled = true;
    try {
      const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
      stage = 'login';
      report.base = base;
      const onLoginResponse = (response) => {
        const url = new URL(response.url());
        if (url.origin === base && url.pathname === '/api/auth/edu-sso' && response.status() >= 400) {
          ssoStatus = response.status();
        }
      };
      page.on('response', onLoginResponse);
      try {
        const token = await loginWithEdu(page, base, {
          eduBase: 'https://edu.weiyuji.cn',
          school: 'dd792255-de1c-4c6e-a750-5b15c7a213c1',
          loginName: 'drill.t701',
        });
        headers = { authorization: `Bearer ${token}` };
      } finally {
        page.off('response', onLoginResponse);
      }

      stage = 'run_rounds';
      for (const round of ROUNDS) {
        const prompt = round === 'bad_address' ? '打开 https://no-such-host.invalid' : template;
        const result = report.rounds[round];
        try {
          await runRound(page, base, out, round, prompt, result, targetHost, headers);
        } catch (error) {
          // Playwright errors can include the prompt passed to fill().
          result.error = error.name;
        }
        opensSettled = result.assertions.sandbox_open_requests_settled === 'PASS';
        if (!opensSettled) break;
      }
      stage = 'close_browser';
    } finally {
      try {
        await browser.close();
      } finally {
        if (headers) {
          if (opensSettled) {
            try {
              report.sessions_current_status = await closeDesks(currentUrl, headers);
            } catch (error) {
              report.cleanup_error = error.message;
            }
          } else {
            report.cleanup_error = 'Sandbox session creation requests were not confirmed settled';
          }
        }
      }
    }
    const allPassed = Object.values(report.rounds).every((result) =>
      !result.error && result.screenshot && Object.values(result.assertions).every((status) => status === 'PASS'),
    );
    if (allPassed && report.sessions_current_status === 404) report.verdict = 'PASS';
  } catch (error) {
    report.error = {
      stage,
      type: error.code || error.name,
      ...(stage === 'login' ? loginFailureDetails(error, ssoStatus) : {}),
    };
  } finally {
    writeJson(path.join(out, 'REPORT.json'), report);
  }
  console.log(`${report.verdict} ${path.join(out, 'REPORT.json')}`);
  return report.verdict === 'PASS' ? 0 : 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().then((status) => { process.exitCode = status; }).catch((error) => {
    console.error(`FAIL #1464 (${error.code || error.name}). Use --template <file> [--base <url>] [--out <dir>].`);
    process.exitCode = 1;
  });
}
