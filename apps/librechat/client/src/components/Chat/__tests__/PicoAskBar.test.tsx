import { fireEvent, render, screen } from '@testing-library/react';
import type { PicoRun, PicoRunEvent } from '~/data-provider/pico/api';
import PicoAskBar from '../PicoAskBar';

const mockAnswerPicoAsk = jest.fn(() => Promise.resolve({ ok: true, run_id: 'run-1' }));

jest.mock('~/data-provider/pico/api', () => ({
  answerPicoAsk: (...args: unknown[]) => mockAnswerPicoAsk(...args),
}));

function event(payload: Record<string, unknown>): PicoRunEvent {
  return { id: 'wait', run_id: 'run-1', seq: 1, type: 'ui.prompt.begin', payload };
}

function run(status = 'running'): PicoRun {
  return { id: 'run-1', task_id: 'task-1', status };
}

describe('PicoAskBar main column', () => {
  beforeEach(() => {
    mockAnswerPicoAsk.mockClear();
  });

  it('renders plan options next to the composer without opening 结果区', () => {
    render(
      <PicoAskBar
        run={run()}
        events={[
          event({
            text: '计划好了，下一步？',
            options: ['确认执行', '先不执行', '再改计划'],
            source: 'true-pi',
          }),
        ]}
      />,
    );
    expect(screen.getByTestId('pico-ask-main')).toHaveTextContent('计划好了，下一步？');
    expect(screen.getByText('点一项继续。这时不是在跑模型。')).toBeInTheDocument();
    expect(screen.getByText('需要你选一项')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认执行' }));
    expect(mockAnswerPicoAsk).toHaveBeenCalledWith('run-1', '确认执行');
    expect(screen.getByTestId('pico-ask-busy')).toHaveTextContent('已选「确认执行」· 继续中…');
    expect(screen.getByRole('button', { name: '确认执行' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('unlocks and shows an error when the answer POST fails', async () => {
    mockAnswerPicoAsk.mockRejectedValueOnce(new Error('network'));
    render(
      <PicoAskBar
        run={run()}
        events={[
          event({
            text: '计划好了，下一步？',
            options: ['确认执行', '先不执行'],
            source: 'true-pi',
          }),
        ]}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '确认执行' }));
    expect(await screen.findByTestId('pico-ask-error')).toHaveTextContent('没送出去，再点一次');
    expect(screen.getByRole('button', { name: '确认执行' })).not.toBeDisabled();
    expect(screen.queryByTestId('pico-ask-busy')).not.toBeInTheDocument();
  });

  it('hides when the prompt already ended', () => {
    render(
      <PicoAskBar
        run={run()}
        events={[
          event({ text: '计划好了，下一步？', options: ['确认执行', '先不执行'] }),
          { id: 'end', run_id: 'run-1', seq: 2, type: 'ui.prompt.end', payload: { text: '已选' } },
        ]}
      />,
    );
    expect(screen.queryByTestId('pico-ask-main')).not.toBeInTheDocument();
  });
});
