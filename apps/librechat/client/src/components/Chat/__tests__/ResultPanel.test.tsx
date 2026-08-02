import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { PicoRun, PicoRunEvent } from '~/data-provider/pico/api';
import ResultPanel, { formatRunTokenUsage } from '../ResultPanel';

jest.mock('~/data-provider/pico/api', () => ({
  getPicoArtifactContent: jest.fn(),
}));
jest.mock('~/utils', () => ({
  cn: (...values: Array<string | false | null | undefined>) => values.filter(Boolean).join(' '),
}));

function run(tokenUsage?: Record<string, unknown>): PicoRun {
  return {
    id: 'run-1',
    task_id: 'task-1',
    status: 'succeeded',
    token_usage: tokenUsage,
  };
}

describe('ResultPanel token usage', () => {
  it('formats total-only and detailed token usage', () => {
    expect(formatRunTokenUsage(run({ total_tokens: 1234 }))).toBe('用量 · 1,234 tokens');
    expect(
      formatRunTokenUsage(run({ input_tokens: 1000, output_tokens: 234, total_tokens: 1234 })),
    ).toBe('用量 · 输入 1,000 · 输出 234 · 共 1,234 tokens');
    expect(formatRunTokenUsage(run({ skill_snapshot: { id: 'analysis' } }))).toBeNull();
  });

  it('shows a concise usage line in the result overview', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel run={run({ total_tokens: 42 })} runStatusLabel="已完成" />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('result-token-usage')).toHaveTextContent('用量 · 42 tokens');
  });

  it('shows the failed user message consistently in the overview and timeline', () => {
    const failedRun = { ...run(), status: 'failed', error: 'technical provider failure' };
    const events: PicoRunEvent[] = [
      {
        id: 'event-failed',
        run_id: failedRun.id,
        seq: 1,
        type: 'run.status',
        payload: {
          status: 'failed',
          user_message: '模型服务暂时繁忙，请稍后重试。',
        },
      },
    ];

    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={failedRun}
          runEvents={events}
          runStatusLabel="失败：模型服务暂时繁忙，请稍后重试。"
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('result-status-banner')).toHaveTextContent(
      '失败：模型服务暂时繁忙，请稍后重试。',
    );
    expect(screen.getByText('模型服务暂时繁忙，请稍后重试。')).toBeInTheDocument();
    expect(screen.queryByText(/technical provider failure/)).not.toBeInTheDocument();
  });
});
