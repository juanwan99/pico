#!/usr/bin/env node
/**
 * Grok 右侧 8080 → https://pico.aivia.asia（EXPERIENCE §90–95）
 *
 * Not an iframe of prod (X-Frame-Options would white-screen).
 * Not a local LibreChat SPA pretending to be live.
 */
import http from "node:http";
import https from "node:https";
import { Buffer } from "node:buffer";

export const TARGET_HOST = process.env.PICO_PREVIEW_HOST || "pico.aivia.asia";
export const PORT = Number(process.env.PICO_PREVIEW_PORT || 8080);
export const LIVE_ORIGIN = `https://${TARGET_HOST}`;

const DEV_PREFIXES = [
  "/__grok",
  "/@",
  "/src/",
  "/node_modules",
  "/auth/popup",
];

const agent = new https.Agent({ keepAlive: true, maxSockets: 64 });

export function isDevPath(urlPath) {
  const path = String(urlPath || "/").split("?")[0];
  return DEV_PREFIXES.some((prefix) => path === prefix || path.startsWith(prefix));
}

export function rewriteCookie(cookie) {
  return String(cookie)
    .replace(/;\s*Domain=[^;]*/gi, "")
    .replace(/;\s*Secure/gi, "")
    .replace(/;\s*SameSite=None/gi, "; SameSite=Lax");
}

export function rewriteLocation(value) {
  const text = String(value || "");
  const stripped = text
    .replaceAll(`https://${TARGET_HOST}`, "")
    .replaceAll(`http://${TARGET_HOST}`, "");
  return stripped || "/";
}

export function outboundHeaders(req) {
  const headers = { ...req.headers };
  headers.host = TARGET_HOST;
  headers.origin = LIVE_ORIGIN;
  if (headers.referer) {
    try {
      const parsed = new URL(headers.referer);
      headers.referer = `${LIVE_ORIGIN}${parsed.pathname}${parsed.search}${parsed.hash}`;
    } catch {
      headers.referer = `${LIVE_ORIGIN}/`;
    }
  }
  delete headers["x-forwarded-host"];
  headers["x-forwarded-proto"] = "https";
  headers["accept-encoding"] = "identity";
  return headers;
}

export function inboundHeaders(headers) {
  const out = {};
  for (const [key, value] of Object.entries(headers || {})) {
    const k = key.toLowerCase();
    if (
      k === "x-frame-options" ||
      k === "content-security-policy" ||
      k === "content-security-policy-report-only" ||
      k === "strict-transport-security" ||
      k === "content-length" ||
      k === "transfer-encoding" ||
      k === "connection"
    ) {
      continue;
    }
    if (k === "set-cookie") {
      const list = Array.isArray(value) ? value : [value];
      out[key] = list.map(rewriteCookie);
      continue;
    }
    if (k === "location" && typeof value === "string") {
      out[key] = rewriteLocation(value);
      continue;
    }
    out[key] = value;
  }
  return out;
}

function fail502(res, err) {
  if (res.headersSent) {
    res.end();
    return;
  }
  const body = Buffer.from(
    `<!doctype html><meta charset="utf-8"><title>Pico</title><p>现网暂时连不上（502）。上游 pico.aivia.asia：${String(err?.message || err)}</p>`,
  );
  res.writeHead(502, {
    "content-type": "text/html; charset=utf-8",
    "content-length": body.length,
    "x-frame-options": "",
  });
  res.end(body);
}

export function createPreviewProxy() {
  const server = http.createServer((req, res) => {
    if (isDevPath(req.url || "/")) {
      res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
      res.end("vite-dev-path");
      return;
    }
    const preq = https.request(
      {
        hostname: TARGET_HOST,
        port: 443,
        path: req.url,
        method: req.method,
        headers: outboundHeaders(req),
        agent,
      },
      (pres) => {
        res.writeHead(pres.statusCode || 502, inboundHeaders(pres.headers));
        pres.pipe(res);
      },
    );
    preq.on("error", (err) => fail502(res, err));
    req.pipe(preq);
  });

  server.on("upgrade", (req, socket, head) => {
    if (isDevPath(req.url || "/")) {
      socket.destroy();
      return;
    }
    const wsReq = https.request({
      hostname: TARGET_HOST,
      port: 443,
      path: req.url,
      method: "GET",
      headers: {
        ...outboundHeaders(req),
        connection: "Upgrade",
        upgrade: req.headers.upgrade || "websocket",
      },
      agent: false,
    });
    wsReq.on("upgrade", (upRes, remote, remoteHead) => {
      const lines = ["HTTP/1.1 101 Switching Protocols"];
      for (const [key, value] of Object.entries(upRes.headers)) {
        if (Array.isArray(value)) {
          for (const item of value) lines.push(`${key}: ${item}`);
        } else {
          lines.push(`${key}: ${value}`);
        }
      }
      socket.write(`${lines.join("\r\n")}\r\n\r\n`);
      if (head?.length) remote.write(head);
      if (remoteHead?.length) socket.write(remoteHead);
      remote.pipe(socket);
      socket.pipe(remote);
    });
    wsReq.on("error", () => socket.destroy());
    socket.on("error", () => wsReq.destroy());
    wsReq.end();
  });
  return server;
}

const isMain = process.argv[1] && process.argv[1].endsWith("grok-preview-proxy.mjs");
if (isMain) {
  const live = await new Promise((resolve) => {
    const probe = https.request(
      { hostname: TARGET_HOST, port: 443, path: "/login", method: "HEAD", timeout: 8000 },
      (res) => {
        res.resume();
        resolve(res.statusCode && res.statusCode < 500);
      },
    );
    probe.on("error", () => resolve(false));
    probe.end();
  });
  if (!live) {
    console.error(`[grok-preview-proxy] probe https://${TARGET_HOST}/login failed`);
  }
  const server = createPreviewProxy();
  server.listen(PORT, "0.0.0.0", () => {
    console.log(`[grok-preview-proxy] 0.0.0.0:${PORT} → ${LIVE_ORIGIN} probe=${live ? "ok" : "fail"}`);
  });
}
