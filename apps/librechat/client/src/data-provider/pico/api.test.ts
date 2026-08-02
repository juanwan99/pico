import { getTokenHeader } from 'librechat-data-provider';
import { getPicoArtifactContent } from './api';

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
