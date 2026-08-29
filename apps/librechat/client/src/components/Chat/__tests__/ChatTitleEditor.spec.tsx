import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ChatTitleEditor from '../ChatTitleEditor';

const mockMutateAsync = jest.fn();

jest.mock('~/data-provider', () => ({
  useUpdateConversationMutation: () => ({ mutateAsync: mockMutateAsync }),
}));

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

describe('ChatTitleEditor', () => {
  beforeEach(() => {
    mockMutateAsync.mockReset();
    mockMutateAsync.mockResolvedValue({});
  });

  it('hides until the conversation has a real id', () => {
    render(<ChatTitleEditor conversationId="new" title="New Chat" />);
    expect(screen.queryByTestId('chat-title')).not.toBeInTheDocument();
  });

  it('shows 新对话 for unnamed titles and saves a rename', async () => {
    render(<ChatTitleEditor conversationId="c1" title="New Chat" />);
    expect(screen.getByTestId('chat-title')).toHaveTextContent('新对话');
    fireEvent.click(screen.getByTestId('chat-title'));
    const input = screen.getByTestId('chat-title-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '期末复习' } });
    fireEvent.submit(screen.getByTestId('chat-title-form'));
    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({ conversationId: 'c1', title: '期末复习' });
    });
  });
});
