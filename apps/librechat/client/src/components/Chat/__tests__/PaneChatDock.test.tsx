import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { TMessage } from 'librechat-data-provider';
import PaneChatDock, { latestReplyText } from '../PaneChatDock';

const mockSubmit = jest.fn();
let mockSubmitting = false;
jest.mock('~/hooks', () => ({
  useSubmitMessage: () => ({ submitMessage: mockSubmit }),
}));
jest.mock('~/Providers', () => ({
  useChatContext: () => ({ isSubmitting: mockSubmitting }),
}));

const msgs = [
  { messageId: 'u1', isCreatedByUser: true, text: '帮我打开报名页' },
  { messageId: 'a1', isCreatedByUser: false, text: '已打开报名页，姓名填好了。' },
  { messageId: 'u2', isCreatedByUser: true, text: '再填电话' },
] as unknown as TMessage[];

/** #1226: talk to the AI from under the full-screen sandbox. */
describe('PaneChatDock', () => {
  beforeEach(() => {
    mockSubmit.mockReset();
    mockSubmitting = false;
  });

  it('shows the latest AI reply and sends with Enter', async () => {
    const user = userEvent.setup();
    const onStop = jest.fn();
    render(<PaneChatDock messages={msgs} canStop={false} onStop={onStop} />);
    expect(screen.getByTestId('pane-chat-dock-reply')).toHaveTextContent(
      '已打开报名页，姓名填好了。',
    );
    expect(screen.queryByTestId('pane-chat-dock-stop')).not.toBeInTheDocument();
    await user.type(screen.getByTestId('pane-chat-dock-input'), '电话 13800000000{Enter}');
    expect(mockSubmit).toHaveBeenCalledWith({ text: '电话 13800000000' });
    expect(screen.getByTestId('pane-chat-dock-input')).toHaveValue('');
  });

  it('while the AI runs: status line and 停止 = stop the task', async () => {
    const user = userEvent.setup();
    const onStop = jest.fn();
    mockSubmitting = true;
    render(
      <PaneChatDock
        messages={msgs}
        processHint="正在填表"
        canStop
        onStop={onStop}
        askBar={<div data-testid="ask-stub" />}
      />,
    );
    expect(screen.getByTestId('pane-chat-dock-status')).toHaveTextContent('正在填表');
    expect(screen.getByTestId('ask-stub')).toBeInTheDocument();
    expect(screen.getByTestId('pane-chat-dock-send')).toBeDisabled();
    await user.click(screen.getByTestId('pane-chat-dock-stop'));
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it('latestReplyText skips the teacher and reads content parts', () => {
    const parts = [
      {
        messageId: 'a',
        isCreatedByUser: false,
        text: '',
        content: [{ type: 'text', text: '分段回复' }],
      },
      { messageId: 'u', isCreatedByUser: true, text: '好' },
    ] as unknown as TMessage[];
    expect(latestReplyText(parts)).toBe('分段回复');
    const failed = [
      {
        messageId: 'e',
        isCreatedByUser: false,
        error: true,
        text: 'Unhandled error type 403 status code (no body)',
      },
    ] as unknown as TMessage[];
    expect(latestReplyText(failed)).toBe('这次没完成。请再发一次。');
    const errorPart = [
      {
        messageId: 'e2',
        isCreatedByUser: false,
        content: [{ type: 'error', error: 'An error occurred while processing the request: 403' }],
      },
    ] as unknown as TMessage[];
    expect(latestReplyText(errorPart)).toBe('这次没完成。请再发一次。');
    expect(latestReplyText([])).toBe('');
  });
});
