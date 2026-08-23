/**
 * Thin workbench ingest: copy composer uploads into the Pico ledger.
 * LibreChat keeps its own file record. Agent workspace_read_file reads Pico.
 * Text (.md/.txt/…) plus OOXML — T-AGENT-PLAIN-V1 F2, not a second cabinet.
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

const INGEST_EXT = new Set([
  '.docx',
  '.pptx',
  '.xlsx',
  '.md',
  '.txt',
  '.csv',
  '.tsv',
  '.json',
  '.html',
  '.htm',
]);
const RESERVED_CONVO = new Set(['new', 'search']);

function conversationHeader(raw) {
  const id = String(raw || '').trim();
  if (!id || RESERVED_CONVO.has(id)) {
    return '';
  }
  if (!/^[A-Za-z0-9._:-]{1,128}$/.test(id)) {
    return '';
  }
  return id;
}

function decodeUploadName(name) {
  const base = path.basename(String(name || ''));
  if (!base) {
    return '';
  }
  try {
    return decodeURIComponent(base).replace(/\0/g, '') || base;
  } catch {
    return base;
  }
}

function membershipFromReq(req) {
  // Same key as chat {{PICO_MEMBERSHIP_ID}} and /api/pico — one ledger.
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
  const name = decodeUploadName(filename);
  const ext = path.extname(name).toLowerCase();
  if (!INGEST_EXT.has(ext)) {
    return null;
  }
  const data = await readOfficeBytes({ buffer, filepath, filePath });
  if (!data || !data.length) {
    return null;
  }
  const conversationId = conversationHeader(
    req.body?.conversationId || req.body?.conversation_id || req.headers['x-conversation-id'],
  );
  const headers = {
    Authorization: `Bearer ${picoKey()}`,
    'Content-Type': 'application/json',
    'X-Pico-Membership-Id': membershipFromReq(req),
  };
  if (conversationId) {
    headers['X-Conversation-Id'] = conversationId;
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

module.exports = {
  ingestOfficeToPico,
  membershipFromReq,
  conversationHeader,
  decodeUploadName,
  INGEST_EXT,
};
