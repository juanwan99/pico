import { chromium } from 'playwright';
import fs from 'fs';

const shots = '/workspace/screenshots';
fs.mkdirSync(shots, { recursive: true });

async function probe(url, name) {
  const res = await fetch(url, { redirect: 'manual' });
  const headers = Object.fromEntries(res.headers.entries());
  const buf = Buffer.from(await res.arrayBuffer());
  const text = buf.toString('utf8');
  return {
    name,
    url,
    status: res.status,
    bodyLen: buf.length,
    contentType: headers['content-type'] || '',
    location: headers['location'] || '',
    hasPicoLoading: text.includes('Pico 正在加载'),
    hasWelcome: /Welcome back|欢迎/i.test(text),
    hasPicoTitle: text.includes('<title>Pico</title>'),
    snippet: text.slice(0, 180).replace(/\s+/g, ' '),
  };
}

async function browser(url, shot) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push(String(err)));
  let navStatus = null;
  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    navStatus = resp ? resp.status() : null;
    await page.waitForTimeout(2500);
  } catch (e) {
    consoleErrors.push('nav:' + e.message);
  }
  const bodyText = await page.locator('body').innerText().catch(() => '');
  const html = await page.content();
  await page.screenshot({ path: shot, fullPage: true });
  await browser.close();
  return {
    url,
    navStatus,
    bodyText: bodyText.slice(0, 500),
    hasWelcome: /Welcome back|欢迎/i.test(bodyText) || /Welcome back|欢迎/i.test(html),
    hasPicoLoading: bodyText.includes('Pico 正在加载') || html.includes('Pico 正在加载'),
    hasLoginForm: /password|email|登录|Sign in/i.test(bodyText),
    consoleErrors: consoleErrors.slice(0, 15),
    shot,
  };
}

const report = {
  at: new Date().toISOString(),
  http: {},
  browser: {},
};

for (const [url, name] of [
  ['http://127.0.0.1:8080/login', '8080'],
  ['http://127.0.0.1:6014/login', '6014'],
  ['http://127.0.0.1:3080/login', '3080'],
  ['http://127.0.0.1:18765/health', 'api'],
]) {
  try {
    report.http[name] = await probe(url, name);
  } catch (e) {
    report.http[name] = { name, url, error: String(e) };
  }
}

for (const [url, name] of [
  ['http://127.0.0.1:8080/login', '8080'],
  ['http://127.0.0.1:6014/login', '6014'],
]) {
  try {
    report.browser[name] = await browser(url, `${shots}/preview-${name}.png`);
  } catch (e) {
    report.browser[name] = { url, error: String(e) };
  }
}

fs.writeFileSync(`${shots}/preview-diagnose.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
