import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { deletePicoMemory, listPicoMemory } from '~/data-provider/pico/api';
import MemoryStrip from '../MemoryStrip';

jest.mock('~/data-provider/pico/api', () => ({
  listPicoMemory: jest.fn(),
  deletePicoMemory: jest.fn(),
}));

const mockList = listPicoMemory as jest.MockedFunction<typeof listPicoMemory>;
const mockDelete = deletePicoMemory as jest.MockedFunction<typeof deletePicoMemory>;

describe('MemoryStrip', () => {
  beforeEach(() => {
    mockList.mockReset();
    mockDelete.mockReset();
  });

  it('shows empty copy when there is no memory', async () => {
    mockList.mockResolvedValue({ files: [] });
    render(<MemoryStrip />);
    expect(await screen.findByText('暂无跨窗短记')).toBeInTheDocument();
  });

  it('lists a memory file and deletes it', async () => {
    mockList
      .mockResolvedValueOnce({ files: [{ name: 'MEMORY.md', text: '我要简体' }] })
      .mockResolvedValueOnce({ files: [] });
    mockDelete.mockResolvedValue({ ok: true, name: 'MEMORY.md' });
    render(<MemoryStrip />);
    expect(await screen.findByText('MEMORY.md')).toBeInTheDocument();
    expect(screen.getByText('我要简体')).toBeInTheDocument();
    await userEvent.click(screen.getByTestId('pico-memory-delete'));
    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith('MEMORY.md'));
  });
});
