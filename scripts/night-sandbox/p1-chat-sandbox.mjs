#!/usr/bin/env node
/**
 * P1 teacher script — S1 site / S2 Writer / S3 no delivery strip / S4 390.
 *
 * Usage:
 *   set -a; . ~/.secrets/pico-r4r6-evidence.env; set +a
 *   node scripts/night-sandbox/p1-chat-sandbox.mjs --base https://pico.aivia.asia
 *
 * Fail = BLOCKED P1. Do not open P2.
 */
import fs from 'node:fs';
import path from 'node:path';
import {
  ROOT,
  loadPlaywright,
  loadEvidenceEnv,
  emailPass,
  fetchTip,
  shot,
  login,
  goNewChat,
  sendPrompt,
  messageInput,
  saveViewportPng,
  writeJson,
} from './lib.mjs';

loadEvidenceEnv();

function parseArgs(argv) {
  const out = {
    base: process.env.PICO_PUBLIC_BASE || process.env.PICO_LOCAL_BASE || 'https://pico.aivia.asia',
    out: process.env.PICO_NIGHT_OUT || path.join(ROOT, 'docs/evidence/pack-night-sandbox/p1'),
    headed: process.env.PICO_VISUAL_HEADED === '1',
    timeoutMs: Number(process.env.PICO_VISUAL_TIMEOUT_MS || 120000),
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--base') out.base = next();
    else if (a === '--out') out.out = next();
    else if (a === '--headed') out.headed = true;
    else throw new Error(`unknown arg: ${a}`);
  }
  return out;
}

function fail(code, reason) {
  const err = new Error(reason);
  err.code = code;
  throw err;
}

async function pageText(page) {
  return page.locator('body').innerText().catch(() => '');
}

async function waitSandboxReady(page, pred, timeoutMs) {
  const start = Date.now();
  let last = '';
  while (Date.now() - start < timeoutMs) {
    const pane = page.getByTestId('sandbox-web-pane');
    if (await pane.count()) {
      const text = `${await pane.innerText().catch(() => '')}\n${await pageText(page)}`;
      last = text;
      if (pred(text) && (await page.getByTestId('sandbox-web-viewport').count())) {
        return text;
      }
    }
    const err = page.getByTestId('artifact-action-error');
    if (await err.count()) {
      const msg = await err.innerText().catch(() => '');
      last = `${last}\nERR:${msg}`.trim();
    }
    await page.waitForTimeout(800);
  }
  fail('P1', `sandbox pane did not show expected text. last=${last.slice(0, 240)}`);
}

async function main() {
  const args = parseArgs(process.argv);
  const { email, password } = emailPass();
  if (!email || !password) {
    fail('P1', 'DEMO_EMAIL / DEMO_PASSWORD missing');
  }
  fs.mkdirSync(args.out, { recursive: true });

  let tip = null;
  try {
    tip = await fetchTip(args.base);
  } catch (err) {
    tip = { error: String(err?.message || err) };
  }

  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: !args.headed,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const report = {
    card: 'T-NIGHT-SANDBOX-COMPUTER',
    phase: 'P1',
    base: args.base,
    tip,
    s1: 'N',
    s2: 'N',
    s3: 'N',
    s4: 'N',
    claim_wb: 'NO',
  };

  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
    await login(page, args.base, email, password);

    // S1 — open example.com, right pane is the sandbox Chrome.
    await goNewChat(page, args.base);
    await sendPrompt(page, '打开 https://example.com');
    await shot(page, path.join(args.out, 'S1-after-send.png'), { allowSmall: true }).catch(() => {});
    const s1Text = await waitSandboxReady(
      page,
      (t) => /Example Domain/i.test(t),
      args.timeoutMs,
    );
    await page.waitForTimeout(1500);
    const s1 = await shot(page, path.join(args.out, 'S1-example.png'));
    const s1v = await saveViewportPng(page, path.join(args.out, 'S1-viewport.png'));
    if (!/Example Domain/i.test(s1Text)) {
      fail('P1', 'S1: Example Domain not visible in right pane');
    }
    report.s1 = 'Y';
    report.s1_bytes = s1.size;
    report.s1_viewport_bytes = s1v.size;

    // S2 — open a real docx in Writer, not PDF / download.
    await goNewChat(page, args.base);
    await sendPrompt(page, '打开课堂笔记.docx');
    const s2Text = await waitSandboxReady(
      page,
      (t) => /Writer|LibreOffice|课堂笔记/i.test(t),
      args.timeoutMs,
    );
    await page.waitForTimeout(2000);
    const s2 = await shot(page, path.join(args.out, 'S2-writer.png'));
    const s2v = await saveViewportPng(page, path.join(args.out, 'S2-viewport.png'));
    if (/成品\s*·\s*可下载文件|MainDeliveryStrip/i.test(s2Text)) {
      fail('P1', 'S2: delivery strip still present');
    }
    if (!/Writer|LibreOffice|课堂笔记/i.test(s2Text)) {
      fail('P1', 'S2: Writer window not visible');
    }
    report.s2 = 'Y';
    report.s2_bytes = s2.size;
    report.s2_viewport_bytes = s2v.size;

    // S3 — middle column is chat only.
    const body = await pageText(page);
    if (await page.getByTestId('main-delivery-strip').count()) {
      fail('P1', 'S3: main-delivery-strip present');
    }
    if (/成品\s*·\s*可下载文件/.test(body)) {
      fail('P1', 'S3: 成品·可下载文件 still in DOM');
    }
    if (await page.locator('[data-testid="artifact-html-iframe"], [data-testid="main-delivery-html-iframe"]').count()) {
      fail('P1', 'S3: bubble/html preview iframe present');
    }
    const s3 = await shot(page, path.join(args.out, 'S3-chat-clean.png'));
    report.s3 = 'Y';
    report.s3_bytes = s3.size;

    // S4 — 390, close right rail, still type.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(600);
    const closeBtn = page.getByTestId('result-panel-close');
    if (await closeBtn.count()) {
      await closeBtn.click().catch(() => {});
      await page.waitForTimeout(400);
    }
    if (await page.getByTestId('result-panel').count()) {
      const box = await page.getByTestId('result-panel').boundingBox().catch(() => null);
      if (box && box.width > 200) {
        fail('P1', 'S4: result panel still open on 390');
      }
    }
    const input = await messageInput(page);
    await input.waitFor({ state: 'visible', timeout: 15000 });
    await input.click();
    await input.fill('390仍能打字');
    const typed = await input.inputValue();
    if (!typed.includes('390仍能打字')) {
      fail('P1', 'S4: could not type in composer');
    }
    const s4 = await shot(page, path.join(args.out, 'S4-390.png'), { allowSmall: false });
    report.s4 = 'Y';
    report.s4_bytes = s4.size;
    report.verdict = 'PASS';
  } catch (err) {
    report.verdict = 'FAIL';
    report.error = String(err?.message || err);
    throw err;
  } finally {
    writeJson(path.join(args.out, 'REPORT.json'), report);
    await browser.close();
  }
  console.log(JSON.stringify(report, null, 2));
}

main().catch((err) => {
  console.error(`## BLOCKED P1\n${err.message || err}`);
  process.exit(2);
});
