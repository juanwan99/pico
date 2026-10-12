import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PaneHandBack, { HAND_BACK_TEXT } from '../PaneHandBack';

const mockSubmit = jest.fn();
let mockSubmitting = false;
jest.mock('~/hooks', () => ({
  useSubmitMessage: () => ({ submitMessage: mockSubmit }),
}));
jest.mock('~/Providers', () => ({
  useChatContext: () => ({ isSubmitting: mockSubmitting }),
}));

/** #1238: the teacher did the password / slider step → one click lets the AI go on. */
describe('PaneHandBack', () => {
  beforeEach(() => {
    mockSubmit.mockReset();
    mockSubmitting = false;
  });

  it('sends the teacher line once and folds away', async () => {
    const user = userEvent.setup();
    render(<PaneHandBack />);
    await user.click(screen.getByTestId('sandbox-continue'));
    expect(mockSubmit).toHaveBeenCalledWith({ text: HAND_BACK_TEXT });
    expect(screen.queryByTestId('sandbox-continue-bar')).not.toBeInTheDocument();
  });

  it('stays when the send is refused, and is disabled while a message is going out', async () => {
    const user = userEvent.setup();
    mockSubmit.mockReturnValue(false);
    const { rerender } = render(<PaneHandBack />);
    await user.click(screen.getByTestId('sandbox-continue'));
    expect(screen.getByTestId('sandbox-continue-bar')).toBeInTheDocument();
    mockSubmitting = true;
    rerender(<PaneHandBack />);
    expect(screen.getByTestId('sandbox-continue')).toBeDisabled();
  });
});
