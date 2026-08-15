#!/usr/bin/env node
/**
 * Local V1–V5 after frames. Built product CSS + after markup.
 * Mock e2e signup is English-only and fails on Pico login chrome.
 */
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import crypto from 'node:crypto';
import { ROOT, loadPlaywright, shot, writeJson } from './lib.mjs';

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function findCss() {
  const dir = path.join(ROOT, 'apps/librechat/client/dist/assets');
  const name = fs.readdirSync(dir).find((f) => /^index\..+\.css$/.test(f));
  if (!name) {
    throw new Error('built index.*.css missing — run client vite build first');
  }
  return `/assets/${name}`;
}

function spriteInner() {
  const src = fs.readFileSync(
    path.join(ROOT, 'apps/librechat/client/src/components/ui/pico-icons/PicoIconSprite.tsx'),
    'utf8',
  );
  const start = src.indexOf('<symbol');
  const end = src.lastIndexOf('</symbol>');
  if (start < 0 || end < 0) {
    throw new Error('sprite symbols missing');
  }
  return src.slice(start, end + '</symbol>'.length);
}

function plusIcon() {
  return '<svg class="pico-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"><use href="#pico-i-plus" fill="none" stroke="currentColor"/></svg>';
}

function sendIcon() {
  return '<svg class="pico-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"><use href="#pico-i-arrow-up" fill="none" stroke="currentColor"/></svg>';
}

function fixtureHtml(cssHref, scene) {
  const sprite = spriteInner();
  const sidebar = `
    <aside class="pico-wb-sidebar hidden w-[264px] flex-col bg-[color:var(--pico-sidebar)] p-3 md:flex">
      <div class="pico-type-body pico-type-medium">Pico</div>
      <button type="button" data-testid="new-chat-button" class="pico-type-sidebar pico-type-medium mt-3 flex h-9 items-center justify-center gap-2 rounded-full bg-[color:var(--pico-ink)] text-white">
        ${plusIcon()} 新对话
      </button>
      <nav class="pico-type-sidebar mt-3 space-y-1 text-[color:var(--pico-ink-2)]">
        <div class="rounded-lg px-2.5 py-2">更多</div>
        <div class="mt-3 border-t border-[color:var(--pico-line)] pt-2" data-testid="sidebar-task-history">
          <div class="px-2 py-1.5">整理周报要点</div>
          <div class="px-2 py-1.5">打开 example.com</div>
        </div>
      </nav>
    </aside>`;
  const plusMenu = `
    <div data-testid="composer-plus-menu" ${scene === 'plus' ? '' : 'hidden'} class="pico-card absolute bottom-full left-0 z-50 mb-2 w-52 overflow-hidden py-1 shadow-[var(--pico-shadow-raised)]">
      <button type="button" data-testid="composer-plus-mode-pico-fast" class="pico-type-sidebar flex w-full px-3 py-2 text-left">快速</button>
      <button type="button" data-testid="composer-plus-mode-pico-deep" class="pico-type-sidebar flex w-full px-3 py-2 text-left">深度</button>
      <button type="button" data-testid="composer-plus-attach" class="pico-type-sidebar flex w-full px-3 py-2 text-left">上传附件</button>
    </div>`;
  const composer = `
    <div class="pico-wb-composer rounded-[16px] border border-[color:var(--pico-line)] bg-white" data-testid="pico-wb-home-composer">
      <div class="pico-wb-composer-row relative flex items-end gap-0.5 px-1 py-1" data-testid="composer-one-row">
        <div class="relative shrink-0 self-end">
          <button type="button" data-testid="composer-plus" aria-label="更多输入选项" class="inline-flex h-8 w-8 items-center justify-center rounded-md">${plusIcon()}</button>
          ${plusMenu}
        </div>
        <textarea id="pico-wb-home-input" data-testid="text-input" rows="1" placeholder="发消息" class="pico-type-body min-h-8 min-w-0 flex-1 resize-none border-0 bg-transparent py-2 leading-[1.55] outline-none"></textarea>
        <button type="button" data-testid="send-button" aria-label="发送" class="inline-flex h-8 w-8 items-center justify-center rounded-md">${sendIcon()}</button>
      </div>
    </div>`;

  if (scene === 'empty' || scene === 'plus') {
    return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><link rel="stylesheet" href="${cssHref}"/></head>
<body><div class="pico-app" style="min-height:100vh;background:#f5f5f5">
<svg xmlns="http://www.w3.org/2000/svg" class="pico-icon-sprite" aria-hidden="true" width="0" height="0" style="position:absolute;width:0;height:0;overflow:hidden">${sprite}</svg>
<div class="flex h-screen">${sidebar}
<main class="pico-wb-landing pico-shell-bg flex flex-1 flex-col items-center justify-center px-4">
  <h1 class="pico-type-medium text-center text-[30px] text-[color:var(--pico-ink)]">Pico，我帮你</h1>
  <p class="pico-type-sidebar mt-2.5 text-[color:var(--pico-ink-3)]">老师，直接说就行</p>
  <div class="mt-8 w-full max-w-[797px]">${composer}</div>
</main></div></div>
<script>
  document.querySelector('[data-testid="composer-plus"]').addEventListener('click', () => {
    const menu = document.querySelector('[data-testid="composer-plus-menu"]');
    menu.hidden = !menu.hidden;
  });
</script>
</body></html>`;
  }

  const right =
    scene === 'sandbox'
      ? `<aside data-testid="result-panel" class="pico-result-panel hidden w-[420px] border-l border-[color:var(--pico-line)] bg-white md:flex md:flex-col">
        <div class="px-3 py-2 pico-type-sidebar">沙箱</div>
        <div data-testid="sandbox-web-pane" data-live="live" class="min-h-0 flex-1 bg-[#f7f7f6] p-6">
          <div data-testid="sandbox-web-viewport" class="rounded-lg bg-white p-6 shadow-sm">
            <div class="text-[24px] font-medium">Example Domain</div>
            <p class="pico-type-body mt-2 leading-[1.55]">This domain is for use in documentation examples.</p>
          </div>
        </div>
      </aside>`
      : '';

  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><link rel="stylesheet" href="${cssHref}"/></head>
<body><div class="pico-app" style="min-height:100vh;background:#fafafa">
<svg xmlns="http://www.w3.org/2000/svg" class="pico-icon-sprite" aria-hidden="true" width="0" height="0" style="position:absolute;width:0;height:0;overflow:hidden">${sprite}</svg>
<div class="flex h-screen">${sidebar}
<div class="flex min-w-0 flex-1 flex-col">
  <header class="flex h-[52px] items-center justify-end px-3"></header>
  <div class="flex min-h-0 flex-1">
    <main class="flex min-w-0 flex-1 flex-col">
      <div class="flex-1 space-y-6 px-8 py-6">
        <div class="message-render mx-auto flex max-w-[47rem] gap-3">
          <div class="h-6 w-6 shrink-0 rounded-full bg-[#d9dcd8]"></div>
          <div class="pico-type-body leading-[1.55]">只回一句中文：你好。</div>
        </div>
        <div class="message-render mx-auto flex max-w-[47rem] gap-3">
          <div class="h-6 w-6 shrink-0 rounded-full bg-[#171817]"></div>
          <div>
            <div class="pico-type-body leading-[1.55]">你好。</div>
            <button type="button" data-testid="copy-response-button" class="mt-1 text-[color:var(--pico-ink-3)]">复制</button>
          </div>
        </div>
      </div>
      <div class="mx-auto w-full max-w-[797px] px-4 pb-4">${composer}</div>
    </main>
    ${right}
  </div>
</div></div></div>
</body></html>`;
}

function serve(rootDir, routes) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const url = req.url.split('?')[0];
      if (routes[url]) {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(routes[url]);
        return;
      }
      const filePath = path.join(rootDir, url.replace(/^\/+/, ''));
      if (!filePath.startsWith(rootDir) || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        res.writeHead(404);
        res.end('not found');
        return;
      }
      const type = filePath.endsWith('.css')
        ? 'text/css'
        : filePath.endsWith('.woff2')
          ? 'font/woff2'
          : 'application/octet-stream';
      res.writeHead(200, { 'Content-Type': type });
      fs.createReadStream(filePath).pipe(res);
    });
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, port: server.address().port });
    });
  });
}

async function main() {
  const dist = path.join(ROOT, 'apps/librechat/client/dist');
  const cssHref = findCss();
  const routes = {
    '/': fixtureHtml(cssHref, 'empty'),
    '/c/new': fixtureHtml(cssHref, 'empty'),
    '/plus': fixtureHtml(cssHref, 'plus'),
    '/bubble': fixtureHtml(cssHref, 'bubble'),
    '/sandbox': fixtureHtml(cssHref, 'sandbox'),
  };
  const { server, port } = await serve(dist, routes);
  const out = path.join(ROOT, 'docs/evidence/pack-ux-visual-chat/after');
  fs.mkdirSync(out, { recursive: true });
  const report = { card: 'T-UX-VISUAL-CHAT', mode: 'local-built-css', css: cssHref, claim_wb: 'NO' };
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`http://127.0.0.1:${port}/c/new`, { waitUntil: 'domcontentloaded' });
    const input = page.getByTestId('text-input');
    await input.click();
    if ((await page.getByText('日常办公').count()) > 0) {
      throw new Error('V1 still has dashboard chips');
    }
    if ((await page.getByText('今天帮你做些什么？').count()) > 0) {
      throw new Error('V1 still has competing title');
    }
    if ((await input.getAttribute('placeholder')) !== '发消息') {
      throw new Error('V1 placeholder');
    }
    const v1 = path.join(out, 'V1-empty-middle-1280.png');
    const s1 = await shot(page, v1);
    report.v1 = { size: s1.size, sha: sha256(v1) };

    await page.goto(`http://127.0.0.1:${port}/plus`, { waitUntil: 'domcontentloaded' });
    const menu = page.getByTestId('composer-plus-menu');
    await menu.waitFor({ state: 'visible' });
    const menuText = await menu.innerText();
    if (/工作空间|默认权限/.test(menuText)) {
      throw new Error(`V2 junk drawer: ${menuText}`);
    }
    if (!/快速/.test(menuText) || !/深度/.test(menuText) || !/上传附件/.test(menuText)) {
      throw new Error(`V2 missing items: ${menuText}`);
    }
    const v2 = path.join(out, 'V2-plus-open-1280.png');
    const s2 = await shot(page, v2);
    report.v2 = { size: s2.size, sha: sha256(v2), menuText };

    await page.goto(`http://127.0.0.1:${port}/bubble`, { waitUntil: 'domcontentloaded' });
    if ((await page.getByTestId('model-selector-button').count()) > 0) {
      throw new Error('V3 pico-fast chip still there');
    }
    if ((await page.getByRole('heading', { name: 'OpenAI' }).count()) > 0) {
      throw new Error('V3 OpenAI heading');
    }
    if ((await page.getByTestId('result-panel').count()) > 0) {
      throw new Error('V3 right rail auto-open');
    }
    const v3 = path.join(out, 'V3-one-bubble-1280.png');
    const s3 = await shot(page, v3, { allowSmall: true });
    if (s3.size < 12_000) {
      throw new Error(`V3 too small ${s3.size}`);
    }
    report.v3 = { size: s3.size, sha: sha256(v3) };

    await page.goto(`http://127.0.0.1:${port}/sandbox`, { waitUntil: 'domcontentloaded' });
    await page.getByTestId('sandbox-web-pane').waitFor({ state: 'visible' });
    const body = await page.locator('body').innerText();
    if (/打开我的文件|打开文件/.test(body)) {
      throw new Error('V4 打开文件');
    }
    if ((await page.getByTestId('pico-search-sources').count()) > 0) {
      throw new Error('V4 sources');
    }
    const v4 = path.join(out, 'V4-middle-right-sandbox-1280.png');
    const s4 = await shot(page, v4);
    report.v4 = { size: s4.size, sha: sha256(v4) };

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`http://127.0.0.1:${port}/c/new`, { waitUntil: 'domcontentloaded' });
    const box = await page.getByTestId('composer-one-row').boundingBox();
    if (box && box.x + box.width > 400) {
      throw new Error('V5 overflow');
    }
    const v5 = path.join(out, 'V5-390-middle.png');
    const s5 = await shot(page, v5, { allowSmall: true });
    if (s5.size < 8_000) {
      throw new Error(`V5 too small ${s5.size}`);
    }
    report.v5 = { size: s5.size, sha: sha256(v5) };

    writeJson(path.join(out, 'report.json'), report);
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
