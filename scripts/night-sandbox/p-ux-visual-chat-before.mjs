#!/usr/bin/env node
/**
 * T-UX-VISUAL-CHAT · public BEFORE frames. No product code change.
 * B1 empty middle · B2 plus open · B3 one bubble · B4 sandbox right · B5 390
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

const EXPECT = process.env.PICO_EXPECT_TIP || '5a057419b589a9a84768ad895453ba490c2919eb';

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

async function dumpMiddle(page) {
  return page.evaluate(() => {
    const text = document.body?.innerText || '';
    const pick = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        sel,
        text: (el.innerText || '').slice(0, 180),
        x: Math.round(r.x),
        y: Math.round(r.y),
        w: Math.round(r.width),
        h: Math.round(r.height),
      };
    };
    return {
      title: document.title,
      url: location.href,
      hasPicoFast: /pico-fast|Pico 快速|快速/.test(text),
      hasWorkspace: /工作空间/.test(text),
      hasPerm: /默认权限|完全访问/.test(text),
      hasSources: /来源/.test(text),
      hasOpenFile: /打开文件|打开我的文件/.test(text),
      hasLogin: /登录|邮箱|密码/.test(text),
      hasHero: /今天想做什么|今天帮你做些什么|Pico，我帮你/.test(text),
      boxes: {
        composer: pick('[data-testid="composer-one-row"]'),
        plus: pick('[data-testid="composer-plus"]'),
        plusMenu: pick('[data-testid="composer-plus-menu"]'),
        homeComposer: pick('[data-testid="pico-wb-home-composer"]'),
        input: pick('#pico-wb-home-input, [data-testid="text-input"]'),
        send: pick('[data-testid="send-button"]'),
        model: pick('[data-testid="model-selector-button"]'),
        bookmark: pick('[data-testid="bookmark-menu"]'),
        sandbox: pick('[data-testid="sandbox-web-pane"]'),
        sources: pick('[data-testid="pico-search-sources"]'),
        result: pick('[data-testid="result-panel"]'),
      },
      plusMenuText: (document.querySelector('[data-testid="composer-plus-menu"]')?.innerText || '').slice(
        0,
        400,
      ),
      headerText: (document.querySelector('header, [class*="Header"], .absolute.top-0')?.innerText || '').slice(
        0,
        240,
      ),
    };
  });
}

async function waitSandbox(page, timeoutMs) {
  const start = Date.now();
  let last = '';
  while (Date.now() - start < timeoutMs) {
    const pane = page.getByTestId('sandbox-web-pane');
    if (await pane.count()) {
      last = `${await pane.innerText().catch(() => '')}`;
      const live = await pane.getAttribute('data-live').catch(() => '');
      const hasView = await page.getByTestId('sandbox-web-viewport').count();
      if (live !== 'dead' && hasView) {
        return last;
      }
      if (/Example Domain|沙箱|网页|打开/i.test(last) && (await pane.isVisible().catch(() => false))) {
        return last;
      }
    }
    await page.waitForTimeout(800);
  }
  return last;
}

async function main() {
  const base = process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia';
  const out = path.join(ROOT, 'docs/evidence/pack-ux-visual-chat/before');
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
    card: 'T-UX-VISUAL-CHAT',
    phase: 'before',
    tip,
    claim_wb: 'NO',
    frames: {},
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
    await page.waitForTimeout(800);
    const input = page.locator('#pico-wb-home-input, [data-testid="text-input"]').first();
    if (await input.count()) {
      await input.click().catch(() => {});
    }

    const b1 = path.join(out, 'B1-empty-middle-1280.png');
    const s1 = await shot(page, b1);
    report.frames.B1 = { size: s1.size, sha: sha256(b1), inspect: await dumpMiddle(page) };

    const plus = page.getByTestId('composer-plus');
    await plus.waitFor({ state: 'visible', timeout: 20000 });
    await plus.click();
    await page.waitForTimeout(400);
    const b2 = path.join(out, 'B2-plus-open-1280.png');
    const s2 = await shot(page, b2);
    report.frames.B2 = { size: s2.size, sha: sha256(b2), inspect: await dumpMiddle(page) };
    await plus.click().catch(() => {});
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(200);

    await sendPrompt(page, '只回一句中文：你好。不要调用工具。');
    const start = Date.now();
    while (Date.now() - start < 90000) {
      const body = await page.locator('body').innerText();
      if (/你好/.test(body) && /只回一句|不要调用/.test(body)) {
        break;
      }
      await page.waitForTimeout(800);
    }
    await page.waitForTimeout(1200);
    const b3 = path.join(out, 'B3-one-bubble-1280.png');
    const s3 = await shot(page, b3);
    report.frames.B3 = { size: s3.size, sha: sha256(b3), inspect: await dumpMiddle(page) };

    await goNewChat(page, base);
    await sendPrompt(page, '打开 https://example.com');
    const sandboxText = await waitSandbox(page, Number(process.env.PICO_VISUAL_TIMEOUT_MS || 150000));
    await page.waitForTimeout(1500);
    const b4 = path.join(out, 'B4-middle-right-sandbox-1280.png');
    const s4 = await shot(page, b4);
    report.frames.B4 = {
      size: s4.size,
      sha: sha256(b4),
      inspect: await dumpMiddle(page),
      sandboxText: String(sandboxText || '').slice(0, 240),
    };

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(500);
    const b5 = path.join(out, 'B5-390-middle.png');
    const s5 = await shot(page, b5);
    report.frames.B5 = { size: s5.size, sha: sha256(b5), inspect: await dumpMiddle(page) };

    const sizes = [s1.size, s2.size, s3.size, s4.size, s5.size];
    if (sizes.some((n) => n < 20_000)) {
      throw new Error(`frame too small: ${sizes.join(',')}`);
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
