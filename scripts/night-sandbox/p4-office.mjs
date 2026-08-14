#!/usr/bin/env node
/**
 * P4 teacher: xlsx in Calc (S10 required) + pptx in Impress (S11, DEGRADED ok).
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
    out: process.env.PICO_NIGHT_OUT || path.join(ROOT, 'docs/evidence/pack-night-sandbox/p4'),
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
    await page.waitForTimeout(700);
  }
  throw new Error(`pane did not match ${re}: ${last.slice(0, 240)}`);
}

async function main() {
  const args = parseArgs(process.argv);
  const { email, password } = emailPass();
  if (!email || !password) {
    throw new Error('DEMO_EMAIL / DEMO_PASSWORD missing');
  }
  const xlsx = `night-p4-${Date.now()}.xlsx`;
  const pptx = `night-p4-${Date.now()}.pptx`;
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
    phase: 'P4',
    base: args.base,
    tip,
    xlsx,
    pptx,
    cell: 'NIGHT-P4-CELL-ALPHA',
    s10: 'N',
    s11: 'N',
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
    await sendPrompt(page, `打开 ${xlsx}`);
    const s10Text = await waitPane(page, /Calc|LibreOffice|NIGHT-P4-CELL-ALPHA/i, args.timeoutMs);
    await page.waitForTimeout(1500);
    const s10 = await shot(page, path.join(args.out, 'S10-calc.png'));
    const s10v = await saveViewportPng(page, path.join(args.out, 'S10-viewport.png')).catch(
      () => ({ size: 0 }),
    );
    if (!/Calc|LibreOffice/i.test(s10Text)) {
      throw new Error('S10: Calc window not visible');
    }
    report.s10 = 'Y';
    report.s10_bytes = s10.size;
    report.s10_viewport = s10v.size;

    await sendPrompt(page, `打开 ${pptx}`);
    try {
      const s11Text = await waitPane(page, /Impress|LibreOffice|NIGHT-P4-SLIDE-ALPHA/i, args.timeoutMs);
      await page.waitForTimeout(1200);
      const s11 = await shot(page, path.join(args.out, 'S11-impress.png'));
      await saveViewportPng(page, path.join(args.out, 'S11-viewport.png')).catch(() => {});
      if (/成品\s*·\s*可下载文件|\.pdf\b/i.test(s11Text)) {
        throw new Error('S11: PDF/download path is not allowed');
      }
      report.s11 = 'Y';
      report.s11_bytes = s11.size;
    } catch (err) {
      const msg = String(err?.message || err);
      if (/PDF|download/i.test(msg)) {
        throw err;
      }
      await shot(page, path.join(args.out, 'S11-degraded.png'), { allowSmall: true }).catch(() => {});
      report.s11 = 'DEGRADED';
      report.s11_reason = msg.slice(0, 240);
    }
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
  console.error(`## BLOCKED P4\n${err.message || err}`);
  process.exit(2);
});
