import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { PicoTask } from '~/data-provider/pico/api';
import TeacherTaskHome, { recoverableTasks, taskTimeValue } from './TeacherTaskHome';

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

jest.mock('~/hooks', () => ({
  useLocalize: () => (key: string) =>
    (
      ({
        com_ui_pico_task_history_loading: '任务历史加载中…',
        com_ui_pico_task_history_empty: '暂无任务记录',
        com_ui_retry: '重试',
      }) as Record<string, string>
    )[key] || key,
}));

function renderHome(props?: Partial<React.ComponentProps<typeof TeacherTaskHome>>) {
  return render(
    <MemoryRouter>
      <TeacherTaskHome
        tasks={[]}
        loading={false}
        error={null}
        onRetry={() => undefined}
        onOpen={() => undefined}
        {...props}
      />
    </MemoryRouter>,
  );
}

describe('TeacherTaskHome', () => {
  const tasks: PicoTask[] = [
    {
      id: 'task-failed',
      title: '失败后待处理',
      conversation_id: 'conversation 1',
      created_at: '2026-08-02T03:00:00Z',
      latest_run: {
        id: 'run-failed',
        status: 'failed',
        ended_at: '2026-08-02T04:00:00Z',
      },
    },
    {
      id: 'task-unbound',
      title: '未关联任务',
      latest_run: { id: 'run-unbound', status: 'running' },
    },
  ];

  it('shows recoverable task title, latest-run status and time linked to its conversation', () => {
    const onOpen = jest.fn();
    renderHome({ tasks, onOpen });

    const row = screen.getByTestId('teacher-task-row');
    expect(row).toHaveAttribute('href', '/c/conversation%201');
    expect(screen.getByText('失败后待处理')).toBeInTheDocument();
    expect(screen.getByTestId('teacher-task-status')).toHaveTextContent('失败');
    expect(screen.queryByText('未关联任务')).not.toBeInTheDocument();
    expect(row).not.toHaveTextContent('时间未知');

    fireEvent.click(row);
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it('renders short loading, empty and retryable failure states', () => {
    const { rerender } = renderHome({ loading: true });
    expect(screen.getByRole('status')).toHaveTextContent('任务历史加载中');

    const onRetry = jest.fn();
    rerender(
      <MemoryRouter>
        <TeacherTaskHome
          tasks={[]}
          loading={false}
          error="任务历史暂不可用，请稍后重试"
          onRetry={onRetry}
          onOpen={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('任务历史暂不可用，请稍后重试');
    expect(screen.queryByText('暂无任务记录')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('shows an honest empty state after a successful empty response', () => {
    renderHome();
    expect(screen.getByTestId('teacher-task-empty')).toHaveTextContent('暂无任务记录');
    expect(screen.getByTestId('teacher-task-empty-start')).toHaveAttribute('href', '/c/new');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows a short failure hint for failed runs and groups by day', () => {
    const withError: PicoTask[] = [
      {
        id: 'task-failed',
        title: '失败后待处理',
        conversation_id: 'conversation-1',
        created_at: '2026-08-02T03:00:00Z',
        latest_run: {
          id: 'run-failed',
          status: 'failed',
          error: '处理超时',
          ended_at: '2026-08-02T04:00:00Z',
        },
      },
    ];
    renderHome({ tasks: withError });
    expect(screen.getByTestId('teacher-task-fail-hint')).toHaveTextContent('处理超时');
    expect(screen.getByTestId('teacher-task-day-groups')).toBeInTheDocument();
  });

  it('uses the latest-run time and keeps only conversation-bound tasks', () => {
    expect(taskTimeValue(tasks[0])).toBe('2026-08-02T04:00:00Z');
    expect(recoverableTasks(tasks).map((task) => task.id)).toEqual(['task-failed']);
  });
});
