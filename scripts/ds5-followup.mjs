// ds5-followup.mjs — send a follow-up prompt in an EXISTING conversation (same-session v2 test).
// Captures V0 (before send) / V2 (settled) frames + ledger for the new run.
// Usage:
//   set -a; source scripts/visual-gate-env.sh; set +a
//   NODE_PATH=... node scripts/ds5-followup.mjs --conv <id> --out <dir> --prompt '<v2 prompt>'
import { createRequire } from 'node:module';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const candidates = [
    path.join(ROOT, 'node_modules', 'playwright'),
    path.join(ROOT, 'apps', 'librechat', 'node_modules', 'playwright'),
    path.join(process.env.HOME || '', '.npm-global', 'lib', 'node_modules', 'playwright'),
    'playwright',
  ];
  for (const c of candidates) {
    try { return require(c); } catch { /* next */ }
  }
  throw new Error('playwright not found');
}

function parseArgs(argv) {
  const out = {
    conv: '', base: process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia',
    outDir: '', prompt: '', timeoutMs: 300000,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--conv') out.conv = next();
    else if (a === '--base') out.base = next();
    else if (a === '--out') out.outDir = next();
    else if (a === '--prompt') out.prompt = next();
    else if (a === '--timeout-ms') out.timeoutMs = Number(next());
  }
  return out;
}

const { chromium } = loadPlaywright();
const args = parseArgs(process.argv);
const email = process.env.PICO_E2E_EMAIL || process.env.DEMO_EMAIL || '';
const password = process.env.PICO_E2E_PASSWORD || process.env.DEMO_PASSWORD || '';
if (!args.conv || !args.prompt) throw new Error('--conv and --prompt required');

function ensureDir(d) { fs.mkdirSync(d, { recursive: true }); }
ensureDir(args.outDir);
const shot = async (page, file) => { await page.screenshot({ path: file, fullPage: true, type: 'png' }); return file; };

async function mainBubbleText(page) {
  const prefer = [
    '[data-testid="messages-view"] .agent-turn [data-testid="message-content"]',
    '[data-testid="messages-view"] .agent-turn .markdown',
    '[data-testid="messages-view"] .agent-turn',
    '[data-testid="message-content"]',
    '[data-testid="messages-view"] .markdown',
    '[data-testid="messages-view"]',
    'main [class*="message"]',
    'main',
  ];
  for (const sel of prefer) {
    const loc = page.locator(sel);
    const n = await loc.count();
    if (!n) continue;
    const parts = [];
    const limit = Math.min(n, 40);
    for (let i = 0; i < limit; i++) {
      const t = await loc.nth(i).innerText().catch(() => '');
      if (t && t.trim()) parts.push(t.trim());
    }
    if (parts.length) return parts.join('\n\n');
  }
  return page.locator('main').innerText().catch(() => page.locator('body').innerText().catch(() => ''));
}

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN' });
let jwt = null;
page.on('request', (req) => {
  const h = req.headers();
  if (!jwt && h['authorization'] && h['authorization'].startsWith('Bearer ')) jwt = h['authorization'].slice(7);
});

// login
await page.goto(new URL('/login', args.base).toString(), { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(800);
if (!(await page.getByRole('textbox', { name: /Message input|消息/i }).count())) {
  const emailBox = page.getByLabel(/Email|邮箱|电子邮件/i).first();
  const passBox = page.getByLabel(/Password|密码/i).first();
  if (await emailBox.count()) { await emailBox.fill(email); await passBox.fill(password); }
  else {
    await page.locator('input[type="email"], input[name="email"]').first().fill(email);
    await page.locator('input[type="password"]').first().fill(password);
  }
  const btn = page.getByTestId('login-button');
  if (await btn.count()) await btn.click();
  else await page.getByRole('button', { name: /[Ll]og ?in|登录|Sign in/i }).click();
  await page.waitForTimeout(4000);
}

// open existing conversation
await page.goto(new URL(`/c/${args.conv}`, args.base).toString(), { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(6000);

const input = page.getByRole('textbox', { name: /Message input|消息/i }).first().or(page.locator('textarea[data-testid="message-input"], textarea, [contenteditable="true"]').first());
await input.waitFor({ state: 'visible', timeout: 30000 }).catch(() => {});
await input.click();
await input.fill(args.prompt);
const v0 = await shot(page, path.join(args.outDir, 'V0-send-v2.png'));
await input.press('Enter');
await page.waitForTimeout(2000);

// wait settled
const deadline = Date.now() + args.timeoutMs;
let text = '';
while (Date.now() < deadline) {
  await page.waitForTimeout(2500);
  const t = await mainBubbleText(page);
  const done = /✅\s*已交付|已交付|Something went wrong|terminated|错误|失败|Rejected/i.test(t) &&
    !/正在准备|…|\.\.\.|思考/i.test(t);
  if (done) { text = t; break; }
}
const v2 = await shot(page, path.join(args.outDir, 'V2-final-v2.png'));
if (!text) text = await mainBubbleText(page);

// ledger: run 2 (revision) via API
let ledger = { conv: args.conv, run: null, delivery_summary: null, terminal_events: [], assistant_text: text };
if (jwt) {
  try {
    const data = await page.evaluate(async ({ token, conv }) => {
      const headers = { 'Authorization': 'Bearer ' + token };
      const r = await fetch(`/api/pico/v1/tasks?conversationId=${conv}`, { headers });
      const body = r.ok ? await r.json() : null;
      const task = body?.tasks?.[0];
      const run = task?.latest_run;
      const res = { task: task ? { id: task.id, title: task.title } : null, run: null, delivery_summary: null, terminal_events: [] };
      if (run?.id) {
        res.run = { id: run.id, status: run.status, model: run.model, error: run.error, cancel_requested: run.cancel_requested };
        const r3 = await fetch(`/api/pico/v1/runs/${run.id}/events`, { headers });
        const ev = r3.ok ? await r3.json() : null;
        const arr = Array.isArray(ev) ? ev : (ev?.events || []);
        const sums = arr.filter((e) => e && e.type === 'delivery.summary').map((e) => e.payload);
        res.delivery_summary = sums[sums.length - 1] || null;
        res.terminal_events = arr.map((e) => e.type).filter(Boolean);
        res.artifacts = arr.filter((e) => e && e.type === 'artifact.created').map((e) => e.payload).filter(Boolean)
          .map((a) => ({ title: a.title, user_label: a.user_label, kind: a.kind, artifact_id: a.artifact_id }));
      }
      return res;
    }, { token: jwt, conv: args.conv });
    ledger.run = data.run;
    ledger.delivery_summary = data.delivery_summary;
    ledger.terminal_events = data.terminal_events;
    ledger.artifacts = data.artifacts;
  } catch (e) { ledger.error = String(e); }
}
fs.writeFileSync(path.join(args.outDir, 'ledger-v2.json'), JSON.stringify(ledger, null, 2));
console.log(JSON.stringify({ conv: args.conv, v0, v2, run: ledger.run, summary: ledger.delivery_summary }, null, 2));
await browser.close();
