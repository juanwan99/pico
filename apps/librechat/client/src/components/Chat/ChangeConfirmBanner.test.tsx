import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  confirmPicoChange,
  listPicoChanges,
  rejectPicoChange,
  type PicoChange,
} from '~/data-provider/pico/api';
import ChangeConfirmBanner from './ChangeConfirmBanner';

jest.mock('~/data-provider/pico/api', () => ({
  confirmPicoChange: jest.fn(),
  listPicoChanges: jest.fn(),
  rejectPicoChange: jest.fn(),
}));

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

const mockListPicoChanges = listPicoChanges as jest.MockedFunction<typeof listPicoChanges>;
const mockConfirmPicoChange = confirmPicoChange as jest.MockedFunction<typeof confirmPicoChange>;
const mockRejectPicoChange = rejectPicoChange as jest.MockedFunction<typeof rejectPicoChange>;

const proposed: PicoChange = {
  id: 'change-1',
  task_id: 'task-1',
  title: '更新课程时间',
  summary: '将周三课程调整到下午三点。',
  status: 'proposed',
};

function terminal(status: 'confirmed' | 'rejected'): PicoChange {
  return {
    ...proposed,
    status,
    confirmed_by: status === 'confirmed' ? 'member-1' : null,
  };
}

describe('ChangeConfirmBanner', () => {
  beforeEach(() => {
    mockListPicoChanges.mockResolvedValue({ changes: [] });
  });

  it('renders nothing when the task has no change proposal', async () => {
    const { container } = render(<ChangeConfirmBanner taskId="task-1" />);

    await waitFor(() => expect(mockListPicoChanges).toHaveBeenCalledWith({ taskId: 'task-1' }));
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/待确认业务变更/)).not.toBeInTheDocument();
  });

  it('shows a proposed change title, summary, status, and actions', async () => {
    mockListPicoChanges.mockResolvedValue({ changes: [proposed] });

    render(<ChangeConfirmBanner taskId="task-1" />);

    expect(await screen.findByText('更新课程时间')).toBeInTheDocument();
    expect(screen.getByText('将周三课程调整到下午三点。')).toBeInTheDocument();
    expect(screen.getByText('待确认')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '确认' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '拒绝' })).toBeEnabled();
  });

  it('confirms, refreshes the list, and refreshes the parent ledger', async () => {
    const confirmed = terminal('confirmed');
    const onChanged = jest.fn();
    mockListPicoChanges
      .mockResolvedValueOnce({ changes: [proposed] })
      .mockResolvedValue({ changes: [confirmed] });
    mockConfirmPicoChange.mockResolvedValue({ change: confirmed });
    const user = userEvent.setup();
    render(<ChangeConfirmBanner taskId="task-1" onChanged={onChanged} />);

    await user.click(await screen.findByRole('button', { name: '确认' }));

    await waitFor(() => expect(screen.getByText('已确认')).toBeInTheDocument());
    expect(screen.getByText('变更已确认，状态已刷新')).toBeInTheDocument();
    expect(mockConfirmPicoChange).toHaveBeenCalledWith('change-1');
    expect(mockListPicoChanges).toHaveBeenCalledTimes(2);
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: '确认' })).not.toBeInTheDocument();
  });

  it('rejects and refreshes to an explicit rejected state', async () => {
    const rejected = terminal('rejected');
    mockListPicoChanges
      .mockResolvedValueOnce({ changes: [proposed] })
      .mockResolvedValue({ changes: [rejected] });
    mockRejectPicoChange.mockResolvedValue({ change: rejected });
    const user = userEvent.setup();
    render(<ChangeConfirmBanner taskId="task-1" />);

    await user.click(await screen.findByRole('button', { name: '拒绝' }));

    await waitFor(() => expect(screen.getByText('已拒绝')).toBeInTheDocument());
    expect(screen.getByText('变更已拒绝，状态已刷新')).toBeInTheDocument();
    expect(mockRejectPicoChange).toHaveBeenCalledWith('change-1');
    expect(mockListPicoChanges).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('button', { name: '拒绝' })).not.toBeInTheDocument();
  });

  it('refreshes after an action failure and never exposes a raw upstream error', async () => {
    mockListPicoChanges.mockResolvedValue({ changes: [proposed] });
    mockConfirmPicoChange.mockRejectedValue(
      new Error('pico 500: database password and internal stack trace'),
    );
    const user = userEvent.setup();
    render(<ChangeConfirmBanner taskId="task-1" />);

    await user.click(await screen.findByRole('button', { name: '确认' }));

    expect(await screen.findByText('确认变更失败，请稍后重试')).toBeInTheDocument();
    expect(mockListPicoChanges).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(/database password/)).not.toBeInTheDocument();
    expect(screen.getByText('待确认')).toBeInTheDocument();
  });

  it('does not display changes returned for another task', async () => {
    mockListPicoChanges.mockResolvedValue({
      changes: [{ ...proposed, task_id: 'task-2' }],
    });
    const { container } = render(<ChangeConfirmBanner taskId="task-1" />);

    await waitFor(() => expect(mockListPicoChanges).toHaveBeenCalledTimes(1));
    expect(container).toBeEmptyDOMElement();
  });
});
