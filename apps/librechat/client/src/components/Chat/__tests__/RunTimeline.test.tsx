import { render, screen } from '@testing-library/react';
import type { PicoRun, PicoRunEvent } from '~/data-provider/pico/api';
import RunTimeline from '../RunTimeline';

function event(
  id: string,
  seq: number,
  type: string,
  payload: Record<string, unknown> = {},
): PicoRunEvent {
  return { id, run_id: 'run-1', seq, type, payload };
}

function run(status: string): PicoRun {
  return { id: 'run-1', task_id: 'task-1', status };
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
    expect(items[1]).toHaveTextContent('正在调工具');
    expect(items[2]).toHaveTextContent('工具已完成');
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

  it('shows failed run and tool summaries with error codes', () => {
    render(
      <RunTimeline
        run={run('failed')}
        events={[
          event('tool-failed', 1, 'tool.result', {
            tool: 'workspace_write_file',
            ok: false,
            code: 'tool.denied',
          }),
          event('run-failed', 2, 'run.status', {
            status: 'failed',
            code: 'timeout',
            user_message: '处理超时，请重试。',
          }),
        ]}
      />,
    );

    expect(screen.getByText('没生成文件')).toBeInTheDocument();
    expect(screen.getByText('失败 · 错误码：tool.denied')).toBeInTheDocument();
    expect(screen.getByText('运行失败')).toBeInTheDocument();
    expect(screen.getByText('处理超时，请重试。 · 错误码：timeout')).toBeInTheDocument();
  });

  it('shows a cancelled run even when the event stream has no terminal event', () => {
    render(<RunTimeline run={run('cancelled')} events={[]} />);

    expect(screen.getByText('云端任务已停止')).toBeInTheDocument();
    expect(screen.getByText(/任务栏「停止任务」已取消云端执行/)).toBeInTheDocument();
  });

  it('shows kimi-agent runtime and agent steps in the process timeline', () => {
    render(
      <RunTimeline
        run={run('running')}
        events={[
          event('run-running', 1, 'run.status', {
            status: 'running',
            runtime: 'kimi-agent',
          }),
          event('step', 2, 'agent.step', { n: 1, phase: 'tool' }),
          event('call', 3, 'tool.call', { tool: 'calculator' }),
        ]}
      />,
    );

    expect(screen.getByText('正在运行')).toBeInTheDocument();
    expect(screen.getByText('运行时 · Kimi Agent')).toBeInTheDocument();
    expect(screen.getByText(/智能体步骤/)).toBeInTheDocument();
    expect(screen.getByText('正在调工具')).toBeInTheDocument();
  });

  it('labels a recovered tool failure neutrally when the run succeeded (P2)', () => {
    render(
      <RunTimeline
        run={run('succeeded')}
        events={[
          event('tool-failed', 1, 'tool.result', {
            tool: 'workspace_write_file',
            ok: false,
          }),
          event('tool-ok', 2, 'tool.result', {
            tool: 'generate_html_document',
            ok: true,
          }),
          event('run-ok', 3, 'run.status', { status: 'succeeded' }),
        ]}
      />,
    );

    expect(screen.getByText('失败 · 已恢复')).toBeInTheDocument();
    expect(screen.getByText('运行成功')).toBeInTheDocument();
    // A bare 「失败」 badge must not contradict the terminal success.
    expect(screen.queryByText(/^失败$/)).not.toBeInTheDocument();
  });

  it('labels recovered steps neutrally from the event stream alone (P2-E4)', () => {
    // Surfaces that render the timeline without the `run` prop (automation
    // page) must still derive the terminal success from the run.status event.
    render(
      <RunTimeline
        events={[
          event('tool-failed', 1, 'tool.result', {
            tool: 'generate_html_document',
            ok: false,
          }),
          event('tool-ok', 2, 'tool.result', {
            tool: 'generate_html_document',
            ok: true,
          }),
          event('run-ok', 3, 'run.status', { status: 'succeeded' }),
        ]}
      />,
    );

    expect(screen.getByText('失败 · 已恢复')).toBeInTheDocument();
    expect(screen.getByText('运行成功')).toBeInTheDocument();
    expect(screen.queryByText(/^失败$/)).not.toBeInTheDocument();
  });

  it('keeps a bare failure while the run has not reached a terminal success (P2-E4)', () => {
    // No terminal succeeded event yet: the failed step is still a real failure
    // and must be labeled as such (transient state, run still in progress).
    render(
      <RunTimeline
        events={[
          event('run-running', 1, 'run.status', { status: 'running' }),
          event('tool-failed', 2, 'tool.result', {
            tool: 'workspace_write_file',
            ok: false,
          }),
        ]}
      />,
    );

    expect(screen.getByText('正在运行')).toBeInTheDocument();
    expect(screen.getByText('失败')).toBeInTheDocument();
    expect(screen.queryByText('失败 · 已恢复')).not.toBeInTheDocument();
  });

  it('labels a live Word write as 正在写 Word (T-AGENT-FACE-V1)', () => {
    render(
      <RunTimeline
        run={run('running')}
        events={[event('call', 1, 'tool.call', { tool: 'generate_docx_document' })]}
      />,
    );
    expect(screen.getByText('正在写 Word')).toBeInTheDocument();
    expect(screen.queryByText(/generate_docx_document/)).not.toBeInTheDocument();
  });

  it('shows 在整理上文 for compaction.begin (T-COMPACT-OFFICE-HARD)', () => {
    render(
      <RunTimeline
        run={run('running')}
        events={[
          event('compact', 1, 'compaction.begin', { text: '在整理上文', source: 'true-pi' }),
        ]}
      />,
    );
    expect(screen.getByText('在整理上文')).toBeInTheDocument();
  });

  it('renders clickable search sources and honest miss copy', () => {
    const { rerender } = render(
      <RunTimeline
        events={[
          event('search-ok', 1, 'search.sources', {
            tool: 'web_search',
            honest_miss: false,
            sources: [{ title: 'Gov', url: 'https://www.gov.cn/a' }],
          }),
        ]}
      />,
    );
    const link = screen.getByTestId('pico-timeline-source-link');
    expect(link).toHaveAttribute('href', 'https://www.gov.cn/a');
    expect(link).toHaveTextContent('Gov');

    rerender(
      <RunTimeline
        events={[
          event('search-miss', 1, 'search.sources', {
            tool: 'web_search',
            honest_miss: true,
            sources: [],
          }),
        ]}
      />,
    );
    expect(screen.getByText('未检索到可用来源')).toBeInTheDocument();
    expect(screen.queryByTestId('pico-timeline-source-link')).not.toBeInTheDocument();
  });
});
