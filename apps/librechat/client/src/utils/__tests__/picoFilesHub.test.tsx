/**
 * T-FILES-PLACE: left file directory can create folders and transfer to school.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import FilesDirectoryPanel from '~/components/Workbench/FilesDirectoryPanel';
import {
  createMyFolder,
  listEduFields,
  listMyFolders,
  listMyPicoArtifacts,
  renameMyFolder,
} from '~/data-provider/pico/api';

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

jest.mock('~/data-provider/pico/api', () => ({
  createMyFolder: jest.fn(),
  getPicoArtifactContent: jest.fn(),
  listEduFields: jest.fn(),
  listMyFolders: jest.fn(),
  listMyPicoArtifacts: jest.fn(),
  renameMyFolder: jest.fn(),
  transferMyArtifact: jest.fn(),
}));

const mockCreate = createMyFolder as jest.MockedFunction<typeof createMyFolder>;
const mockRename = renameMyFolder as jest.MockedFunction<typeof renameMyFolder>;
const mockFields = listEduFields as jest.MockedFunction<typeof listEduFields>;
const mockFolders = listMyFolders as jest.MockedFunction<typeof listMyFolders>;
const mockMine = listMyPicoArtifacts as jest.MockedFunction<typeof listMyPicoArtifacts>;

describe('FilesDirectoryPanel', () => {
  beforeEach(() => {
    mockFields.mockResolvedValue({ fields: [{ id: 'field-1', name: '本学期排课' }] });
    mockFolders.mockResolvedValue({ folders: [] });
    mockMine.mockResolvedValue({
      artifacts: [{ id: 'art-1', title: '通知.html', kind: 'html' }],
    });
    mockCreate.mockResolvedValue({ folder: { id: 'fold-1', name: '新建文件夹' } });
    mockRename.mockResolvedValue({ folder: { id: 'fold-1', name: '备课' } });
    mockFolders
      .mockResolvedValueOnce({ folders: [] })
      .mockResolvedValue({ folders: [{ id: 'fold-1', name: '新建文件夹' }] });
  });

  it('creates a folder like Explorer then renames, and can transfer', async () => {
    render(<FilesDirectoryPanel />);
    expect(await screen.findByTestId('files-directory')).toBeInTheDocument();
    expect(await screen.findByTestId('my-files-transfer-art-1')).toBeInTheDocument();
    expect(screen.queryByText('落到哪一场')).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('新夹名')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('my-files-create-folder'));
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith('');
    });
    const rename = await screen.findByTestId('my-files-folder-rename-fold-1');
    fireEvent.change(rename, { target: { value: '备课' } });
    fireEvent.blur(rename);
    await waitFor(() => {
      expect(mockRename).toHaveBeenCalledWith('fold-1', '备课');
    });
    fireEvent.click(screen.getByTestId('my-files-transfer-art-1'));
    expect(await screen.findByTestId('my-files-transfer-dialog')).toBeInTheDocument();
    expect(screen.getByTestId('my-files-transfer-field')).toBeInTheDocument();
  });
});
