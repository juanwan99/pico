/**
 * T-FILES-PLACE: left file directory can create folders and transfer to school.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import FilesDirectoryPanel from '~/components/Workbench/FilesDirectoryPanel';
import { createMyFolder, listEduFields, listMyFolders, listMyPicoArtifacts } from '~/data-provider/pico/api';

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

jest.mock('~/data-provider/pico/api', () => ({
  createMyFolder: jest.fn(),
  getPicoArtifactContent: jest.fn(),
  listEduFields: jest.fn(),
  listMyFolders: jest.fn(),
  listMyPicoArtifacts: jest.fn(),
  transferMyArtifact: jest.fn(),
}));

const mockCreate = createMyFolder as jest.MockedFunction<typeof createMyFolder>;
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
    mockCreate.mockResolvedValue({ folder: { id: 'fold-1', name: '备课' } });
  });

  it('can create a folder and transfer a file, without 落到哪一场 or search', async () => {
    render(<FilesDirectoryPanel />);
    expect(await screen.findByTestId('files-directory')).toBeInTheDocument();
    expect(await screen.findByTestId('my-files-transfer-art-1')).toBeInTheDocument();
    expect(screen.queryByText('落到哪一场')).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('搜索学校材料标题')).not.toBeInTheDocument();
    fireEvent.change(screen.getByTestId('my-files-folder-name'), { target: { value: '备课' } });
    fireEvent.click(screen.getByTestId('my-files-create-folder'));
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith('备课');
    });
    fireEvent.click(screen.getByTestId('my-files-transfer-art-1'));
    expect(await screen.findByTestId('my-files-transfer-dialog')).toBeInTheDocument();
    expect(screen.getByTestId('my-files-transfer-field')).toBeInTheDocument();
  });
});
