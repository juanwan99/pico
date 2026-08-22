const express = require('express');
const request = require('supertest');
const { readFileSync } = require('fs');
const { join } = require('path');

const mockFindUser = jest.fn();
const mockCreateUser = jest.fn();
const mockGetUserById = jest.fn();
const mockUpdateUser = jest.fn();
const mockSetAuthTokens = jest.fn().mockResolvedValue('access-token');

jest.mock('~/models', () => ({
  findUser: (...args) => mockFindUser(...args),
  createUser: (...args) => mockCreateUser(...args),
  getUserById: (...args) => mockGetUserById(...args),
  updateUser: (...args) => mockUpdateUser(...args),
}));

jest.mock('~/server/services/AuthService', () => ({
  setAuthTokens: (...args) => mockSetAuthTokens(...args),
}));

jest.mock(
  '@librechat/data-schemas',
  () => ({
    logger: { warn: jest.fn(), error: jest.fn(), info: jest.fn(), debug: jest.fn() },
  }),
  { virtual: true },
);

const { eduSsoController, parentDomainCookie, eduMembershipHeader, eduDisplayName } = require('./eduSso');

const SCHOOL = '627bcf3a-a9a8-4047-afcc-3d4878e2a7af';
const MEMBER = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee';

describe('edu SSO', () => {
  let app;

  beforeEach(() => {
    mockFindUser.mockReset();
    mockCreateUser.mockReset();
    mockGetUserById.mockReset();
    mockUpdateUser.mockReset();
    mockSetAuthTokens.mockClear();
    app = express();
    app.get('/api/auth/edu-sso', eduSsoController);
    global.fetch = jest.fn();
  });

  afterEach(() => {
    delete global.fetch;
    delete process.env.COOKIE_DOMAIN;
  });

  it('sets workbench session and leaves login wall', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        ok: true,
        school_id: SCHOOL,
        membership_id: MEMBER,
        display_name: '孙骏博',
      }),
    });
    mockFindUser.mockResolvedValue(null);
    mockCreateUser.mockResolvedValue('user-1');
    mockGetUserById.mockResolvedValue({ _id: 'user-1', eduId: MEMBER, eduSchoolId: SCHOOL, name: '孙骏博' });

    const res = await request(app).get('/api/auth/edu-sso').query({ ticket: 'web-ticket' });
    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('/c/new');
    expect(res.headers.location).not.toMatch(/login/);
    expect(mockSetAuthTokens).toHaveBeenCalledWith('user-1', expect.anything(), null, expect.anything());
    expect(mockCreateUser).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: 'edu',
        eduId: MEMBER,
        eduSchoolId: SCHOOL,
        name: '孙骏博',
      }),
      undefined,
      true,
      false,
    );
    expect(mockCreateUser.mock.calls[0][0].name).not.toBe('学校账号');
    const consumeUrl = global.fetch.mock.calls[0][0];
    expect(consumeUrl).toMatch(/\/v1\/edu-sso\/consume$/);
  });

  it('reuses the same membership user (no serial mix-up)', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        ok: true,
        school_id: SCHOOL,
        membership_id: MEMBER,
        display_name: '孙骏博',
      }),
    });
    mockFindUser.mockResolvedValue({
      _id: 'existing',
      eduId: MEMBER,
      eduSchoolId: SCHOOL,
      name: '学校账号',
    });
    mockUpdateUser.mockResolvedValue({ _id: 'existing', name: '孙骏博' });

    const res = await request(app).get('/api/auth/edu-sso').query({ ticket: 'web-ticket' });
    expect(res.headers.location).toBe('/c/new');
    expect(mockCreateUser).not.toHaveBeenCalled();
    expect(mockUpdateUser).toHaveBeenCalledWith('existing', expect.objectContaining({ name: '孙骏博' }));
    expect(mockSetAuthTokens).toHaveBeenCalledWith('existing', expect.anything(), null, expect.anything());
  });

  it('falls back to workbench login when ticket is spent or missing', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: { code: 'auth.invalid', message: 'ticket already used' } }),
    });
    const spent = await request(app).get('/api/auth/edu-sso').query({ ticket: 'used' });
    expect(spent.headers.location).toBe('/login');
    expect(mockSetAuthTokens).not.toHaveBeenCalled();

    const missing = await request(app).get('/api/auth/edu-sso');
    expect(missing.headers.location).toBe('/login');
  });

  it('strips field/student query and never sets parent-domain cookies', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, school_id: SCHOOL, membership_id: MEMBER }),
    });
    mockFindUser.mockResolvedValue({ _id: 'existing', eduId: MEMBER });
    const res = await request(app)
      .get('/api/auth/edu-sso')
      .query({ ticket: 'web-ticket', field: 'abc', student: '1', page: '2', material: '3' });
    expect(res.headers.location).toBe('/c/new');
    const setCookie = res.headers['set-cookie'] || [];
    expect(String(setCookie)).not.toMatch(/weiyuji\.cn/i);
    expect(parentDomainCookie('.weiyuji.cn')).toBe(true);
    expect(parentDomainCookie('pico.aivia.asia')).toBe(false);
  });

  it('refuses COOKIE_DOMAIN on parent edu domain', async () => {
    process.env.COOKIE_DOMAIN = '.weiyuji.cn';
    const res = await request(app).get('/api/auth/edu-sso').query({ ticket: 'x' });
    expect(res.headers.location).toBe('/login');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('maps edu membership to the sidebar person header', () => {
    expect(eduMembershipHeader({ eduId: MEMBER, eduSchoolId: SCHOOL })).toBe(`${SCHOOL}:${MEMBER}`);
    expect(eduMembershipHeader({ id: 'mongo-id' })).toBe('');
  });

  it('source does not iframe edu or mint on a subpage', () => {
    const src = readFileSync(join(__dirname, 'eduSso.js'), 'utf8');
    expect(src).not.toMatch(/<iframe/i);
    expect(src).toMatch(/\/c\/new/);
    expect(src).toMatch(/\/login/);
    expect(src).not.toMatch(/name:\s*['"]学校账号['"]/);
  });

  it('never uses 学校账号 as the workbench name', () => {
    expect(eduDisplayName('孙骏博', MEMBER)).toBe('孙骏博');
    expect(eduDisplayName('学校账号', MEMBER)).toBe(`edu-${MEMBER.replace(/-/g, '').slice(0, 12)}`);
    expect(eduDisplayName('', MEMBER)).not.toBe('学校账号');
  });
});
