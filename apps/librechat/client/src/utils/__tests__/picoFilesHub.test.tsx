/**
 * T-FILES-PLACE: Explorer folder tree, create/rename, transfer to school.
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

jest.mock('~/components/ui/pico-icons', () => ({
  PicoIcon: ({ name }: { name: string }) => <span data-testid={`pico-icon-${name}`} />,
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
    jest.clearAllMocks();
    mockFields.mockResolvedValue({ fields: [{ id: 'field-1', name: '本学期排课' }] });
    mockMine.mockResolvedValue({
      artifacts: [{ id: 'art-1', title: '通知.html', kind: 'html' }],
    });
    mockCreate.mockResolvedValue({ folder: { id: 'fold-1', name: '新建文件夹', parent_id: '' } });
    mockRename.mockResolvedValue({ folder: { id: 'fold-1', name: '备课', parent_id: '' } });
    mockFolders.mockResolvedValue({ folders: [] });
  });

  it('creates a folder like Explorer then renames, keeps tree and folder icons, can transfer', async () => {
    mockFolders
      .mockResolvedValueOnce({ folders: [] })
      .mockResolvedValue({ folders: [{ id: 'fold-1', name: '新建文件夹', parent_id: '' }] });
    render(<FilesDirectoryPanel />);
    expect(await screen.findByTestId('files-directory')).toBeInTheDocument();
    expect(await screen.findByTestId('my-files-tree')).toBeInTheDocument();
    expect(await screen.findByTestId('my-files-transfer-art-1')).toBeInTheDocument();
    expect(screen.getAllByTestId('pico-icon-folder-open').length).toBeGreaterThan(0);
    expect(screen.queryByText('落到哪一场')).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('新夹名')).not.toBeInTheDocument();
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
    expect(screen.getByTestId('my-files-tree')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('my-files-transfer-art-1'));
    expect(await screen.findByTestId('my-files-transfer-dialog')).toBeInTheDocument();
    expect(screen.getByTestId('my-files-transfer-field')).toBeInTheDocument();
  });

  it('can create a nested folder inside the current folder', async () => {
    mockFolders.mockResolvedValue({
      folders: [{ id: 'fold-1', name: '备课', parent_id: '' }],
    });
    mockCreate.mockResolvedValue({
      folder: { id: 'fold-2', name: '新建文件夹', parent_id: 'fold-1' },
    });
    render(<FilesDirectoryPanel />);
    expect(await screen.findByTestId('my-files-folder-fold-1')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('my-files-folder-fold-1'));
    await waitFor(() => {
      expect(mockMine).toHaveBeenCalledWith('fold-1');
    });
    fireEvent.click(screen.getByTestId('my-files-create-folder'));
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith('', 'fold-1');
    });
  });
});
