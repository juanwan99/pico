import { render, screen } from '@testing-library/react';
import TaskRunBar from '../TaskRunBar';

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

jest.mock('~/components/ui/pico-icons', () => ({
  PicoIcon: () => null,
}));

describe('TaskRunBar parked ask', () => {
  it('shows a static 在等你选 badge instead of the generating spinner', () => {
    render(
      <TaskRunBar
        isSubmitting
        canCancel
        waitingAsk
        processHint="在等你选"
      />,
    );
    expect(screen.getByTestId('task-waiting-ask')).toHaveTextContent('在等你选');
    expect(screen.queryByText('等待模型响应')).not.toBeInTheDocument();
    expect(screen.getByTestId('task-stop-button')).toBeInTheDocument();
  });

  it('still spins 等待模型响应 when the model is actually generating', () => {
    render(<TaskRunBar isSubmitting canCancel />);
    expect(screen.getByRole('status')).toHaveTextContent('等待模型响应');
    expect(screen.queryByTestId('task-waiting-ask')).not.toBeInTheDocument();
  });

  it('does not repeat the conversation title', () => {
    render(<TaskRunBar isSubmitting={false} completedLabel="已完成" />);
    expect(screen.queryByText('当前任务')).not.toBeInTheDocument();
    expect(screen.getByTestId('task-run-column').className).toContain('max-w-[797px]');
  });
});
