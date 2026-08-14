#!/usr/bin/env node
/**
 * P3 teacher: unique file visible on sandbox screen, open shows content.
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
    out: process.env.PICO_NIGHT_OUT || path.join(ROOT, 'docs/evidence/pack-night-sandbox/p3'),
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

async function waitText(page, re, timeoutMs) {
  const start = Date.now();
  let last = '';
  while (Date.now() - start < timeoutMs) {
    last = await page.locator('body').innerText().catch(() => '');
    if (re.test(last)) {
      return last;
    }
    await page.waitForTimeout(700);
  }
  throw new Error(`did not see ${re}: ${last.slice(0, 200)}`);
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
  throw new Error(`pane did not match ${re}: ${last.slice(0, 200)}`);
}

async function main() {
  const args = parseArgs(process.argv);
  const { email, password } = emailPass();
  const unique = `night-p3-${Date.now()}.docx`;
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
    phase: 'P3',
    base: args.base,
    tip,
    unique,
    s7: 'N',
    s8: 'N',
    s9: 'N',
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
    await sendPrompt(page, `打开 ${unique}`);
    const uniqueRe = new RegExp(unique.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    await waitPane(page, uniqueRe, args.timeoutMs);
    await waitPane(page, /Writer|LibreOffice/i, args.timeoutMs);
    await shot(page, path.join(args.out, 'S7-before-files.png'), { allowSmall: true }).catch(
      () => {},
    );
    const filesTab = page.getByTestId('sandbox-window-files');
    if (await filesTab.count()) {
      await filesTab.click();
    } else {
      await page.getByTestId('sandbox-open-files').click();
    }
    const fileBtn = page.getByTestId(`sandbox-file-${unique}`);
    await fileBtn.waitFor({ state: 'visible', timeout: args.timeoutMs });
    const s7 = await shot(page, path.join(args.out, 'S7-files.png'));
    report.s7 = 'Y';
    report.s7_bytes = s7.size;

    await fileBtn.click();
    await waitText(page, /Writer|LibreOffice|Word 正文/i, args.timeoutMs);
    await page.waitForTimeout(800);
    const s8 = await shot(page, path.join(args.out, 'S8-open.png'));
    await saveViewportPng(page, path.join(args.out, 'S8-viewport.png')).catch(() => {});
    report.s8 = 'Y';
    report.s8_bytes = s8.size;

    const body = await page.locator('body').innerText();
    if (/https?:\/\/pico\.aivia\.asia\/.+docx/i.test(body) && !body.includes(unique)) {
      throw new Error('S9: file only visible as public URL');
    }
    if (!body.includes(unique) && !/工作区文件|sandbox:\/\/writer/i.test(body)) {
      throw new Error('S9: workspace file not visible on sandbox screen');
    }
    const s9 = await shot(page, path.join(args.out, 'S9-workspace.png'));
    report.s9 = 'Y';
    report.s9_bytes = s9.size;
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
  console.error(`## BLOCKED P3\n${err.message || err}`);
  process.exit(2);
});
