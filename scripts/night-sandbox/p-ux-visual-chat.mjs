#!/usr/bin/env node
/**
 * T-UX-VISUAL-CHAT public AFTER frames. Run only after tip install.
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

const EXPECT = process.env.PICO_EXPECT_TIP || '';

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

async function main() {
  const base = process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia';
  const out = path.join(ROOT, 'docs/evidence/pack-ux-visual-chat/live');
  fs.mkdirSync(out, { recursive: true });
  const { email, password } = emailPass();
  if (!email || !password) {
    throw new Error('DEMO_EMAIL missing');
  }
  const tip = await fetchTip(base);
  if (EXPECT && tip.git_sha !== EXPECT) {
    throw new Error(`tip ${tip.git_sha} != ${EXPECT}`);
  }
  const report = { card: 'T-UX-VISUAL-CHAT', phase: 'live-after', tip, claim_wb: 'NO' };
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      ignoreHTTPSErrors: true,
      serviceWorkers: 'block',
    });
    const page = await context.newPage();
    await login(page, base, email, password);
    await goNewChat(page, base);
    const body = await page.locator('body').innerText();
    if (/日常办公|今天帮你做些什么？/.test(body)) {
      throw new Error('live V1 still dashboard');
    }
    if ((await page.getByTestId('model-selector-button').count()) > 0) {
      throw new Error('live V1 header model chip');
    }
    const v1 = path.join(out, 'V1-empty-middle-1280.png');
    report.v1 = { size: (await shot(page, v1)).size, sha: sha256(v1) };

    await page.getByTestId('composer-plus').click();
    const menu = page.getByTestId('composer-plus-menu');
    await menu.waitFor({ state: 'visible' });
    const menuText = await menu.innerText();
    if (/工作空间|默认权限/.test(menuText)) {
      throw new Error(`live V2 junk: ${menuText}`);
    }
    const v2 = path.join(out, 'V2-plus-open-1280.png');
    report.v2 = { size: (await shot(page, v2)).size, sha: sha256(v2), menuText };
    await page.keyboard.press('Escape').catch(() => {});

    await sendPrompt(page, '只回一句中文：你好。不要调用工具。');
    await page.waitForTimeout(8000);
    if ((await page.getByTestId('result-panel').count()) > 0) {
      throw new Error('live V3 right rail opened on hello');
    }
    const v3 = path.join(out, 'V3-one-bubble-1280.png');
    report.v3 = { size: (await shot(page, v3)).size, sha: sha256(v3) };

    await goNewChat(page, base);
    await sendPrompt(page, '打开 https://example.com');
    const start = Date.now();
    while (Date.now() - start < Number(process.env.PICO_VISUAL_TIMEOUT_MS || 150000)) {
      if (await page.getByTestId('sandbox-web-viewport').count()) {
        break;
      }
      await page.waitForTimeout(800);
    }
    if (await page.getByTestId('pico-search-sources').count()) {
      throw new Error('live V4 sources');
    }
    if (await page.getByText('打开我的文件', { exact: true }).count()) {
      throw new Error('live V4 打开文件');
    }
    const v4 = path.join(out, 'V4-middle-right-sandbox-1280.png');
    report.v4 = { size: (await shot(page, v4)).size, sha: sha256(v4) };

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(400);
    const v5 = path.join(out, 'V5-390-middle.png');
    report.v5 = { size: (await shot(page, v5, { allowSmall: true })).size, sha: sha256(v5) };

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
