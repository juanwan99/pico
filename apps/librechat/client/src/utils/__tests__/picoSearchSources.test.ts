import { collectPicoSearchSources } from '../picoSearchSources';
import type { PicoRunEvent } from '~/data-provider/pico/api';

function event(type: string, payload: Record<string, unknown>): PicoRunEvent {
  return { id: type, run_id: 'run-1', seq: 1, type, payload };
}

describe('collectPicoSearchSources', () => {
  it('surfaces clickable http sources from search.sources', () => {
    const view = collectPicoSearchSources([
      event('search.sources', {
        tool: 'web_search',
        honest_miss: false,
        sources: [{ title: 'Gov', url: 'https://www.gov.cn/a' }],
      }),
    ]);
    expect(view.searched).toBe(true);
    expect(view.honestMiss).toBe(false);
    expect(view.sources).toEqual([{ title: 'Gov', url: 'https://www.gov.cn/a' }]);
  });

  it('shows honest miss when search ran with no sources', () => {
    const view = collectPicoSearchSources([
      event('search.sources', {
        tool: 'web_search',
        honest_miss: true,
        sources: [],
      }),
    ]);
    expect(view.searched).toBe(true);
    expect(view.honestMiss).toBe(true);
    expect(view.sources).toEqual([]);
  });

  it('parses tool.result JSON and ignores invented non-http urls', () => {
    const view = collectPicoSearchSources([
      event('tool.result', {
        tool: 'web_search',
        ok: true,
        result: JSON.stringify({
          sources: [
            { title: 'News', url: 'https://example.com/n' },
            { title: 'bad', url: 'javascript:alert(1)' },
          ],
        }),
      }),
    ]);
    expect(view.sources).toEqual([{ title: 'News', url: 'https://example.com/n' }]);
  });

  it('does not claim a miss when no search ran', () => {
    const view = collectPicoSearchSources([
      event('tool.result', { tool: 'calculator', ok: true, result: '{}' }),
    ]);
    expect(view.searched).toBe(false);
    expect(view.honestMiss).toBe(false);
    expect(view.sources).toEqual([]);
  });

  it('falls back to assistant markdown links when ledger events are empty', () => {
    const view = collectPicoSearchSources([], [
      { isCreatedByUser: true, text: '搜一下 https://evil.example/nope' },
      {
        isCreatedByUser: false,
        text: '见 [义务教育法](https://www.gov.cn/a) 与 https://www.gov.cn/b',
      },
    ]);
    expect(view.searched).toBe(true);
    expect(view.honestMiss).toBe(false);
    expect(view.sources).toEqual([
      { title: '义务教育法', url: 'https://www.gov.cn/a' },
      { title: 'https://www.gov.cn/b', url: 'https://www.gov.cn/b' },
    ]);
  });

  it('keeps honest miss when ledger searched and ignores invented bubble links', () => {
    const view = collectPicoSearchSources(
      [
        event('search.sources', {
          tool: 'web_search',
          honest_miss: true,
          sources: [],
        }),
      ],
      [{ isCreatedByUser: false, text: '见 [假](https://example.com/invented)' }],
    );
    expect(view.searched).toBe(true);
    expect(view.honestMiss).toBe(true);
    expect(view.sources).toEqual([]);
  });
});
