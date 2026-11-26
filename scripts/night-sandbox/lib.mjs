#!/usr/bin/env node
/**
 * Shared teacher-click helpers for overnight sandbox human tests.
 * Playwright is the teacher. API 200 / Jest is not a stage pass.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(__dirname, '../..');

export function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const candidates = [
    path.join(ROOT, 'node_modules', 'playwright'),
    path.join(ROOT, 'apps', 'librechat', 'node_modules', 'playwright'),
    path.join(process.env.HOME || '', '.npm-global', 'lib', 'node_modules', 'playwright'),
    'playwright',
  ];
  for (const c of candidates) {
    try {
      return require(c);
    } catch {
      /* next */
    }
  }
  throw new Error('playwright not found');
}

export function emailPass() {
  const email = process.env.PICO_E2E_EMAIL || process.env.DEMO_EMAIL || '';
  const password = process.env.PICO_E2E_PASSWORD || process.env.DEMO_PASSWORD || '';
  return { email, password };
}

export function loadEvidenceEnv() {
  const p = path.join(process.env.HOME || '', '.secrets', 'pico-r4r6-evidence.env');
  if (!fs.existsSync(p)) {
    return;
  }
  for (const line of fs.readFileSync(p, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!m) continue;
    const key = m[1];
    let val = m[2];
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    if (!process.env[key]) {
      process.env[key] = val;
    }
  }
}

export async function fetchTip(base) {
  const url = new URL('/api/pico/tip', base).toString();
  const res = await fetch(url, { redirect: 'follow' });
  const text = await res.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error(`tip not JSON http=${res.status}: ${text.slice(0, 120)}`);
  }
  if (!json?.ok || !json?.git_sha || !/^[0-9a-f]{40}$/.test(json.git_sha)) {
    throw new Error(`tip invalid: ${text.slice(0, 200)}`);
  }
  return { url, ...json };
}

export function ensureDir(d) {
  fs.mkdirSync(d, { recursive: true });
}

export async function shot(page, filePath, opts = {}) {
  ensureDir(path.dirname(filePath));
  await page.screenshot({ path: filePath, fullPage: !!opts.fullPage, type: 'png' });
  const size = fs.statSync(filePath).size;
  if (size < 20_000 && !opts.allowSmall) {
    throw new Error(`frame too small (${size}B): ${filePath}`);
  }
  return { filePath, size };
}

export async function gotoRetry(
  page,
  url,
  { waitUntil = 'domcontentloaded', timeout = 60000, tries = 4 } = {},
) {
  let lastErr;
  for (let i = 1; i <= tries; i++) {
    try {
      await page.goto(url, { waitUntil, timeout });
      return;
    } catch (err) {
      lastErr = err;
      const msg = String(err?.message || err);
      const transient =
        /ERR_NETWORK_CHANGED|ERR_CONNECTION_RESET|ERR_CONNECTION_REFUSED|ERR_ABORTED|net::ERR_|timeout|Timeout|net::ERR_EMPTY_RESPONSE/i.test(
          msg,
        );
      if (!transient) throw err;
      await page.waitForTimeout(1500 * i);
    }
  }
  throw lastErr;
}

export async function messageInput(page) {
  const landing = page.locator('#pico-wb-home-input');
  if (await landing.count()) return landing.first();
  const home = page.locator('[data-testid="pico-wb-home-composer"] textarea');
  if (await home.count()) return home.first();
  const byName = page.getByRole('textbox', { name: /Message input|消息|发消息|任务/i });
  if (await byName.count()) return byName.first();
  const formBox = page.locator('form').getByRole('textbox');
  if (await formBox.count()) return formBox.first();
  return page.locator('[data-testid="text-input"], textarea').first();
}

export async function login(page, base, email, password) {
  const loginUrl = new URL('/login', base).toString();
  await gotoRetry(page, loginUrl);
  await page.waitForTimeout(800);
  if (await page.getByRole('textbox', { name: /Message input|消息/i }).count()) {
    return { already: true };
  }
  const emailBox = page.getByLabel(/Email|邮箱|电子邮件/i).first();
  const passBox = page.getByLabel(/Password|密码/i).first();
  if ((await emailBox.count()) && (await passBox.count())) {
    await emailBox.fill(email);
    await passBox.fill(password);
  } else {
    await page.locator('input[type="email"], input[name="email"]').first().fill(email);
    await page.locator('input[type="password"]').first().fill(password);
  }
  const loginBtn = page.getByTestId('login-button');
  if (await loginBtn.count()) {
    await loginBtn.click();
  } else {
    await page.getByRole('button', { name: /[Ll]og ?in|登录|Sign in/i }).click();
  }
  await page.waitForURL(/\/(c\/|chat)/, { timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(1200);
  return { already: false };
}

export async function loginWithEdu(page, base, { eduBase, school, loginName }) {
  if (!school) throw new Error('--edu-school is required with --edu-login.');
  if (school !== 'dd792255-de1c-4c6e-a750-5b15c7a213c1' || !loginName.startsWith('drill.')) {
    throw new Error('Use a drill.* teacher from 建校演练校 for the edu latency test.');
  }
  const key = `ACCEPT_PASSWORD_${loginName.toUpperCase().replace(/[^A-Z0-9]/g, '_')}`;
  const password = process.env[key] || process.env.EDU_ACCEPT_PASSWORD || process.env.EDU_SMOKE_PASSWORD;
  if (!password) throw new Error(`Set ${key}, EDU_ACCEPT_PASSWORD or EDU_SMOKE_PASSWORD.`);

  const loginResponse = await fetch(new URL('/api/v1/auth/login', eduBase), {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'application/json' },
    body: JSON.stringify({ login_name: loginName, password }),
  });
  if (!loginResponse.ok) throw new Error(`edu login HTTP ${loginResponse.status}`);
  const { access_token: eduToken } = await loginResponse.json();
  if (!eduToken) throw new Error('edu login did not return an access token.');

  const ticketResponse = await fetch(new URL(`/api/v1/schools/${school}/pico/web-ticket`, eduBase), {
    method: 'POST',
    headers: { authorization: `Bearer ${eduToken}`, accept: 'application/json' },
  });
  if (!ticketResponse.ok) throw new Error(`edu web-ticket HTTP ${ticketResponse.status}`);
  const { ticket } = await ticketResponse.json();
  if (!ticket) throw new Error('edu web-ticket did not return a ticket.');

  const ssoUrl = new URL('/api/auth/edu-sso', base);
  ssoUrl.searchParams.set('ticket', ticket);
  const [refreshed] = await Promise.all([
    page.waitForResponse((res) =>
      res.url() === `${base}/api/auth/refresh` && res.request().method() === 'POST',
    ),
    (async () => {
      // Playwright navigation errors include the URL. Keep the one-time ticket out of logs.
      const landing = await page.goto(ssoUrl.href, { waitUntil: 'domcontentloaded' }).catch((error) => {
        throw new Error(`Pico edu SSO navigation failed (${error.name}).`);
      });
      if (landing?.url() !== `${base}/c/new` || !landing.ok()) {
        throw new Error('Pico edu SSO did not reach /c/new.');
      }
    })(),
  ]);
  if (!refreshed.ok()) throw new Error(`Pico edu session refresh HTTP ${refreshed.status()}`);
  const { token } = await refreshed.json();
  if (!token) throw new Error('Pico edu session refresh did not return an access token.');
  return token;
}

export async function goNewChat(page, base) {
  const newUrl = new URL('/c/new', base).toString();
  await gotoRetry(page, newUrl);
  await page.waitForTimeout(800);
  const close = page.getByRole('button', { name: /close|关闭|Got it|知道了/i });
  if (await close.count()) {
    await close.first().click().catch(() => {});
  }
}

export async function sendPrompt(page, prompt) {
  const input = await messageInput(page);
  await input.waitFor({ state: 'visible', timeout: 30000 });
  await input.click();
  await input.fill(prompt);
  await page.waitForTimeout(200);
  const sendBtn = page.getByRole('button', { name: /^发送$|Send/i });
  if (await sendBtn.count()) {
    await sendBtn.first().click();
  } else {
    await input.press('Enter');
  }
}

export async function waitForTestId(page, testId, timeout = 45000) {
  const loc = page.getByTestId(testId);
  await loc.first().waitFor({ state: 'visible', timeout });
  return loc.first();
}

export async function saveViewportPng(page, filePath) {
  const img = page.getByTestId('sandbox-web-viewport');
  await img.waitFor({ state: 'visible', timeout: 45000 });
  const buf = await img.screenshot({ type: 'png' });
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, buf);
  if (buf.length < 20_000) {
    throw new Error(`viewport png too small (${buf.length}B): ${filePath}`);
  }
  return { filePath, size: buf.length };
}

export function writeJson(filePath, data) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`);
}

/** A shared downlink with propagation delay in both directions, including open SSE. */
export async function limitedSandboxLink(base) {
  const target = new URL(base);
  if (target.protocol !== 'http:' || target.hostname !== '127.0.0.1') {
    throw new Error('--limit requires a local http://127.0.0.1 stack');
  }
  const delay = 97;
  const bytesPerMs = 687.5;
  let sendAt = 0;
  const server = http.createServer((req, res) => {
    const upstream = http.request({
      hostname: target.hostname,
      port: target.port,
      method: req.method,
      path: req.url,
      headers: { ...req.headers, host: target.host },
    });
    const packets = [];
    let timer;
    function schedule() {
      if (!packets.length || res.destroyed) return;
      timer = setTimeout(() => {
        const now = performance.now();
        while (packets.length && packets[0].when <= now && !res.destroyed) {
          packets.shift().send();
        }
        timer = undefined;
        schedule();
      }, Math.max(1, packets[0].when - performance.now()));
    }
    function at(when, send) {
      packets.push({ when, send });
      if (!timer) schedule();
    }
    upstream.on('response', (incoming) => {
      let endAt = performance.now() + delay;
      at(endAt, () => res.writeHead(incoming.statusCode, incoming.headers));
      incoming.on('data', (chunk) => {
        sendAt = Math.max(sendAt, performance.now()) + chunk.length / bytesPerMs;
        endAt = sendAt + delay;
        at(endAt, () => res.write(chunk));
      });
      incoming.on('end', () => at(endAt, () => res.end()));
      incoming.on('error', (error) => res.destroy(error));
    });
    upstream.on('error', (error) => res.destroy(error));
    res.once('close', () => {
      upstream.destroy();
      clearTimeout(timer);
      packets.length = 0;
    });
    at(performance.now() + delay, () => req.pipe(upstream));
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  return {
    base: `http://127.0.0.1:${server.address().port}`,
    close() {
      server.close();
      server.closeAllConnections();
    },
  };
}
