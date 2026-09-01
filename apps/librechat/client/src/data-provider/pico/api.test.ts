import { getTokenHeader } from 'librechat-data-provider';
import {
  getPicoArtifactContent,
  picoAuthedGet,
  picoAuthedPost,
  humanizeRunError,
  labelForLatestRun,
  searchEduSchoolMaterials,
  putEduNamedIds,
  listEduFields,
  listMyPicoArtifacts,
  listMyFolders,
  createMyFolder,
  transferMyArtifact,
  quotePicoPoints,
} from './api';

jest.mock('librechat-data-provider', () => ({
  getTokenHeader: jest.fn(),
}));

const mockGetTokenHeader = getTokenHeader as jest.MockedFunction<typeof getTokenHeader>;

describe('getPicoArtifactContent', () => {
  const originalFetch = global.fetch;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
    mockGetTokenHeader.mockReturnValue('Bearer browser-jwt');
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  it.each([
    ['inline', false, '', undefined],
    ['download', true, '?download=true', undefined],
    ['preview', false, '?preview=1', { preview: true }],
  ])('requests the authenticated %s artifact blob', async (_mode, download, query, opts) => {
    const blob = new Blob(['artifact bytes'], { type: 'text/plain' });
    fetchMock.mockResolvedValue({
      ok: true,
      blob: async () => blob,
    });

    await expect(getPicoArtifactContent('artifact-1', download as boolean, opts as { preview?: boolean } | undefined)).resolves.toBe(blob);
    expect(fetchMock).toHaveBeenCalledWith(`/api/pico/v1/artifacts/artifact-1/content${query}`, {
      credentials: 'include',
      headers: expect.objectContaining({
        Authorization: 'Bearer browser-jwt',
      }),
    });
  });

  it('sends Authorization on same-origin LibreChat file download', async () => {
    fetchMock.mockResolvedValue({ ok: true, blob: async () => new Blob(['%PDF']) });
    await picoAuthedGet('/api/files/download/u1/fid');
    expect(fetchMock).toHaveBeenCalledWith('/api/files/download/u1/fid', {
      credentials: 'include',
      headers: expect.objectContaining({
        Authorization: 'Bearer browser-jwt',
      }),
    });
  });

  it('POSTs JSON with the same Authorization header', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    await picoAuthedPost('/api/pico/v1/admin/gateway/accounts/9/refresh');
    expect(fetchMock).toHaveBeenCalledWith('/api/pico/v1/admin/gateway/accounts/9/refresh', {
      method: 'POST',
      credentials: 'include',
      headers: expect.objectContaining({
        Authorization: 'Bearer browser-jwt',
        'Content-Type': 'application/json',
      }),
      body: undefined,
    });
  });
});

describe('labelForLatestRun', () => {
  it('maps ledger run status to teacher-facing labels', () => {
    expect(labelForLatestRun(null)).toBeNull();
    expect(labelForLatestRun({ id: '1', status: 'running' })).toBe('仍在处理…');
    expect(
      labelForLatestRun({ id: '1', status: 'running', cancel_requested: true }),
    ).toBe('停止中');
    expect(labelForLatestRun({ id: '1', status: 'cancelled' })).toBe('已停止');
    expect(labelForLatestRun({ id: '1', status: 'failed' })).toBe('失败');
    expect(labelForLatestRun({ id: '1', status: 'succeeded' })).toBe('已完成');
  });
});

describe('humanizeRunError', () => {
  it('prefers server user_message', () => {
    expect(humanizeRunError('run owner was lost', '服务维护或重启导致任务中断')).toContain(
      '维护',
    );
  });

  it('maps bare owner-lost English', () => {
    const msg = humanizeRunError('run owner was lost during API restart');
    expect(msg).toMatch(/重启|维护/);
    expect(msg?.toLowerCase()).not.toContain('owner was lost');
  });

  it('maps LibreChat stream terminated English', () => {
    const msg = humanizeRunError(
      'An error occurred while processing the request: terminated',
    );
    expect(msg).toMatch(/重启|维护/);
    expect(msg?.toLowerCase()).not.toContain('terminated');
  });
});

describe('edu school materials client', () => {
  const originalFetch = global.fetch;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
    mockGetTokenHeader.mockReturnValue('Bearer browser-jwt');
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  it('searches membership materials without dumping', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: 'a', title: '课时' }], dumped: false }),
    });
    await expect(searchEduSchoolMaterials('课时')).resolves.toEqual({
      items: [{ id: 'a', title: '课时' }],
      dumped: false,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/pico/v1/edu/materials?q=%E8%AF%BE%E6%97%B6',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('searches membership materials for a named field', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: 'a', title: '课时' }], dumped: false }),
    });
    await searchEduSchoolMaterials('课时', 'field-1');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/pico/v1/edu/materials?q=%E8%AF%BE%E6%97%B6&field_id=field-1',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('puts named ids only', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ ids: ['aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'], dumped: false }),
    });
    await putEduNamedIds('c1', ['aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee']);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/pico/v1/edu/named',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          conversation_id: 'c1',
          ids: ['aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'],
          field_id: '',
        }),
      }),
    );
  });

  it('lists school fields', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ fields: [{ id: 'f1', name: '本学期排课' }], dumped: false }),
    });
    await expect(listEduFields()).resolves.toEqual({
      fields: [{ id: 'f1', name: '本学期排课' }],
      dumped: false,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/pico/v1/edu/fields',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('lists my ledger artifacts for 文件页次级区', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 1,
        artifacts: [{ id: 'art-1', title: '家长会通知.html', kind: 'html' }],
      }),
    });
    await expect(listMyPicoArtifacts()).resolves.toEqual({
      count: 1,
      artifacts: [{ id: 'art-1', title: '家长会通知.html', kind: 'html' }],
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/pico/v1/artifacts?mine=true',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('creates a personal folder and transfers via existing land mouth', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ folder: { id: 'f1', name: '备课' } }),
    });
    await expect(createMyFolder('备课')).resolves.toEqual({
      folder: { id: 'f1', name: '备课' },
    });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ folders: [{ id: 'f1', name: '备课' }] }),
    });
    await expect(listMyFolders()).resolves.toEqual({
      folders: [{ id: 'f1', name: '备课' }],
    });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ landed: false, code: 'edu.unconfigured' }),
    });
    await expect(transferMyArtifact('art-1', 'field-1', 'copy')).resolves.toEqual({
      landed: false,
      code: 'edu.unconfigured',
    });
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/pico/v1/my/artifacts/art-1/transfer',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ field_id: 'field-1', mode: 'copy' }),
      }),
    );
  });
});

describe('quotePicoPoints', () => {
  const originalFetch = global.fetch;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
    mockGetTokenHeader.mockReturnValue('Bearer browser-jwt');
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  it('posts teacher chars without borrowing a placeholder conversation', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ phase: 'quote', points: '25.224', wallet: false }),
    });
    await expect(quotePicoPoints(14, 'new')).resolves.toEqual({
      phase: 'quote',
      points: '25.224',
      wallet: false,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/pico/v1/usage/points/quote',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ input_chars: 14 }),
      }),
    );
  });

  it('passes this conversation so 预计 can cover the last bill', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ phase: 'quote', points: '25.278', wallet: false }),
    });
    await expect(quotePicoPoints(14, 'convo-hi')).resolves.toEqual({
      phase: 'quote',
      points: '25.278',
      wallet: false,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/pico/v1/usage/points/quote',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ input_chars: 14, conversation_id: 'convo-hi' }),
      }),
    );
  });
});
