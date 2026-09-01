import {
  composeProcessHint,
  computeRunStatusLabel,
  lastProcessStep,
} from '~/hooks/Pico/usePicoTaskLedger';
import type { PicoRunEvent } from '~/data-provider/pico/api';

jest.mock(
  'librechat-data-provider',
  () => ({
    getTokenHeader: jest.fn(() => 'Bearer test-token'),
  }),
  { virtual: true },
);

const prompt: PicoRunEvent = {
  id: 'e1',
  run_id: 'r1',
  seq: 1,
  type: 'ui.prompt.begin',
  payload: { text: '在线数据提交到哪里?', options: ['HTTPS', '暂无'] },
};

describe('parked ask_user labels', () => {
  it('keeps 在等你选 even if a later tool.call exists', () => {
    expect(
      lastProcessStep([
        prompt,
        {
          id: 'e2',
          run_id: 'r1',
          seq: 2,
          type: 'tool.call',
          payload: { tool: 'ask_user' },
        },
      ]),
    ).toBe('在等你选');
  });

  it('does not paint 云端继续中 / 等待模型响应 while waiting for a pick', () => {
    expect(composeProcessHint({ id: 'r1', task_id: 't1', status: 'running' }, [prompt])).toBe(
      '在等你选',
    );
    expect(
      computeRunStatusLabel({ id: 'r1', task_id: 't1', status: 'running' }, true, [], [prompt]),
    ).toBe('在等你选');
    expect(
      computeRunStatusLabel({ id: 'r1', task_id: 't1', status: 'succeeded' }, true, [], [prompt]),
    ).toBe('已完成');
  });
});
