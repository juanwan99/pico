#!/usr/bin/env node
/** Measure what the teacher sees in the sandbox pane. Use a dedicated test teacher. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { gzipSync } from 'node:zlib';
import {
  ROOT,
  emailPass,
  fetchTip,
  goNewChat,
  limitedSandboxLink,
  loadPlaywright,
  login,
  loginWithEdu,
  sendPrompt,
  writeJson,
} from './lib.mjs';

const STAGE = '[data-testid="sandbox-web-stage"]';
const IMAGE = '[data-testid="sandbox-web-viewport"]';
const FULLSCREEN = '[data-testid="result-panel-fullscreen"]';
const DPR = 1.5;
const WIDTH = 1920;
const HEIGHT = 1080;
const SCROLL_MS = 8000;
const WINDOW = { width: 2000, height: 1210 };
const CROP = [24, 380, 2706, 240];
const MAX_ATTEMPTS = 3;

class FixtureUnavailable extends Error {}

function watchPane({ image, fullscreen }) {
  const now = () => performance.timeOrigin + performance.now();
  const requests = [];
  const frames = [];
  const arrivals = new Map();
  const signature = (src) => `${src.length}:${src.slice(-64)}`;
  window.sandboxLatency = { requests, frames, clicks: [] };
  document.addEventListener(
    'click',
    (event) => {
      if (event.target.closest(image)) window.sandboxLatency.clicks.push(now());
      if (event.target.closest(fullscreen))
        window.sandboxLatency.maximizeAt = now();
    },
    true,
  );

  const fetchPage = window.fetch;
  window.fetch = async (url, opts) => {
    if (typeof url === 'string' && url.endsWith('/input')) {
      const body = JSON.parse(opts.body);
      if (!body.frame_ack) requests.push({ at: now(), ...body });
    }
    const res = await fetchPage(url, opts);
    if (
      typeof url !== 'string' ||
      !url.includes('/stream?') ||
      !res.ok ||
      !res.body
    )
      return res;
    let buffer = '';
    const decoder = new TextDecoder();
    const body = res.body.pipeThrough(
      new TransformStream({
        transform(chunk, controller) {
          buffer += decoder.decode(chunk, { stream: true });
          const events = buffer.split('\n\n');
          buffer = events.pop();
          for (const event of events) {
            const { jpeg, width, height } = JSON.parse(event.slice(6));
            if (jpeg)
              arrivals.set(signature(`data:image/jpeg;base64,${jpeg}`), {
                at: now(),
                width,
                height,
              });
          }
          controller.enqueue(chunk);
        },
      }),
    );
    return new Response(body, { status: res.status, headers: res.headers });
  };

  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const pixels = canvas.getContext('2d', { willReadFrequently: true });
  let lastSource;
  new MutationObserver(async () => {
    const img = document.querySelector(image);
    const src = img?.getAttribute('src');
    if (!src?.startsWith('data:image/jpeg') || src === lastSource) return;
    lastSource = src;
    const sig = signature(src);
    const arrival = arrivals.get(sig);
    if (!arrival) return;
    arrivals.delete(sig);
    await img.decode();
    if (img.getAttribute('src') !== src) return;
    const at = now();
    const { width, height } = arrival;
    const pixel = (x, y) => {
      pixels.drawImage(
        img,
        (x * img.naturalWidth) / width,
        (y * img.naturalHeight) / height,
        1,
        1,
        0,
        0,
        1,
        1,
      );
      return pixels.getImageData(0, 0, 1, 1).data;
    };
    const button = pixel(30, 24);
    const layout = pixel(width - 35, 20);
    let scroll = 0;
    for (let i = 0; i < 10; i++) {
      if (pixel(487 + 14 * i, 20)[0] < 128) scroll |= 1 << i;
    }
    frames.push({
      at,
      arrival: arrival.at,
      sig,
      width,
      height,
      scroll,
      natural: [img.naturalWidth, img.naturalHeight],
      ready: button[2] > 140 && button[1] < 105,
      clicked: button[1] > 105 && button[2] < 95,
      wide: layout[1] > 90 && layout[0] < 45,
    });
  }).observe(document, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['src'],
  });
}

export async function measurePane(page, maximize, { out, getReference, run }) {
  const img = page.locator(IMAGE);
  const wait = { polling: 25, timeout: 15000 };
  try {
    await page.waitForFunction(
      () =>
        window.sandboxLatency.frames.some(
          (f) => f.ready && f.width === 720 && f.height === 700 && f.natural[0] === 1080,
        ),
      null,
      { ...wait, timeout: 60000 },
    );
  } catch (error) {
    if (error.name !== 'TimeoutError') throw error;
    throw new FixtureUnavailable('Sandbox test page did not render within 60 s.', { cause: error });
  }
  await img.click({ position: { x: 30, y: 24 } });
  await page.waitForFunction(
    () =>
      window.sandboxLatency.frames.some(
        (f) =>
          f.at >= window.sandboxLatency.clicks.at(-1) &&
          f.clicked &&
          f.natural[0] === 1080,
      ),
    null,
    wait,
  );
  const click = await page.evaluate(() => {
    const { clicks, frames, requests } = window.sandboxLatency;
    const at = clicks.at(-1);
    const frame = frames.find((f) => f.at >= at && f.clicked);
    return {
      at,
      frame,
      request: requests.find((r) => r.at >= at && r.click_x != null),
      ms: frame.at - at,
    };
  });

  await maximize();
  await page.waitForFunction(
    () => {
      const { frames, maximizeAt } = window.sandboxLatency;
      return frames.some(
        (f) =>
          f.at >= maximizeAt &&
          f.natural[0] === 2880 &&
          f.natural[1] === 1620 &&
          f.width === 1920 &&
          f.height === 1080 &&
          f.wide,
      );
    },
    null,
    wait,
  );
  const max = await page.evaluate(
    (image) => {
      const { frames, requests, maximizeAt } = window.sandboxLatency;
      const frame = frames.find(
        (f) => f.at >= maximizeAt && f.natural[0] === 2880 && f.wide,
      );
      const request = requests.find(
        (r) => r.at >= maximizeAt && r.viewport_width === 1920,
      );
      return {
        frame,
        request,
        ms: frame.at - maximizeAt,
        jpeg: document.querySelector(image).getAttribute('src').split(',')[1],
      };
    },
    IMAGE,
  );
  if (getReference) {
    const reference = await getReference();
    max.rms = await page.evaluate(async ({ jpeg, reference, crop }) => {
      const shown = new Image();
      shown.src = `data:image/jpeg;base64,${jpeg}`;
      const png = new Image();
      png.src = `data:image/png;base64,${reference}`;
      await Promise.all([shown.decode(), png.decode()]);
      const [x, y, width, height] = crop;
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(shown, -x, -y);
      const pixels = ctx.getImageData(0, 0, width, height).data;
      ctx.drawImage(png, -x, -y);
      const truth = ctx.getImageData(0, 0, width, height).data;
      let error = 0;
      for (let i = 0; i < pixels.length; i += 4) {
        for (let channel = 0; channel < 3; channel++)
          error += (pixels[i + channel] - truth[i + channel]) ** 2;
      }
      return Math.sqrt(error / (width * height * 3));
    }, { jpeg: max.jpeg, reference, crop: CROP });
  }
  const jpeg = Buffer.from(max.jpeg, 'base64');
  await fs.writeFile(path.join(out, `clear-${run}.jpg`), jpeg);
  max.jpegKiB = jpeg.length / 1024;
  max.gzipKiB = gzipSync(max.jpeg, { level: 1 }).length / 1024;
  delete max.jpeg;

  await img.hover({ position: { x: 400, y: 240 } });
  const start = await page.evaluate(
    () => performance.timeOrigin + performance.now(),
  );
  const deadline = performance.now() + SCROLL_MS;
  while (performance.now() < deadline) {
    await page.mouse.wheel(0, 105);
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  const scroll = await page.evaluate(
    ({ start, duration }) => {
      const { frames, requests } = window.sandboxLatency;
      const shown = frames.filter(
        (f) => f.at >= start && f.at <= start + duration,
      );
      const first = frames.findLast((f) => f.at < start).scroll;
      const changed = shown.filter(
        (f, i) => f.scroll !== (i ? shown[i - 1].scroll : first),
      );
      return {
        fps: (changed.length * 1000) / duration,
        frames: changed,
        requests: requests.filter((r) => r.at >= start && r.scroll_dy != null),
      };
    },
    { start, duration: SCROLL_MS },
  );
  return { click, max, scroll };
}

export async function captureReference(gold) {
  await gold.locator('section span').first().waitFor();
  await gold.evaluate(() => document.fonts.ready);
  const context = gold.context();
  const browserCdp = await context.browser().newBrowserCDPSession();
  const metrics = await context.newCDPSession(gold);
  const pageCdp = await context.newCDPSession(gold);
  const { screenInfo } = await browserCdp.send('Emulation.addScreen', {
    left: 3840,
    top: 0,
    width: 3840,
    height: 2400,
    devicePixelRatio: DPR,
  });
  return await withCleanup(async () => {
    const { windowId } = await metrics.send('Browser.getWindowForTarget');
    await metrics.send('Browser.setWindowBounds', {
      windowId,
      bounds: { left: screenInfo.left, top: 0 },
    });
    async function raster(width, height) {
      await metrics.send('Emulation.setDeviceMetricsOverride', {
        width,
        height,
        deviceScaleFactor: DPR,
        mobile: false,
      });
      const { data } = await pageCdp.send('Page.captureScreenshot', {
        format: 'png',
      });
      const header = Buffer.from(data.slice(0, 32), 'base64');
      if (
        header.readUInt32BE(16) !== width * DPR ||
        header.readUInt32BE(20) !== height * DPR
      ) {
        throw new Error('PNG reference has the wrong DPR or viewport');
      }
      return data;
    }
    await raster(720, 700);
    return await raster(WIDTH, HEIGHT);
  }, async () => {
    await pageCdp.detach();
    await metrics.detach();
    await browserCdp.send('Emulation.removeScreen', {
      screenId: screenInfo.id,
    });
    await browserCdp.detach();
  });
}

async function withCleanup(run, cleanup) {
  let completed = false;
  try {
    const result = await run();
    completed = true;
    return result;
  } finally {
    try {
      await cleanup();
    } catch (error) {
      if (completed) throw error;
      console.error('Sandbox latency cleanup failed:', error);
    }
  }
}

async function hasOpenDesk(sessions, headers) {
  const current = await fetch(`${sessions}/current`, { headers });
  if (current.ok) return true;
  if (current.status === 404 && (await current.json()).detail?.code === 'sandbox.session_not_found') {
    return false;
  }
  throw new Error(`sandbox current HTTP ${current.status}`);
}

async function requireEmptyDesk(sessions, headers) {
  if (await hasOpenDesk(sessions, headers)) {
    throw new Error('The test teacher already has an open sandbox desk.');
  }
}

async function closeDesks(sessions, headers, ids) {
  for (const id of ids) {
    const closed = await fetch(`${sessions}/${id}`, { method: 'DELETE', headers });
    if (!closed.ok) throw new Error(`sandbox cleanup HTTP ${closed.status}`);
  }
  if (await hasOpenDesk(sessions, headers)) {
    throw new Error('A sandbox desk remains open after round cleanup.');
  }
}

export async function collectChatDesks(page, base, headers, ids) {
  // The public `current` route returns the alias as its session_id. Use the
  // same sandbox.session events that mount the pane to get the concrete IDs.
  await page.getByTestId('task-stop-button').waitFor({ state: 'detached', timeout: 60000 });
  const conversationId = new URL(page.url()).pathname.split('/').at(-1);
  if (conversationId === 'new') return;
  async function read(route) {
    const response = await fetch(`${base}/api/pico/v1${route}`, { headers });
    if (!response.ok) throw new Error(`sandbox ledger HTTP ${response.status} (${route})`);
    return response.json();
  }
  const { tasks } = await read(`/tasks?conversation_id=${encodeURIComponent(conversationId)}`);
  for (const task of tasks) {
    const { runs } = await read(`/tasks/${task.id}/runs`);
    for (const run of runs) {
      const { events } = await read(`/runs/${run.id}/events`);
      for (const { type, payload } of events) {
        if (type === 'sandbox.session') ids.add(payload.session_id);
      }
    }
  }
}

export async function measureRound({
  sessions, headers, fixtureUrl, prepare, measure, collectDesks, onRetry,
}) {
  for (let attempt = 1; ; attempt++) {
    await requireEmptyDesk(sessions, headers);
    await prepare();
    const ids = new Set();
    let cleaned = false;
    try {
      return await withCleanup(async () => {
        const response = await fetch(sessions, {
          method: 'POST',
          headers: { ...headers, 'content-type': 'application/json' },
          body: JSON.stringify({ url: fixtureUrl }),
        });
        if (response.status === 400 && (await response.json()).detail?.code === 'sandbox.fetch_failed') {
          throw new FixtureUnavailable('sandbox open HTTP 400 (sandbox.fetch_failed)');
        }
        if (!response.ok) throw new Error(`sandbox open HTTP ${response.status}`);
        const { session_id: id } = await response.json();
        ids.add(id);
        return await measure();
      }, async () => {
        await withCleanup(async () => {
          if (ids.size) await collectDesks(ids);
        }, () => closeDesks(sessions, headers, ids));
        cleaned = true;
      });
    } catch (error) {
      if (!cleaned || !(error instanceof FixtureUnavailable) || attempt === MAX_ATTEMPTS) {
        throw error;
      }
      onRetry(attempt, error);
    }
  }
}

async function loginWithEmail(page, base, { email, password }) {
  const [loggedIn] = await Promise.all([
    page.waitForResponse((res) =>
      res.url() === `${base}/api/auth/login` && res.request().method() === 'POST',
    ),
    login(page, base, email, password),
  ]);
  if (!loggedIn.ok()) throw new Error(`sandbox login HTTP ${loggedIn.status()}`);
  const { token } = await loggedIn.json();
  return token;
}

async function main() {
  const { values: args } = parseArgs({
    options: {
      'base-url': { type: 'string', default: 'http://127.0.0.1:3090' },
      'fixture-url': { type: 'string' },
      'edu-login': { type: 'string' },
      'edu-base': { type: 'string', default: 'https://edu.weiyuji.cn' },
      'edu-school': { type: 'string' },
      'print-fixture': { type: 'boolean' },
      limit: { type: 'boolean' },
    },
  });
  if (args['print-fixture']) {
    const fixture = await fs.readFile(new URL('./sandbox-latency-fixture.html', import.meta.url));
    process.stdout.write(fixture);
    return;
  }
  if (!args['fixture-url']) {
    throw new Error(
      'Serve --print-fixture at an HTTPS URL and pass --fixture-url.',
    );
  }
  const fixture = new URL(args['fixture-url']);
  // The chat treats bare *.html URLs as files. Keep supplied query strings intact.
  if (!fixture.search) fixture.searchParams.set('pico-latency', '1');
  const fixtureUrl = fixture.href;
  const eduLogin = args['edu-login'];
  const emailCredentials = eduLogin === undefined ? emailPass() : null;
  if (emailCredentials && (!emailCredentials.email || !emailCredentials.password))
    throw new Error('Set PICO_E2E_EMAIL and PICO_E2E_PASSWORD.');
  const out = path.join(ROOT, '.gpt-out', 'sandbox-latency');
  await fs.mkdir(out, { recursive: true });
  const { chromium } = loadPlaywright();
  const target = new URL(args['base-url']);
  const local = ['127.0.0.1', 'localhost', '[::1]'].includes(target.hostname);
  const link = args.limit ? await limitedSandboxLink(args['base-url']) : null;
  let browser;
  await withCleanup(async () => {
    browser = await chromium.launch({
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
      args: [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-lcd-text',
        '--hide-scrollbars',
      ],
    });
    const base = link?.base || target.origin;
    const tip = await fetchTip(base);

    const page = await browser.newPage({
      viewport: WINDOW,
      deviceScaleFactor: DPR,
    });
    const token = emailCredentials
      ? await loginWithEmail(page, base, emailCredentials)
      : await loginWithEdu(page, base, {
        eduBase: args['edu-base'],
        school: args['edu-school'],
        loginName: eduLogin,
      });
    const headers = { authorization: `Bearer ${token}` };
    const sessions = `${base}/api/pico/v1/sandbox/sessions`;
    await requireEmptyDesk(sessions, headers);

    let reference;
    if (local) {
      const gold = await browser.newPage({ viewport: { width: 1280, height: 800 } });
      reference = await withCleanup(async () => {
        await gold.goto(fixtureUrl);
        return await captureReference(gold);
      }, () => gold.close());
      await fs.writeFile(path.join(out, 'reference.png'), Buffer.from(reference, 'base64'));
    }
    await page.addInitScript(watchPane, {
      image: IMAGE,
      fullscreen: FULLSCREEN,
    });
    const report = {
      tip,
      limited: args.limit,
      referencePixels: local ? 'native' : undefined,
      fixtureUrl,
      runs: [],
      retries: [],
      medianFps: null,
      pass: false,
    };
    await withCleanup(async () => {
      for (let run = 1; run <= 3; run++) {
        report.retries.push(0);
        const result = await measureRound({
          sessions,
          headers,
          fixtureUrl,
          prepare: async () => {
            await goNewChat(page, base);
            await page.addStyleTag({
              content: `
                ${STAGE} { flex: none !important; width: 720px !important; height: 700px !important }
                [data-expanded="true"] ${STAGE} {
                  width: ${WIDTH}px !important; height: ${HEIGHT}px !important
                }
              `,
            });
          },
          measure: async () => {
            // A snapshot publishes the existing desk to the pane. A chat URL
            // would also trigger the frontend's own open request.
            await sendPrompt(
              page,
              '请调用一次 sandbox_browser_snapshot，把我当前沙箱桌的网页显示在右侧供我操作。只读这张已有的桌，保持页面原样，然后结束任务。',
            );
            return await measurePane(
              page,
              () => page.locator(FULLSCREEN).click(),
              { out, getReference: local ? () => reference : undefined, run },
            );
          },
          collectDesks: (ids) => collectChatDesks(page, base, headers, ids),
          onRetry: (retry, error) => {
            report.retries[run - 1] = retry;
            console.warn(`Round ${run}, retry ${retry}: ${error.message}`);
          },
        });
        report.runs.push(result);
        console.log(
          JSON.stringify({
            run,
            retries: report.retries[run - 1],
            clickMs: result.click.ms,
            maxMs: result.max.ms,
            fps: result.scroll.fps,
            smallTextRms: result.max.rms,
          }),
        );
      }
      report.medianFps = report.runs.map((r) => r.scroll.fps).sort((a, b) => a - b)[1];
      report.pass =
        report.medianFps >= 2 &&
        report.runs.every((r) => r.click.ms < 1000 && r.max.ms < 1000 && (!local || r.max.rms <= 5));
      if (!report.pass) process.exitCode = 1;
    }, () => writeJson(path.join(out, 'report.json'), report));
  }, async () => {
    link?.close();
    await browser?.close();
  });
}

export { watchPane };

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
