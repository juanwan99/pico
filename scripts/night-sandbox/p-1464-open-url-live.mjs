#!/usr/bin/env node
/**
 * Set ACCEPT_PASSWORD_DRILL_T701 (or EDU_ACCEPT_PASSWORD / EDU_SMOKE_PASSWORD).
 * Put the original template with the drill account line in a file outside the repo.
 * node scripts/night-sandbox/p-1464-open-url-live.mjs --template ~/.secrets/pico-1464.txt
 */
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { ROOT, goNewChat, loadPlaywright, loginWithEdu, sendPrompt, shot, writeJson } from './lib.mjs';

const STOP = '[data-testid="stop-generation-button"], [data-testid="task-stop-button"]';
const ROUND_TIMEOUT = 6 * 60 * 1000;

export function isSandboxOpen4xx(method, url, status) {
  return method === 'POST' && status >= 400 && status < 500 &&
    new URL(url).pathname.endsWith('/sandbox/sessions');
}

export function roundAssertions(round, {
  finished, paneSeen, chromeErrorSeen, open4xx, reply = '', paneError = '',
} = {}) {
  const assertions = {
    finished,
    sandbox_open_4xx_at_most_one: Number.isInteger(open4xx) && open4xx <= 1,
  };
  if (round === 'template') {
    assertions.sandbox_web_pane_shown = paneSeen;
    assertions.no_chrome_error = chromeErrorSeen === false;
    assertions.reply_without_platform_error = reply.trim() && !reply.includes('平台异常');
  } else {
    const dns = /解析|ERR_NAME_NOT_RESOLVED/i;
    assertions.dns_error_shown = dns.test(reply) || dns.test(paneError);
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

async function runRound(page, base, out, round, prompt, result) {
  await goNewChat(page, base);
  await page.evaluate(watchRound, STOP);
  let open4xx = 0;
  const paneMetadata = [];
  const onResponse = (response) => {
    if (isSandboxOpen4xx(response.request().method(), response.url(), response.status())) {
      open4xx++;
    }
    // The remote browser is rendered as an image. Its URL comes from session metadata.
    if (round === 'template' && response.ok() &&
      /\/sandbox\/sessions(?:\/sbox_[^/]+)?$/.test(new URL(response.url()).pathname)) {
      paneMetadata.push(response);
    }
  };
  page.on('response', onResponse);

  let finished = true;
  let observed;
  try {
    await sendPrompt(page, prompt);
    try {
      await page.waitForFunction(
        (stop) => window.picoOpenUrlWatch.watch.stopSeen && !document.querySelector(stop),
        STOP,
        { timeout: ROUND_TIMEOUT },
      );
    } catch (error) {
      if (error.name !== 'TimeoutError') throw error;
      finished = false;
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
      const paneError = Array.from(
        document.querySelectorAll('[data-testid="artifact-action-error"], [data-testid="sandbox-web-error"]'),
        (alert) => alert.innerText,
      ).join('\n');
      return { paneSeen: watch.paneSeen, chromeErrorSeen: watch.chromeErrorSeen, reply, paneError };
    });
  } finally {
    page.off('response', onResponse);
  }
  const metadata = await Promise.all(paneMetadata.map((response) => response.json()));
  observed.chromeErrorSeen ||= metadata.some(({ url }) => /^chrome-error:/i.test(url ?? ''));
  result.sandbox_open_4xx = open4xx;
  result.assertions = roundAssertions(round, { ...observed, finished, open4xx });

  // Capture the right rail alone so the user's template stays out of the first image.
  const file = path.join(out, `${round}.png`);
  const panel = page.getByTestId('result-panel');
  const shotTarget = round === 'template' ? panel : page;
  if (round !== 'template' || await panel.isVisible()) {
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
  const report = { card: 1464, verdict: 'FAIL', rounds: {} };
  for (const round of ['template', 'bad_address']) {
    report.rounds[round] = { assertions: roundAssertions(round), sandbox_open_4xx: null, screenshot: null };
  }
  let stage = 'read_template';
  try {
    if (!args.template) throw new Error('--template is required');
    const template = await readFile(args.template, 'utf8');
    stage = 'launch_browser';
    const { chromium } = loadPlaywright();
    const browser = await chromium.launch({
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    try {
      const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
      stage = 'login';
      const base = new URL(args.base).origin;
      report.base = base;
      await loginWithEdu(page, base, {
        eduBase: 'https://edu.weiyuji.cn',
        school: 'dd792255-de1c-4c6e-a750-5b15c7a213c1',
        loginName: 'drill.t701',
      });

      for (const [round, prompt] of [
        ['template', template],
        ['bad_address', '打开 https://no-such-host.invalid'],
      ]) {
        const result = report.rounds[round];
        try {
          await runRound(page, base, out, round, prompt, result);
        } catch (error) {
          // Playwright errors can include the prompt passed to fill().
          result.error = error.name;
        }
      }
      stage = 'close_browser';
    } finally {
      await browser.close();
    }
    const allPassed = Object.values(report.rounds).every((result) =>
      !result.error && result.screenshot && Object.values(result.assertions).every((status) => status === 'PASS'),
    );
    if (allPassed) report.verdict = 'PASS';
  } catch (error) {
    report.error = { stage, type: error.code || error.name };
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
