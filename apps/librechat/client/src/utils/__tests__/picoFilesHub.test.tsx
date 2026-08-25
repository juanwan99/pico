/**
 * T-FILES-PLACE: 我的文件 page can create folders and offer school transfer.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FilesHubPage from '~/components/Workbench/FilesHubPage';
import {
  createMyFolder,
  listEduFields,
  listMyFolders,
  listMyPicoArtifacts,
  searchEduSchoolMaterials,
} from '~/data-provider/pico/api';

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

jest.mock('~/components/ui/pico-icons', () => ({
  PicoIcon: () => <span />,
}));

jest.mock('~/components/Workbench/WorkbenchShell', () => ({
  __esModule: true,
  default: ({ title, children, actions }: { title: string; children: React.ReactNode; actions?: React.ReactNode }) => (
    <div>
      <h1>{title}</h1>
      {actions}
      {children}
    </div>
  ),
}));

jest.mock('~/data-provider/pico/api', () => ({
  createMyFolder: jest.fn(),
  getPicoArtifactContent: jest.fn(),
  listEduFields: jest.fn(),
  listMyFolders: jest.fn(),
  listMyPicoArtifacts: jest.fn(),
  searchEduSchoolMaterials: jest.fn(),
  transferMyArtifact: jest.fn(),
}));

const mockCreate = createMyFolder as jest.MockedFunction<typeof createMyFolder>;
const mockFields = listEduFields as jest.MockedFunction<typeof listEduFields>;
const mockFolders = listMyFolders as jest.MockedFunction<typeof listMyFolders>;
const mockMine = listMyPicoArtifacts as jest.MockedFunction<typeof listMyPicoArtifacts>;
const mockSearch = searchEduSchoolMaterials as jest.MockedFunction<typeof searchEduSchoolMaterials>;

describe('FilesHubPage my files', () => {
  beforeEach(() => {
    mockSearch.mockResolvedValue({ configured: false, items: [] });
    mockFields.mockResolvedValue({ fields: [{ id: 'field-1', name: '本学期排课' }] });
    mockFolders.mockResolvedValue({ folders: [] });
    mockMine.mockResolvedValue({
      artifacts: [{ id: 'art-1', title: '通知.html', kind: 'html' }],
    });
    mockCreate.mockResolvedValue({ folder: { id: 'fold-1', name: '备课' } });
  });

  it('can create a folder and transfer a file, without 落到哪一场', async () => {
    render(
      <MemoryRouter initialEntries={['/more/files']}>
        <FilesHubPage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('my-files-create-folder')).toBeInTheDocument();
    expect(await screen.findByTestId('my-files-transfer-art-1')).toBeInTheDocument();
    expect(screen.queryByText('落到哪一场')).not.toBeInTheDocument();
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
