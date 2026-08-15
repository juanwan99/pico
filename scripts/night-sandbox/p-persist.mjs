#!/usr/bin/env node
/**
 * T-SANDBOX-PERSIST: write unique.docx, kill session, file still there.
 * Playwright is the teacher. Jest is not a stage pass.
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
    out: process.env.PICO_PERSIST_OUT || path.join(ROOT, 'docs/evidence/pack-sandbox-persist'),
    headed: process.env.PICO_VISUAL_HEADED === '1',
    timeoutMs: Number(process.env.PICO_VISUAL_TIMEOUT_MS || 180000),
    expectTip: process.env.PICO_EXPECT_TIP || '',
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--base') out.base = next();
    else if (a === '--out') out.out = next();
    else if (a === '--headed') out.headed = true;
    else if (a === '--expect-tip') out.expectTip = next();
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
      if (re.test(last)) return last;
    }
    last = await page.locator('body').innerText().catch(() => last);
    if (re.test(last)) return last;
    await page.waitForTimeout(700);
  }
  throw new Error(`pane did not match ${re}: ${last.slice(0, 220)}`);
}

async function main() {
  const args = parseArgs(process.argv);
  const { email, password } = emailPass();
  const unique = `persist-t1-${Date.now()}.docx`;
  const marker = `PERSIST-${Date.now()}`;
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
    card: 'T-SANDBOX-PERSIST',
    base: args.base,
    tip,
    unique,
    marker,
    t1: 'N',
    t2: 'N',
    t3: 'N',
    t4: 'N',
    claim_wb: 'NO',
  };
  try {
    if (args.expectTip && tip?.git_sha && tip.git_sha !== args.expectTip) {
      throw new Error(`tip ${tip.git_sha} != expect ${args.expectTip}`);
    }
    if (tip?.git_sha && /^[0-9a-f]{40}$/.test(tip.git_sha)) {
      report.t4 = 'Y';
    }
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
    await login(page, args.base, email, password);
    await goNewChat(page, args.base);
    await sendPrompt(page, `打开 ${unique} ，正文写 ${marker}`);
    await waitPane(page, new RegExp(unique.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')), args.timeoutMs);

    const closeBtn = page.getByTestId('sandbox-close-keep-disk');
    if (await closeBtn.count()) {
      await closeBtn.click();
    }
    await page.waitForTimeout(800);
    const openFiles = page.getByTestId('sandbox-open-files');
    await openFiles.click();
    const fileBtn = page.getByTestId(`sandbox-file-${unique}`);
    await fileBtn.waitFor({ state: 'visible', timeout: args.timeoutMs });
    const t1 = await shot(page, path.join(args.out, 't1-tree.png'));
    report.t1 = 'Y';
    report.t1_bytes = t1.size;

    await fileBtn.click();
    await waitPane(page, /Writer|LibreOffice|Word/i, args.timeoutMs);
    await page.waitForTimeout(800);
    const t2 = await shot(page, path.join(args.out, 't2-reopen.png'));
    await saveViewportPng(page, path.join(args.out, 't2-viewport.png')).catch(() => {});
    report.t2 = 'Y';
    report.t2_bytes = t2.size;

    const disk = await page.evaluate(async () => {
      const res = await fetch('/api/pico/v1/sandbox/disk', { credentials: 'include' });
      return { status: res.status, body: await res.json().catch(() => ({})) };
    });
    const names = (disk.body?.files || []).map((f) => f.name);
    if (!names.includes(unique)) {
      throw new Error(`T1 disk missing ${unique}: ${JSON.stringify(disk).slice(0, 240)}`);
    }
    report.t3 = 'SKIP-same-account';
    report.disk = disk;
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
  console.error(err);
  process.exit(1);
});
