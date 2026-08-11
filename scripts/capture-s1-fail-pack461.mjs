#!/usr/bin/env node
/**
 * T-PACK-TRIPLE-100-NIGHT (#461) S1 evidence — real public browser, open a
 * known failed conversation and capture main-area fail frame.
 * Verifies: no `Something went wrong`, no bare `terminated`, Chinese + rerun.
 * CLAIM-WB: NO
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const outDir = path.join(
  ROOT,
  'docs/evidence/pack-triple-100-night/m1-s1-fail-human',
);
fs.mkdirSync(outDir, { recursive: true });

const email = process.env.PICO_E2E_EMAIL || process.env.DEMO_EMAIL || '';
const password = process.env.PICO_E2E_PASSWORD || process.env.DEMO_PASSWORD || '';
const base = process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia';
const failUrl =
  process.env.FAIL_CONV_URL ||
  'https://pico.aivia.asia/c/fa731e9b-5809-4a95-9664-8fe4ca0e3dd6';

function analyze(text) {
  const hasSomething = /Something went wrong/i.test(text);
  const hasOwnerLost = /owner was lost/i.test(text);
  const hasBareTerminated =
    /(request:\s*terminated|^terminated$|\bterminated\b)/i.test(text) &&
    !/服务维护/.test(text);
  const hasChineseFail = /服务维护|重启导致|任务中断|重新运行/.test(text);
  const snippets = text
    .split('\n')
    .map((s) => s.trim())
    .filter((s) =>
      /terminated|Something went wrong|服务维护|重新运行|owner was lost|失败|中断/i.test(
        s,
      ),
    )
    .slice(0, 50);
  return {
    hasSomething,
    hasOwnerLost,
    hasBareTerminated,
    hasChineseFail,
    snippets,
    pass:
      !hasSomething && !hasOwnerLost && !hasBareTerminated && hasChineseFail,
  };
}

async function login(page) {
  await page.goto(`${base}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(800);
  await page
    .locator('input[type="email"], input[name="email"], input#email, input[autocomplete="username"]')
    .first()
    .fill(email);
  await page
    .locator('input[type="password"], input[name="password"], input#password')
    .first()
    .fill(password);
  await page
    .locator('button[type="submit"], button:has-text("登录"), button:has-text("Continue"), button:has-text("Sign")')
    .first()
    .click();
  for (let i = 0; i < 50; i++) {
    if (!page.url().includes('/login')) break;
    await page.waitForTimeout(400);
  }
}

async function main() {
  if (!email || password.length < 12) {
    console.error('BLOCKED: demo credentials missing');
    process.exit(2);
  }
  const tip = await (await fetch(`${base}/api/pico/tip`)).json();
  console.log(JSON.stringify({ step: 'tip', ...tip }));

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: 'zh-CN',
  });
  const page = await context.newPage();
  try {
    await login(page);
    console.log('login_url', page.url());

    await page.goto(failUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);
    let text = await page.locator('body').innerText();
    const a = analyze(text);
    await page.screenshot({ path: path.join(outDir, 'V2-fail-main.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(outDir, 'V2-fail-main-390.png'), fullPage: true });
    await page.setViewportSize({ width: 1440, height: 900 });

    // home + sidebar fail state
    await page.goto(`${base}/`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);
    const homeText = await page.locator('body').innerText();
    await page.screenshot({ path: path.join(outDir, 'V2-home-sidebar.png'), fullPage: true });

    const report = {
      tip,
      failUrl,
      conversation: a,
      homeChinese: /服务维护|重启导致|重新运行/.test(homeText),
      homeEnglish: /Something went wrong|owner was lost/i.test(homeText),
      pass_v1: a.pass,
      claim_wb: 'NO',
    };
    fs.writeFileSync(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    await browser.close();
    process.exit(report.pass_v1 ? 0 : 3);
  } catch (e) {
    await browser.close().catch(() => {});
    console.error(e);
    process.exit(1);
  }
}

main();
