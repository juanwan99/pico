import assert from "node:assert/strict";
import test from "node:test";
import {
  isDevPath,
  outboundHeaders,
  rewriteCookie,
  rewriteLocation,
  TARGET_HOST,
} from "./grok-preview-proxy.mjs";

test("dev paths stay off the live reverse proxy", () => {
  assert.equal(isDevPath("/__grok/foo"), true);
  assert.equal(isDevPath("/src/main.tsx"), true);
  assert.equal(isDevPath("/login"), false);
  assert.equal(isDevPath("/api/auth/login"), false);
});

test("request Host/Origin/Referer become the live origin", () => {
  const headers = outboundHeaders({
    headers: {
      host: "127.0.0.1:8080",
      origin: "https://preview.example",
      referer: "https://preview.example/login",
    },
  });
  assert.equal(headers.host, TARGET_HOST);
  assert.equal(headers.origin, `https://${TARGET_HOST}`);
  assert.equal(headers.referer, `https://${TARGET_HOST}/login`);
});

test("cookies lose Domain and keep SameSite=Lax", () => {
  const out = rewriteCookie("sid=1; Domain=pico.aivia.asia; Secure; SameSite=None");
  assert.equal(out.includes("Domain="), false);
  assert.match(out, /SameSite=Lax/i);
});

test("absolute live Location becomes relative", () => {
  assert.equal(rewriteLocation("https://pico.aivia.asia/login"), "/login");
  assert.equal(rewriteLocation("https://pico.aivia.asia/"), "/");
});
