/**
 * T-FILES-PLACE: sidebar tree — new-first under open folder, delete empty, transfer.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import FilesDirectoryPanel from '~/components/Workbench/FilesDirectoryPanel';
import {
  createMyFolder,
  deleteMyFolder,
  listEduFields,
  listMyFolders,
  listMyPicoArtifacts,
  renameMyFolder,
} from '~/data-provider/pico/api';

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

jest.mock('~/components/ui/pico-icons', () => ({
  PicoIcon: ({ name }: { name: string }) => <span data-testid={`pico-icon-${name}`} />,
}));

jest.mock('~/data-provider/pico/api', () => ({
  createMyFolder: jest.fn(),
  deleteMyFolder: jest.fn(),
  getPicoArtifactContent: jest.fn(),
  listEduFields: jest.fn(),
  listMyFolders: jest.fn(),
  listMyPicoArtifacts: jest.fn(),
  renameMyFolder: jest.fn(),
  transferMyArtifact: jest.fn(),
}));

const mockCreate = createMyFolder as jest.MockedFunction<typeof createMyFolder>;
const mockDelete = deleteMyFolder as jest.MockedFunction<typeof deleteMyFolder>;
const mockRename = renameMyFolder as jest.MockedFunction<typeof renameMyFolder>;
const mockFields = listEduFields as jest.MockedFunction<typeof listEduFields>;
const mockFolders = listMyFolders as jest.MockedFunction<typeof listMyFolders>;
const mockMine = listMyPicoArtifacts as jest.MockedFunction<typeof listMyPicoArtifacts>;

describe('FilesDirectoryPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFields.mockResolvedValue({ fields: [{ id: 'field-1', name: '本学期排课' }] });
    mockMine.mockResolvedValue({
      artifacts: [{ id: 'art-1', title: '通知.html', kind: 'html', folder_id: '' }],
    });
    mockCreate.mockResolvedValue({ folder: { id: 'fold-1', name: '新建文件夹', parent_id: '' } });
    mockRename.mockResolvedValue({ folder: { id: 'fold-1', name: '备课', parent_id: '' } });
    mockDelete.mockResolvedValue({ ok: true, id: 'fold-1' });
    mockFolders.mockResolvedValue({ folders: [] });
  });

  it('creates under open root via first new icon, renames, keeps tree icons, can transfer', async () => {
    mockFolders
      .mockResolvedValueOnce({ folders: [] })
      .mockResolvedValue({ folders: [{ id: 'fold-1', name: '新建文件夹', parent_id: '' }] });
    render(<FilesDirectoryPanel />);
    expect(await screen.findByTestId('files-directory')).toBeInTheDocument();
    expect(await screen.findByTestId('my-files-tree')).toBeInTheDocument();
    expect(screen.queryByText('当前文件夹')).not.toBeInTheDocument();
    expect(await screen.findByTestId('my-files-transfer-art-1')).toBeInTheDocument();
    expect(screen.getAllByTestId('pico-icon-folder-open').length).toBeGreaterThan(0);
    // Edu fields are not fetched until 转到学校 opens.
    expect(mockFields).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('my-files-create-folder'));
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith('', '');
    });
    const rename = await screen.findByTestId('my-files-folder-rename-fold-1');
    fireEvent.change(rename, { target: { value: '备课' } });
    fireEvent.blur(rename);
    await waitFor(() => {
      expect(mockRename).toHaveBeenCalledWith('fold-1', '备课');
    });
    fireEvent.click(screen.getByTestId('my-files-transfer-art-1'));
    expect(await screen.findByTestId('my-files-transfer-dialog')).toBeInTheDocument();
    await waitFor(() => {
      expect(mockFields).toHaveBeenCalled();
    });
  });

  it('creates nested folder as first icon under an opened folder', async () => {
    mockFolders.mockResolvedValue({
      folders: [{ id: 'fold-1', name: '备课', parent_id: '' }],
    });
    mockCreate.mockResolvedValue({
      folder: { id: 'fold-2', name: '新建文件夹', parent_id: 'fold-1' },
    });
    render(<FilesDirectoryPanel />);
    expect(await screen.findByTestId('my-files-folder-fold-1')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('my-files-tree-toggle-fold-1'));
    expect(await screen.findByTestId('my-files-create-folder-fold-1')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('my-files-create-folder-fold-1'));
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith('', 'fold-1');
    });
  });

  it('deletes an empty folder and blocks non-empty', async () => {
    mockFolders.mockResolvedValue({
      folders: [
        { id: 'empty-1', name: '空夹', parent_id: '' },
        { id: 'full-1', name: '有文件', parent_id: '' },
      ],
    });
    mockMine.mockResolvedValue({
      artifacts: [{ id: 'art-2', title: '页.html', kind: 'html', folder_id: 'full-1' }],
    });
    render(<FilesDirectoryPanel />);
    expect(await screen.findByTestId('my-files-folder-delete-empty-1')).toBeEnabled();
    expect(screen.getByTestId('my-files-folder-delete-full-1')).toBeDisabled();
    fireEvent.click(screen.getByTestId('my-files-folder-delete-empty-1'));
    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith('empty-1');
    });
  });
});
