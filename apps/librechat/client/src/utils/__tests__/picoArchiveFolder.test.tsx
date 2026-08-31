/**
 * T-FILES-PLACE: dialog archive location is 我的文件, not a school venue.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ArchiveFolderBar from '~/components/Chat/ArchiveFolderBar';
import { getMyArchiveFolder, listMyFolders, putMyArchiveFolder } from '~/data-provider/pico/api';

jest.mock('~/data-provider/pico/api', () => ({
  getMyArchiveFolder: jest.fn(),
  listMyFolders: jest.fn(),
  putMyArchiveFolder: jest.fn(),
}));

const mockGet = getMyArchiveFolder as jest.MockedFunction<typeof getMyArchiveFolder>;
const mockList = listMyFolders as jest.MockedFunction<typeof listMyFolders>;
const mockPut = putMyArchiveFolder as jest.MockedFunction<typeof putMyArchiveFolder>;

describe('ArchiveFolderBar', () => {
  beforeEach(() => {
    mockGet.mockResolvedValue({ folder_id: '', folder_name: '' });
    mockList.mockResolvedValue({ folders: [{ id: 'fold-1', name: '备课' }] });
    mockPut.mockResolvedValue({ folder_id: 'fold-1', folder_name: '备课' });
  });

  it('defaults to 我的文件 and can pick a self-made folder', async () => {
    render(<ArchiveFolderBar conversationId="c1" />);
    expect(screen.getByTestId('archive-folder-select')).toHaveTextContent('我的文件');
    expect(screen.getByText('存档位置')).toBeInTheDocument();
    expect(screen.queryByText('落到哪一场')).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('archive-folder-select'));
    expect(await screen.findByRole('option', { name: '备课' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('option', { name: '备课' }));
    await waitFor(() => {
      expect(mockPut).toHaveBeenCalledWith('c1', 'fold-1');
    });
  });

  it('uses one custom caret and no native select arrow', async () => {
    render(<ArchiveFolderBar conversationId="c1" />);
    const toggle = screen.getByTestId('archive-folder-select');
    expect(toggle.tagName).toBe('BUTTON');
    expect(toggle.querySelectorAll('.pico-chrome-caret')).toHaveLength(1);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });
});
