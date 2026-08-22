/**
 * Thin workbench ingest: copy uploaded .docx/.pptx bytes into Pico ledger.
 * LibreChat keeps its own file record; Pico needs OOXML for edit_* tools.
 */
const fs = require('fs').promises;
const path = require('path');
const { logger } = require('@librechat/data-schemas');

function picoBase() {
  const raw =
    process.env.OPENAI_REVERSE_PROXY || process.env.PICO_API_BASE || 'http://127.0.0.1:18765/v1';
  const base = raw.replace(/\/v1\/?$/, '');
  try {
    const u = new URL(base.includes('://') ? base : `http://${base}`);
    return `${u.protocol}//${u.host}`;
  } catch {
    return 'http://127.0.0.1:18765';
  }
}

function picoKey() {
  return process.env.PICO_OPENAI_PROXY_KEY || process.env.OPENAI_API_KEY || 'sk-pico-dev';
}

function membershipFromReq(req) {
  const eduId = String(req.user?.eduId || '').trim();
  const schoolId = String(req.user?.eduSchoolId || '').trim();
  const idRe = /^[A-Za-z0-9_-]{1,128}$/;
  if (idRe.test(eduId) && idRe.test(schoolId)) {
    return `${schoolId}:${eduId}`;
  }
  if (idRe.test(eduId)) {
    return eduId;
  }
  const id = req.user?.id?.toString?.() || req.user?._id?.toString?.() || '';
  return id.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 128) || 'anonymous';
}

async function readOfficeBytes({ buffer, filepath, filePath }) {
  if (buffer && buffer.length) {
    return Buffer.from(buffer);
  }
  for (const candidate of [filePath, filepath]) {
    if (
      candidate &&
      typeof candidate === 'string' &&
      !candidate.startsWith('http://') &&
      !candidate.startsWith('https://')
    ) {
      try {
        return await fs.readFile(candidate);
      } catch {
        continue;
      }
    }
  }
  return null;
}

async function ingestOfficeToPico({ req, filename, filepath, buffer, filePath }) {
  const name = path.basename(String(filename || ''));
  const ext = path.extname(name).toLowerCase();
  if (ext !== '.docx' && ext !== '.pptx') {
    return null;
  }
  const data = await readOfficeBytes({ buffer, filepath, filePath });
  if (!data || !data.length) {
    return null;
  }
  const conversationId =
    req.body?.conversationId || req.body?.conversation_id || req.headers['x-conversation-id'];
  const headers = {
    Authorization: `Bearer ${picoKey()}`,
    'Content-Type': 'application/json',
    'X-Pico-Membership-Id': membershipFromReq(req),
  };
  if (conversationId && /^[A-Za-z0-9._:-]{1,128}$/.test(String(conversationId))) {
    headers['X-Conversation-Id'] = String(conversationId);
  }
  try {
    const res = await fetch(`${picoBase()}/v1/files`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        filename: name,
        content_b64: data.toString('base64'),
      }),
    });
    if (!res.ok) {
      logger.warn(`[pico office ingest] HTTP ${res.status}`);
      return null;
    }
    return await res.json();
  } catch (err) {
    logger.warn('[pico office ingest]', err);
    return null;
  }
}

module.exports = { ingestOfficeToPico, membershipFromReq };
