#!/usr/bin/env node
/**
 * T-SANDBOX-OPEN-REGRESS public frames.
 * PHASE=before|after. Word is regression only.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {
  ROOT,
  loadPlaywright,
  loadEvidenceEnv,
  emailPass,
  fetchTip,
  login,
  goNewChat,
  sendPrompt,
  shot,
  writeJson,
} from './lib.mjs';

loadEvidenceEnv();

const PHASE = process.env.PHASE || 'before';
const EXPECT = process.env.PICO_EXPECT_TIP || '';
const WAIT_MS = Number(process.env.PICO_VISUAL_TIMEOUT_MS || 90000);

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

async function snapshot(page, out, name) {
  const filePath = path.join(out, name);
  const s = await shot(page, filePath, { allowSmall: true });
  const pane = page.getByTestId('result-panel');
  const view = page.getByTestId('sandbox-web-viewport');
  const empty = page.getByTestId('sandbox-empty');
  const toggle = page.getByTestId('result-panel-toggle');
  const body = ((await page.locator('body').innerText().catch(() => '')) || '').slice(0, 400);
  const paneOn = (await pane.count()) > 0 && (await pane.isVisible().catch(() => false));
  const viewOn = (await view.count()) > 0 && (await view.isVisible().catch(() => false));
  const emptyOn = (await empty.count()) > 0 && (await empty.isVisible().catch(() => false));
  let viewText = '';
  if (viewOn) {
    viewText = ((await view.innerText().catch(() => '')) || '').slice(0, 160);
  }
  return {
    name,
    size: s.size,
    sha: sha256(filePath),
    result_panel: paneOn,
    viewport: viewOn,
    empty: emptyOn,
    toggle: (await toggle.count()) > 0,
    view_text: viewText,
    body_head: body.replace(/\s+/g, ' ').slice(0, 220),
  };
}

async function waitSettle(page, ms) {
  const start = Date.now();
  while (Date.now() - start < ms) {
    const view = page.getByTestId('sandbox-web-viewport');
    if ((await view.count()) && (await view.isVisible().catch(() => false))) {
      const text = `${await view.innerText().catch(() => '')}`;
      if (text.trim().length > 8) {
        await page.waitForTimeout(800);
        return;
      }
    }
    await page.waitForTimeout(1200);
  }
}

async function main() {
  const base = process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia';
  const out = path.join(ROOT, 'docs/evidence/pack-sandbox-open-regress', PHASE);
  fs.mkdirSync(out, { recursive: true });
  const { email, password } = emailPass();
  if (!email || !password) {
    throw new Error('DEMO_EMAIL missing');
  }
  const tip = await fetchTip(base);
  if (EXPECT && tip.git_sha !== EXPECT) {
    throw new Error(`tip ${tip.git_sha} != ${EXPECT}`);
  }
  const report = { card: 'T-SANDBOX-OPEN-REGRESS', phase: PHASE, tip, claim_wb: 'NO', frames: {} };
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
    await login(page, base, email, password);

    const prompts = [
      { key: 's1_example', prompt: '打开 https://example.com', file: 'S1-example-before.png' },
      { key: 's1b_browser', prompt: '打开浏览器', file: 'S1b-open-browser-before.png' },
      { key: 's1c_tencent', prompt: '打开腾讯官网', file: 'S1c-tencent-before.png' },
      { key: 's2_word', prompt: '打开一份 Word', file: 'S2-word-before.png' },
    ];
    for (const item of prompts) {
      await goNewChat(page, base);
      await sendPrompt(page, item.prompt);
      await waitSettle(page, WAIT_MS);
      report.frames[item.key] = await snapshot(page, out, item.file);
    }

    writeJson(path.join(out, 'report.json'), report);
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
