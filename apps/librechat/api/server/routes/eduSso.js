/**
 * T-PICO-SSO-LOGIN: school-minted one-time ticket → Pico workbench session.
 * New window lands here, not an edu iframe / subpage.
 */
const { logger } = require('@librechat/data-schemas');
const { findUser, createUser, getUserById } = require('~/models');
const { setAuthTokens } = require('~/server/services/AuthService');

const ID_RE = /^[A-Za-z0-9_-]{1,128}$/;
const FORBIDDEN_QS = [
  'field',
  'student',
  'page',
  'material',
  'school',
  'school_id',
  'field_id',
  'student_id',
];

function picoApiBase() {
  const raw =
    process.env.PICO_API_BASE || process.env.OPENAI_REVERSE_PROXY || 'http://127.0.0.1:18765';
  try {
    const u = new URL(raw.includes('://') ? raw : `http://${raw}`);
    return `${u.protocol}//${u.host}`;
  } catch {
    return 'http://127.0.0.1:18765';
  }
}

function parentDomainCookie(domain) {
  return typeof domain === 'string' && /(^|\.)weiyuji\.cn$/i.test(String(domain).trim());
}

function eduMembershipHeader(user) {
  const eduId = String(user?.eduId || '').trim();
  const schoolId = String(user?.eduSchoolId || '').trim();
  if (ID_RE.test(eduId) && ID_RE.test(schoolId)) {
    return `${schoolId}:${eduId}`;
  }
  if (ID_RE.test(eduId)) {
    return eduId;
  }
  return '';
}

async function consumeTicket(ticket, fetchImpl = fetch) {
  const raw = String(ticket || '').trim();
  if (!raw) {
    const err = new Error('ticket required');
    err.code = 'auth.missing';
    throw err;
  }
  const response = await fetchImpl(`${picoApiBase()}/v1/edu-sso/consume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ ticket: raw }),
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = json && typeof json.detail === 'object' ? json.detail : {};
    const err = new Error(detail.message || json.message || 'ticket rejected');
    err.code = detail.code || 'auth.invalid';
    err.status = response.status;
    throw err;
  }
  const schoolId = String(json.school_id || '').trim();
  const membershipId = String(json.membership_id || '').trim();
  if (!ID_RE.test(schoolId) || !ID_RE.test(membershipId)) {
    const err = new Error('bad identity');
    err.code = 'auth.invalid';
    throw err;
  }
  return { schoolId, membershipId };
}

async function findOrCreateEduUser({ schoolId, membershipId }) {
  const existing = await findUser({ provider: 'edu', eduId: membershipId });
  if (existing) {
    return existing;
  }
  const createdId = await createUser(
    {
      email: `${membershipId}@edu.pico.sso`,
      emailVerified: true,
      username: `edu-${membershipId.replace(/-/g, '').slice(0, 12)}`,
      name: '学校账号',
      provider: 'edu',
      eduId: membershipId,
      eduSchoolId: schoolId,
    },
    undefined,
    true,
    false,
  );
  return await getUserById(createdId);
}

async function eduSsoController(req, res) {
  try {
    if (parentDomainCookie(process.env.COOKIE_DOMAIN)) {
      logger.warn('[edu-sso] refusing parent-domain COOKIE_DOMAIN');
      return res.redirect(302, '/login');
    }
    const query = req.query && typeof req.query === 'object' ? req.query : {};
    for (const key of FORBIDDEN_QS) {
      if (Object.prototype.hasOwnProperty.call(query, key)) {
        delete query[key];
      }
    }
    const ticket = typeof query.ticket === 'string' ? query.ticket : '';
    const { schoolId, membershipId } = await consumeTicket(ticket);
    const user = await findOrCreateEduUser({ schoolId, membershipId });
    const userId = user._id || user.id;
    await setAuthTokens(userId, res, null, req);
    return res.redirect(302, '/c/new');
  } catch (err) {
    logger.warn('[edu-sso] ticket not accepted', err?.code || err?.message || err);
    return res.redirect(302, '/login');
  }
}

module.exports = {
  eduSsoController,
  consumeTicket,
  findOrCreateEduUser,
  eduMembershipHeader,
  picoApiBase,
  parentDomainCookie,
};
