#!/usr/bin/env node
/**
 * T-UX-COMPOSER-TYPE-ICON human Playwright: C1 one-row, C2 plus, C3 type, C5 390.
 * Live public after tip install. Local mock uses e2e spec.
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
  shot,
  writeJson,
} from './lib.mjs';

loadEvidenceEnv();

const EXPECT = process.env.PICO_EXPECT_TIP || '';

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function overlapMid(a, b) {
  const mid = a.y + a.height / 2;
  return mid >= b.y - 4 && mid <= b.y + b.height + 4;
}

async function main() {
  const base = process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia';
  const out = path.join(ROOT, 'docs/evidence/pack-ux-composer-type-icon/live');
  fs.mkdirSync(out, { recursive: true });
  const { email, password } = emailPass();
  if (!email || !password) {
    throw new Error('DEMO_EMAIL missing');
  }
  const tip = await fetchTip(base);
  if (EXPECT && tip.git_sha !== EXPECT) {
    throw new Error(`tip ${tip.git_sha} != ${EXPECT}`);
  }
  const report = {
    card: 'T-UX-COMPOSER-TYPE-ICON',
    tip,
    c1: 'N',
    c2: 'N',
    c3: 'N',
    c4: 'N',
    c5: 'N',
    composer_one_row: 'N',
    type_scale: 'N',
    icons_one_set: 'N',
    claim_wb: 'NO',
  };
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

    const row = page.getByTestId('composer-one-row');
    const plus = page.getByTestId('composer-plus');
    const input = page.locator('#pico-wb-home-input, [data-testid="text-input"]').first();
    const send = page.getByTestId('send-button');
    await row.waitFor({ state: 'visible', timeout: 20000 });
    await plus.waitFor({ state: 'visible' });
    await send.waitFor({ state: 'visible' });
    const [rowBox, plusBox, inputBox, sendBox] = await Promise.all([
      row.boundingBox(),
      plus.boundingBox(),
      input.boundingBox(),
      send.boundingBox(),
    ]);
    if (!rowBox || !plusBox || !inputBox || !sendBox) {
      throw new Error('C1: missing boxes');
    }
    if (!overlapMid(plusBox, rowBox) || !overlapMid(sendBox, rowBox) || !overlapMid(inputBox, rowBox)) {
      throw new Error('C1: plus/input/send not one row');
    }
    if (rowBox.height >= 88) {
      throw new Error(`C1: composer row too tall ${rowBox.height}`);
    }
    if (((await plus.textContent()) || '').trim() === '+') {
      throw new Error('C1: text plus still used');
    }
    const c1 = path.join(out, 'c1-one-row-1280.png');
    const s1 = await shot(page, c1);
    report.c1 = 'Y';
    report.composer_one_row = 'Y';
    report.c1_size = s1.size;
    report.c1_sha = sha256(c1);

    await plus.click();
    await page.getByTestId('composer-plus-menu').waitFor({ state: 'visible', timeout: 8000 });
    const c2 = path.join(out, 'c2-plus-open-1280.png');
    const s2 = await shot(page, c2);
    await plus.click();
    if (await page.getByTestId('composer-plus-menu').count()) {
      throw new Error('C2: plus menu did not close');
    }
    report.c2 = 'Y';
    report.c2_size = s2.size;
    report.c2_sha = sha256(c2);

    const style = await input.evaluate((el) => {
      const computed = getComputedStyle(el);
      return { fontSize: computed.fontSize, fontFamily: computed.fontFamily };
    });
    if (parseFloat(style.fontSize) !== 15) {
      throw new Error(`C3: font-size ${style.fontSize}`);
    }
    if (/^\s*inter\b/i.test(style.fontFamily)) {
      throw new Error(`C3: Inter still first: ${style.fontFamily}`);
    }
    if (!/PingFang|Hiragino|Source Han|Noto Sans SC|Microsoft YaHei|Heiti/i.test(style.fontFamily)) {
      throw new Error(`C3: CJK face missing: ${style.fontFamily}`);
    }
    report.c3 = 'Y';
    report.type_scale = 'Y';
    report.font = style;

    const lucide = page.locator(
      '.pico-wb-sidebar svg.lucide, .pico-wb-composer svg.lucide, .pico-wb-sidebar [class*="lucide-"], .pico-wb-composer [class*="lucide-"]',
    );
    if ((await lucide.count()) > 0) {
      throw new Error('C4: lucide still in sidebar/composer');
    }
    if ((await page.getByRole('button', { name: '新对话' }).count()) > 1) {
      throw new Error('C4: duplicate 新对话');
    }
    report.c4 = 'Y';
    report.icons_one_set = 'Y';

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(400);
    const c5 = path.join(out, 'c5-390.png');
    const s5 = await shot(page, c5);
    const box390 = await row.boundingBox();
    if (box390 && box390.x + box390.width > 400) {
      throw new Error('C5: composer stretches past 390');
    }
    report.c5 = 'Y';
    report.c5_size = s5.size;
    report.c5_sha = sha256(c5);

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
