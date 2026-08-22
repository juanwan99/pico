jest.mock(
  '@librechat/data-schemas',
  () => ({
    logger: { warn: jest.fn(), error: jest.fn(), debug: jest.fn(), info: jest.fn() },
  }),
  { virtual: true },
);

const {
  conversationHeader,
  INGEST_EXT,
  decodeUploadName,
  membershipFromReq,
  ingestOfficeToPico,
} = require('./picoOfficeIngest');

describe('pico composer ingest (T-AGENT-PLAIN-V1 F2)', () => {
  it('accepts markdown and text plus office', () => {
    expect(INGEST_EXT.has('.md')).toBe(true);
    expect(INGEST_EXT.has('.txt')).toBe(true);
    expect(INGEST_EXT.has('.docx')).toBe(true);
    expect(INGEST_EXT.has('.pptx')).toBe(true);
    expect(INGEST_EXT.has('.png')).toBe(false);
  });

  it('does not stamp reserved conversation ids', () => {
    expect(conversationHeader('new')).toBe('');
    expect(conversationHeader('search')).toBe('');
    expect(conversationHeader('')).toBe('');
    expect(conversationHeader('pending_abc-1')).toBe('pending_abc-1');
    expect(conversationHeader('f2bd2503-a59e-4428-a18e-6d9520b2ae51')).toBe(
      'f2bd2503-a59e-4428-a18e-6d9520b2ae51',
    );
  });

  it('decodes composer percent-encoded filenames', () => {
    expect(decodeUploadName('%E7%8F%AD%E6%83%85.md')).toBe('班情.md');
    expect(decodeUploadName('学期要点.md')).toBe('学期要点.md');
    expect(decodeUploadName('/tmp/%E5%AD%A6%E6%9C%9F%E8%A6%81%E7%82%B9.md')).toBe('学期要点.md');
  });

  it('binds membership to LibreChat user id (same as chat completions)', () => {
    expect(
      membershipFromReq({
        user: { id: 'mongoUser1', eduId: 'edu-99', eduSchoolId: 'school-a' },
      }),
    ).toBe('mongoUser1');
    expect(membershipFromReq({ user: { _id: { toString: () => 'oid-ab' } } })).toBe('oid-ab');
  });

  it('posts decoded filename and membership to /v1/files', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'art-1', status: 'ok' }),
    });
    global.fetch = fetchMock;
    const req = {
      user: { id: 'user-lc-1' },
      body: { conversationId: 'new' },
      headers: {},
    };
    const got = await ingestOfficeToPico({
      req,
      filename: '%E7%8F%AD%E6%83%85.md',
      buffer: Buffer.from('年级：三年级二班。人数：42。\n'),
    });
    expect(got).toEqual({ id: 'art-1', status: 'ok' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/v1\/files$/);
    expect(init.headers['X-Pico-Membership-Id']).toBe('user-lc-1');
    expect(init.headers['X-Conversation-Id']).toBeUndefined();
    const body = JSON.parse(init.body);
    expect(body.filename).toBe('班情.md');
    expect(Buffer.from(body.content_b64, 'base64').toString('utf8')).toContain('三年级二班');
  });
});
