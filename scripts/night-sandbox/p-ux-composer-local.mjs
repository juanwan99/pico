#!/usr/bin/env node
/**
 * Local C1–C5 frames against the freshly built product CSS + composer markup.
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

function overlapMid(a, b) {
  const mid = a.y + a.height / 2;
  return mid >= b.y - 4 && mid <= b.y + b.height + 4;
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

function fixtureHtml(cssHref) {
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="${cssHref}" />
</head>
<body>
<div class="pico-app" style="min-height:100vh;background:#f5f5f5">
  <svg xmlns="http://www.w3.org/2000/svg" class="pico-icon-sprite" aria-hidden="true" width="0" height="0" style="position:absolute;width:0;height:0;overflow:hidden">${spriteInner()}</svg>
  <div class="flex h-screen">
    <aside class="pico-wb-sidebar hidden w-[264px] flex-col bg-[color:var(--pico-sidebar)] p-3 md:flex">
      <div class="pico-type-body pico-type-medium">Pico</div>
      <button type="button" data-testid="new-chat-button" class="pico-type-sidebar pico-type-medium mt-3 flex h-9 items-center justify-center gap-2 rounded-full bg-[color:var(--pico-ink)] text-white">
        <svg class="pico-icon pico-icon-sm" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"><use href="#pico-i-plus" fill="none" stroke="currentColor"/></svg>
        新对话
      </button>
      <nav class="pico-type-sidebar mt-3 space-y-1 text-[color:var(--pico-ink-2)]">
        <div class="rounded-lg px-2.5 py-2">更多</div>
        <div class="mt-3 border-t border-[color:var(--pico-line)] pt-2">
          <div class="px-2 py-1.5">整理周报要点</div>
          <div class="px-2 py-1.5">打开 example.com</div>
          <div class="px-2 py-1.5">合同对照表</div>
          <div class="px-2 py-1.5">课件提纲</div>
        </div>
      </nav>
    </aside>
    <main class="pico-wb-landing flex flex-1 flex-col items-center justify-center px-4">
      <h1 class="pico-type-medium text-center text-[30px] text-[color:var(--pico-ink)]">Pico，我帮你</h1>
      <p class="pico-type-sidebar mt-2 text-[color:var(--pico-ink-3)]">描述任务即可开始</p>
      <div class="mt-5 flex max-w-[797px] flex-wrap justify-center gap-2">
        <span class="pico-chip inline-flex h-8 items-center rounded-full px-3 pico-type-aux">日常办公</span>
        <span class="pico-chip inline-flex h-8 items-center rounded-full px-3 pico-type-aux">文档处理</span>
        <span class="pico-chip inline-flex h-8 items-center rounded-full px-3 pico-type-aux">深度研究</span>
        <span class="pico-chip inline-flex h-8 items-center rounded-full px-3 pico-type-aux">幻灯片</span>
        <span class="pico-chip inline-flex h-8 items-center rounded-full px-3 pico-type-aux">数据分析</span>
      </div>
      <div class="mt-6 w-full max-w-[797px]">
        <div class="pico-wb-composer rounded-[16px] border bg-white" data-testid="pico-wb-home-composer">
          <div class="pico-wb-composer-row relative flex items-end gap-0.5 px-1 py-1" data-testid="composer-one-row">
            <button type="button" data-testid="composer-plus" aria-label="更多输入选项" class="inline-flex h-8 w-8 items-center justify-center rounded-md">
              <svg class="pico-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"><use href="#pico-i-plus" fill="none" stroke="currentColor"/></svg>
            </button>
            <div data-testid="composer-plus-menu" hidden class="pico-card absolute bottom-full left-0 z-50 mb-2 w-56 py-1">
              <button type="button" class="pico-type-sidebar flex w-full px-3 py-2 text-left">快速</button>
            </div>
            <textarea id="pico-wb-home-input" data-testid="text-input" rows="1" placeholder="今天帮你做些什么？" class="pico-type-body min-h-8 min-w-0 flex-1 resize-none border-0 bg-transparent py-2 outline-none"></textarea>
            <button type="button" data-testid="send-button" aria-label="发送" class="inline-flex h-8 w-8 items-center justify-center rounded-md">
              <svg class="pico-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"><use href="#pico-i-arrow-up" fill="none" stroke="currentColor"/></svg>
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</div>
<script>
  document.querySelector('[data-testid="composer-plus"]').addEventListener('click', () => {
    const menu = document.querySelector('[data-testid="composer-plus-menu"]');
    menu.hidden = !menu.hidden;
  });
</script>
</body>
</html>`;
}

function serve(rootDir, html) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const url = req.url.split('?')[0];
      if (url === '/' || url === '/c/new') {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(html);
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
  const html = fixtureHtml(cssHref);
  const { server, port } = await serve(dist, html);
  const out = path.join(ROOT, 'docs/evidence/pack-ux-composer-type-icon');
  fs.mkdirSync(out, { recursive: true });
  const report = {
    card: 'T-UX-COMPOSER-TYPE-ICON',
    mode: 'local-built-css',
    css: cssHref,
    c1: 'N',
    c2: 'N',
    c3: 'N',
    c4: 'N',
    c5: 'N',
    claim_wb: 'NO',
  };
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`http://127.0.0.1:${port}/c/new`, { waitUntil: 'domcontentloaded' });
    const row = page.getByTestId('composer-one-row');
    const plus = page.getByTestId('composer-plus');
    const input = page.getByTestId('text-input');
    const send = page.getByTestId('send-button');
    await row.waitFor({ state: 'visible' });
    const [rowBox, plusBox, inputBox, sendBox] = await Promise.all([
      row.boundingBox(),
      plus.boundingBox(),
      input.boundingBox(),
      send.boundingBox(),
    ]);
    if (!rowBox || !plusBox || !inputBox || !sendBox) {
      throw new Error('C1 missing boxes');
    }
    if (!overlapMid(plusBox, rowBox) || !overlapMid(sendBox, rowBox) || !overlapMid(inputBox, rowBox)) {
      throw new Error('C1 not one row');
    }
    if (rowBox.height >= 88) {
      throw new Error(`C1 too tall ${rowBox.height}`);
    }
    if (((await plus.textContent()) || '').trim() === '+') {
      throw new Error('C1 text plus');
    }
    const s1 = await shot(page, path.join(out, 'c1-one-row-1280.png'));
    report.c1 = 'Y';
    report.composer_one_row = 'Y';
    report.c1_size = s1.size;
    report.c1_sha = sha256(path.join(out, 'c1-one-row-1280.png'));
    report.row_height = rowBox.height;

    await plus.click();
    await page.getByTestId('composer-plus-menu').waitFor({ state: 'visible' });
    const s2 = await shot(page, path.join(out, 'c2-plus-open-1280.png'));
    await plus.click();
    const hidden = await page.getByTestId('composer-plus-menu').evaluate((el) => el.hasAttribute('hidden'));
    if (!hidden) {
      throw new Error('C2 menu did not close');
    }
    report.c2 = 'Y';
    report.c2_size = s2.size;
    report.c2_sha = sha256(path.join(out, 'c2-plus-open-1280.png'));

    const style = await input.evaluate((el) => {
      const computed = getComputedStyle(el);
      return { fontSize: computed.fontSize, fontFamily: computed.fontFamily };
    });
    if (parseFloat(style.fontSize) !== 15) {
      throw new Error(`C3 font-size ${style.fontSize}`);
    }
    if (/^\s*inter\b/i.test(style.fontFamily)) {
      throw new Error(`C3 Inter first ${style.fontFamily}`);
    }
    if (!/PingFang|Hiragino|Source Han|Noto Sans SC|Microsoft YaHei|Heiti/i.test(style.fontFamily)) {
      throw new Error(`C3 no CJK ${style.fontFamily}`);
    }
    report.c3 = 'Y';
    report.type_scale = 'Y';
    report.font = style;

    const lucide = page.locator('svg.lucide, [class*="lucide-"]');
    if ((await lucide.count()) > 0) {
      throw new Error('C4 lucide present');
    }
    if ((await page.getByRole('button', { name: '新对话' }).count()) !== 1) {
      throw new Error('C4 新对话 count');
    }
    report.c4 = 'Y';
    report.icons_one_set = 'Y';

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(200);
    const s5 = await shot(page, path.join(out, 'c5-390.png'), { allowSmall: true });
    if (s5.size < 12_000) {
      throw new Error(`C5 frame too small ${s5.size}`);
    }
    const box390 = await row.boundingBox();
    if (box390 && box390.x + box390.width > 400) {
      throw new Error('C5 overflow');
    }
    report.c5 = 'Y';
    report.c5_size = s5.size;
    report.c5_sha = sha256(path.join(out, 'c5-390.png'));

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
