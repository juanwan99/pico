import { ContentTypes } from 'librechat-data-provider';
import { collectThinkText } from '../picoThinking';

describe('collectThinkText', () => {
  it('joins THINK parts and strips <think> wrappers', () => {
    expect(
      collectThinkText([
        { type: ContentTypes.THINK, think: '<think>one' },
        { type: ContentTypes.TEXT, text: 'answer' },
        { type: ContentTypes.THINK, think: { value: 'two</think>' } },
      ]),
    ).toBe('onetwo');
  });

  it('returns empty when there is no thinking', () => {
    expect(collectThinkText([{ type: ContentTypes.TEXT, text: 'hi' }])).toBe('');
    expect(collectThinkText([])).toBe('');
    expect(collectThinkText(undefined)).toBe('');
  });
});
