import { getTokenHeader } from 'librechat-data-provider';
import {
  getPicoArtifactContent,
  humanizeRunError,
  labelForLatestRun,
  searchEduSchoolMaterials,
  putEduNamedIds,
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
    ['inline', false, ''],
    ['download', true, '?download=true'],
  ])('requests the authenticated %s artifact blob', async (_mode, download, query) => {
    const blob = new Blob(['artifact bytes'], { type: 'text/plain' });
    fetchMock.mockResolvedValue({
      ok: true,
      blob: async () => blob,
    });

    await expect(getPicoArtifactContent('artifact-1', download)).resolves.toBe(blob);
    expect(fetchMock).toHaveBeenCalledWith(`/api/pico/v1/artifacts/artifact-1/content${query}`, {
      credentials: 'include',
      headers: expect.objectContaining({
        Authorization: 'Bearer browser-jwt',
      }),
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
        }),
      }),
    );
  });
});
