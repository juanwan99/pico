import { buildConversationStatusMap } from './usePicoConversationStatusMap';
import type { PicoTask } from '~/data-provider/pico/api';

describe('buildConversationStatusMap', () => {
  it('maps conversation ids to teacher-facing labels', () => {
    const tasks: PicoTask[] = [
      {
        id: 't1',
        title: 'a',
        conversation_id: 'c1',
        latest_run: { id: 'r1', status: 'running' },
      },
      {
        id: 't2',
        title: 'b',
        conversation_id: 'c2',
        latest_run: { id: 'r2', status: 'failed' },
      },
    ];
    expect(buildConversationStatusMap(tasks)).toEqual({
      c1: '进行中',
      c2: '失败',
    });
  });

  it('prefers active over succeeded when multiple tasks share a conversation', () => {
    const tasks: PicoTask[] = [
      {
        id: 't-old',
        title: 'done',
        conversation_id: 'c-shared',
        latest_run: { id: 'r-old', status: 'succeeded' },
      },
      {
        id: 't-new',
        title: 'live',
        conversation_id: 'c-shared',
        latest_run: { id: 'r-new', status: 'running' },
      },
    ];
    expect(buildConversationStatusMap(tasks)).toEqual({ 'c-shared': '进行中' });
  });

  it('ignores tasks without conversation binding', () => {
    expect(
      buildConversationStatusMap([
        { id: 't', title: 'x', latest_run: { id: 'r', status: 'running' } },
      ]),
    ).toEqual({});
  });
});
