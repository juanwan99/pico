#!/usr/bin/env node
/**
 * Live persist: teacher JWT → sandbox API (same as 打开), not LLM wait.
 * T1 before/after destroy, T2 reopen Writer. Frames must differ from local fixtures.
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
  ensureDir,
  writeJson,
} from './lib.mjs';

loadEvidenceEnv();

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

async function shotPage(page, filePath) {
  ensureDir(path.dirname(filePath));
  await page.screenshot({ path: filePath, type: 'png', fullPage: true });
  const size = fs.statSync(filePath).size;
  if (size < 20_000) throw new Error(`frame too small (${size}B): ${filePath}`);
  return { filePath, size, sha: sha256(filePath) };
}

async function pico(page, method, urlPath, body) {
  return page.evaluate(
    async ({ method, urlPath, body }) => {
      const headers = { Accept: 'application/json' };
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      const bearer = window.__PICO_BEARER;
      if (bearer) headers.Authorization = bearer;
      const res = await fetch(`/api/pico${urlPath}`, {
        method,
        credentials: 'include',
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      const text = await res.text();
      let json = null;
      try {
        json = JSON.parse(text);
      } catch {
        json = { raw: text.slice(0, 300) };
      }
      return { status: res.status, json };
    },
    { method, urlPath, body },
  );
}

async function showStage(page, title, color, lines, imgB64) {
  const lis = lines.map((l) => `<p style="font-size:20px">${l}</p>`).join('');
  const img = imgB64
    ? `<img alt="sandbox" src="data:image/png;base64,${imgB64}" style="max-width:100%;border:1px solid #333"/>`
    : '';
  await page.setContent(`<!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>${title}</title></head>
    <body style="margin:0;font-family:sans-serif;background:${color}">
      <header style="padding:18px 24px;background:#111;color:#fff;font-size:26px">${title}</header>
      <main style="margin:16px;padding:20px;background:#fff;min-height:620px;border:2px solid #111">
        ${lis}${img}
      </main>
    </body></html>`);
}

async function pngB64(page, sessionId) {
  return page.evaluate(async (sessionId) => {
    const res = await fetch(`/api/pico/v1/sandbox/sessions/${sessionId}/screenshot`, {
      credentials: 'include',
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`shot ${res.status}`);
    const buf = await res.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let bin = '';
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin);
  }, sessionId);
}

async function main() {
  const base = process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia';
  const out = process.env.PICO_PERSIST_OUT || path.join(ROOT, 'docs/evidence/pack-sandbox-persist/live');
  const expectTip = process.env.PICO_EXPECT_TIP || '';
  const { email, password } = emailPass();
  if (!email || !password) throw new Error('DEMO_EMAIL missing');
  const unique = `persist-${Date.now()}.docx`;
  const marker = `PERSIST-${Date.now()}`;
  const tip = await fetchTip(base);
  if (expectTip && tip.git_sha !== expectTip) {
    throw new Error(`tip ${tip.git_sha} != ${expectTip}`);
  }
  const report = {
    card: 'T-SANDBOX-PERSIST-SHIP',
    base,
    tip,
    unique,
    marker,
    t1: 'N',
    t2: 'N',
    t3: 'N',
    t4: tip.git_sha ? 'Y' : 'N',
    claim_wb: 'NO',
  };
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
    let bearer = '';
    page.on('response', async (res) => {
      try {
        if (!/\/api\/auth\/(login|refresh)/.test(res.url())) return;
        const json = await res.json();
        const tok = json?.token || json?.access_token;
        if (typeof tok === 'string' && tok.length > 20) bearer = tok;
      } catch {
        /* ignore */
      }
    });
    await login(page, base, email, password);
    await goNewChat(page, base);
    if (!bearer) {
      bearer = await page.evaluate(() => {
        try {
          const raw = localStorage.getItem('token') || localStorage.getItem('authToken') || '';
          return raw;
        } catch {
          return '';
        }
      });
    }
    if (bearer) {
      await page.addInitScript((tok) => {
        window.__PICO_BEARER = tok;
      }, bearer.startsWith('Bearer ') ? bearer : `Bearer ${bearer}`);
      await page.evaluate((tok) => {
        window.__PICO_BEARER = tok;
      }, bearer.startsWith('Bearer ') ? bearer : `Bearer ${bearer}`);
    }

    const opened = await pico(page, 'POST', '/v1/sandbox/sessions', {
      kind: 'writer',
      filename: unique,
      body: marker,
    });
    if (opened.status !== 200 || !String(opened.json?.session_id || '').startsWith('sbox_')) {
      throw new Error(`open writer failed ${opened.status} ${JSON.stringify(opened.json).slice(0, 240)}`);
    }
    const sid1 = opened.json.session_id;
    const names1 = (opened.json.files || []).map((f) => f.name);
    if (!names1.includes(unique)) {
      throw new Error(`T1 open missing ${unique}: ${JSON.stringify(names1)}`);
    }
    const files1 = await pico(page, 'POST', `/v1/sandbox/sessions/${sid1}/focus`, { kind: 'files' });
    if (files1.status !== 200) throw new Error(`focus files ${files1.status}`);
    const shot1 = await pngB64(page, sid1);
    await showStage(
      page,
      'LIVE T1 BEFORE DESTROY',
      '#1d4ed8',
      [`file ${unique}`, `session ${sid1}`, `files ${names1.join(',')}`],
      shot1,
    );
    const f1 = await shotPage(page, path.join(out, 't1-before-destroy.png'));
    report.t1_before = f1;

    const closed = await pico(page, 'DELETE', `/v1/sandbox/sessions/${sid1}`);
    if (closed.status !== 200 || closed.json?.persist !== true) {
      throw new Error(`destroy ${closed.status} ${JSON.stringify(closed.json).slice(0, 200)}`);
    }
    const gone = await pico(page, 'GET', `/v1/sandbox/sessions/${sid1}`);
    if (gone.status !== 404) throw new Error(`expected 404 after destroy got ${gone.status}`);

    const files2 = await pico(page, 'POST', '/v1/sandbox/sessions', { kind: 'files' });
    if (files2.status !== 200) throw new Error(`reopen files ${files2.status} ${JSON.stringify(files2.json).slice(0, 200)}`);
    const sid2 = files2.json.session_id;
    if (sid2 === sid1) throw new Error('new session reused destroyed id');
    const names2 = (files2.json.files || []).map((f) => f.name);
    if (!names2.includes(unique)) {
      throw new Error(`T1 after destroy missing ${unique}: ${JSON.stringify(names2)}`);
    }
    const shot2 = await pngB64(page, sid2);
    await showStage(
      page,
      'LIVE T1 AFTER DESTROY',
      '#15803d',
      [`file still ${unique}`, `old ${sid1} gone`, `new ${sid2}`],
      shot2,
    );
    const f1b = await shotPage(page, path.join(out, 't1-after-destroy.png'));
    report.t1 = 'Y';
    report.t1_after = f1b;

    const reopen = await pico(page, 'POST', '/v1/sandbox/sessions', {
      kind: 'writer',
      filename: unique,
    });
    if (reopen.status !== 200) {
      throw new Error(`reopen writer ${reopen.status} ${JSON.stringify(reopen.json).slice(0, 240)}`);
    }
    const sid3 = reopen.json.session_id;
    const shot3 = await pngB64(page, sid3);
    await showStage(
      page,
      'LIVE T2 WRITER REOPEN',
      '#f59e0b',
      [`Writer ${unique}`, `marker ${marker}`, `title ${reopen.json.title || ''}`],
      shot3,
    );
    const f2 = await shotPage(page, path.join(out, 't2-writer.png'));
    report.t2 = 'Y';
    report.t2_frame = f2;

    const hashes = [f1.sha, f1b.sha, f2.sha];
    if (new Set(hashes).size !== hashes.length) {
      throw new Error(`live frames not distinct: ${hashes.join(' ')}`);
    }
    report.hashes = { t1_before: f1.sha, t1_after: f1b.sha, t2: f2.sha };
    report.verdict = 'PASS';
  } catch (err) {
    report.verdict = 'FAIL';
    report.error = String(err?.message || err);
    throw err;
  } finally {
    writeJson(path.join(out, 'REPORT.json'), report);
    await browser.close();
  }
  console.log(JSON.stringify(report, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
