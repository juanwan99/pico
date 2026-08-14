#!/usr/bin/env node
/**
 * P2 teacher script — same session: site → Writer → back to site.
 *
 *   node scripts/night-sandbox/p2-switch.mjs --base https://pico.aivia.asia
 */
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
  saveViewportPng,
  writeJson,
} from './lib.mjs';

loadEvidenceEnv();

function parseArgs(argv) {
  const out = {
    base: process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia',
    out: process.env.PICO_NIGHT_OUT || path.join(ROOT, 'docs/evidence/pack-night-sandbox/p2'),
    headed: process.env.PICO_VISUAL_HEADED === '1',
    timeoutMs: Number(process.env.PICO_VISUAL_TIMEOUT_MS || 180000),
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

async function waitPane(page, re, timeoutMs) {
  const start = Date.now();
  let last = '';
  while (Date.now() - start < timeoutMs) {
    const pane = page.getByTestId('sandbox-web-pane');
    if (await pane.count()) {
      last = await pane.innerText().catch(() => '');
      if (re.test(last) && (await page.getByTestId('sandbox-web-viewport').count())) {
        return last;
      }
    }
    await page.waitForTimeout(800);
  }
  throw new Error(`pane did not match ${re}: ${last.slice(0, 200)}`);
}

async function main() {
  const args = parseArgs(process.argv);
  const { email, password } = emailPass();
  if (!email || !password) {
    throw new Error('DEMO_EMAIL / DEMO_PASSWORD missing');
  }
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
    phase: 'P2',
    base: args.base,
    tip,
    s5: 'N',
    s6: 'N',
    claim_wb: 'NO',
  };
  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
    await login(page, args.base, email, password);
    await goNewChat(page, args.base);
    await sendPrompt(page, '打开 https://example.com');
    await waitPane(page, /Example Domain/i, args.timeoutMs);
    await page.waitForTimeout(800);
    await sendPrompt(page, '打开课堂笔记.docx');
    await waitPane(page, /Writer|LibreOffice|课堂笔记/i, args.timeoutMs);
    await page.waitForTimeout(1500);
    const s5 = await shot(page, path.join(args.out, 'S5-writer.png'));
    const s5v = await saveViewportPng(page, path.join(args.out, 'S5-viewport.png'));
    report.s5 = 'Y';
    report.s5_bytes = s5.size;
    report.s5_viewport = s5v.size;

    const bar = page.getByTestId('sandbox-window-bar');
    await bar.waitFor({ state: 'visible', timeout: 20000 });
    const browserBtn = page.getByTestId('sandbox-window-browser');
    await browserBtn.click();
    await waitPane(page, /Example Domain/i, args.timeoutMs);
    await page.waitForTimeout(800);
    const s6 = await shot(page, path.join(args.out, 'S6-browser.png'));
    const s6v = await saveViewportPng(page, path.join(args.out, 'S6-viewport.png'));
    report.s6 = 'Y';
    report.s6_bytes = s6.size;
    report.s6_viewport = s6v.size;
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
  console.error(`## BLOCKED P2\n${err.message || err}`);
  process.exit(2);
});
