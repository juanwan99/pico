import { render, screen } from '@testing-library/react';
import type { PicoRunEvent } from '~/data-provider/pico/api';
import RunTimeline from '../RunTimeline';

function event(
  id: string,
  seq: number,
  type: string,
  payload: Record<string, unknown> = {},
): PicoRunEvent {
  return { id, run_id: 'run-1', seq, type, payload };
}

describe('RunTimeline', () => {
  it('shows the current run skill, tools, results, and artifacts in sequence order', () => {
    render(
      <RunTimeline
        events={[
          event('artifact', 4, 'artifact.created', { title: 'report.csv', kind: 'file' }),
          event('result', 3, 'tool.result', { tool: 'calculator', ok: true }),
          event('skill', 1, 'skill.snapshot', { id: 'analysis', tools: ['calculator'] }),
          event('call', 2, 'tool.call', { tool: 'calculator', arguments: { expression: '6*7' } }),
          event('noise', 5, 'message.delta', { text: 'secret output' }),
        ]}
      />,
    );

    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(4);
    expect(items[0]).toHaveTextContent('Skill · analysis');
    expect(items[0]).toHaveTextContent('工具：calculator');
    expect(items[1]).toHaveTextContent('调用工具 · calculator');
    expect(items[2]).toHaveTextContent('工具结果 · calculator');
    expect(items[3]).toHaveTextContent('生成产物 · report.csv');
    expect(screen.queryByText('secret output')).not.toBeInTheDocument();
  });

  it('shows an empty-tools snapshot and the empty state', () => {
    const { rerender } = render(
      <RunTimeline events={[event('skill', 1, 'skill.snapshot', { id: 'unknown', tools: [] })]} />,
    );

    expect(screen.getByText('无工具')).toBeInTheDocument();

    rerender(<RunTimeline events={[]} />);
    expect(screen.getByText('暂无步骤')).toBeInTheDocument();
  });
});
