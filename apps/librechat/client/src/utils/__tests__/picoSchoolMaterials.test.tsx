/**
 * T-FILES-PLACE: opening school materials shows a venue folder tree.
 * No search-first, no landing dropdown. Open = fields only; docs lazy on expand.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import SchoolMaterialsBar from '~/components/Chat/SchoolMaterialsBar';
import {
  getEduNamedIds,
  listEduFields,
  putEduNamedIds,
  searchEduSchoolMaterials,
} from '~/data-provider/pico/api';

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

jest.mock('~/components/ui/pico-icons', () => ({
  PicoIcon: ({ name }: { name: string }) => <span data-testid={`pico-icon-${name}`} />,
}));

jest.mock('~/data-provider/pico/api', () => ({
  getEduNamedIds: jest.fn(),
  listEduFields: jest.fn(),
  putEduNamedIds: jest.fn(),
  searchEduSchoolMaterials: jest.fn(),
}));

const mockGetEduNamedIds = getEduNamedIds as jest.MockedFunction<typeof getEduNamedIds>;
const mockListEduFields = listEduFields as jest.MockedFunction<typeof listEduFields>;
const mockPutEduNamedIds = putEduNamedIds as jest.MockedFunction<typeof putEduNamedIds>;
const mockSearch = searchEduSchoolMaterials as jest.MockedFunction<typeof searchEduSchoolMaterials>;

describe('SchoolMaterialsBar venue folder tree', () => {
  beforeEach(() => {
    mockGetEduNamedIds.mockResolvedValue({ ids: [] });
    mockListEduFields.mockResolvedValue({
      fields: [
        { id: 'field-1', name: '本学期排课' },
        { id: 'field-2', name: '一年级语文', followed: true },
      ],
    });
    mockPutEduNamedIds.mockResolvedValue({ ids: [] });
    mockSearch.mockImplementation(async (_q: string, fieldId = '') => {
      if (fieldId === 'field-1') {
        return { items: [{ id: 'doc-1', title: '课时计划.docx', fieldId: 'field-1' }] };
      }
      if (fieldId === 'field-2') {
        return { items: [{ id: 'doc-2', title: '课文.docx', fieldId: 'field-2' }] };
      }
      return { items: [] };
    });
  });

  it('uses the shared chrome row and a single caret', () => {
    render(<SchoolMaterialsBar conversationId="c1" />);
    const toggle = screen.getByTestId('school-materials-toggle');
    expect(toggle.tagName).toBe('BUTTON');
    expect(toggle.querySelectorAll('.pico-chrome-caret')).toHaveLength(1);
    expect(screen.getByText('学校材料')).toBeInTheDocument();
  });

  it('opens into venue folders without materials fan-out; docs load on expand', async () => {
    render(<SchoolMaterialsBar conversationId="c1" />);
    fireEvent.click(screen.getByTestId('school-materials-toggle'));

    expect(await screen.findByTestId('school-field-folder-field-1')).toBeInTheDocument();
    expect(screen.queryByTestId('school-field-folder-field-2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('school-follow-folder-field-2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('school-material-doc-1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('school-materials-q')).not.toBeInTheDocument();
    expect(screen.queryByText('搜')).not.toBeInTheDocument();
    expect(screen.queryByText('落到哪一场')).not.toBeInTheDocument();
    expect(screen.queryByTestId('school-land-field')).not.toBeInTheDocument();
    await waitFor(() => {
      expect(mockListEduFields).toHaveBeenCalled();
      expect(mockSearch).not.toHaveBeenCalled();
    });

    fireEvent.click(screen.getByTestId('school-field-toggle-field-1'));
    expect(await screen.findByTestId('school-material-doc-1')).toBeInTheDocument();
    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith('', 'field-1');
      expect(mockSearch).toHaveBeenCalledTimes(1);
    });
  });

  it('closes the tree when clicking outside', async () => {
    render(
      <div>
        <SchoolMaterialsBar conversationId="c1" />
        <button type="button">outside</button>
      </div>,
    );
    fireEvent.click(screen.getByTestId('school-materials-toggle'));
    expect(await screen.findByTestId('school-materials-tree')).toBeInTheDocument();
    fireEvent.pointerDown(screen.getByText('outside'));
    expect(screen.queryByTestId('school-materials-tree')).not.toBeInTheDocument();
  });

  it('can check documents from two venues', async () => {
    mockPutEduNamedIds.mockImplementation(async (_convo: string, ids: string[]) => ({ ids }));

    render(<SchoolMaterialsBar conversationId="c1" />);
    fireEvent.click(screen.getByTestId('school-materials-toggle'));
    fireEvent.click(await screen.findByTestId('school-field-toggle-field-1'));
    fireEvent.click(await screen.findByTestId('school-followed-toggle'));
    fireEvent.click(await screen.findByTestId('school-follow-toggle-field-2'));
    fireEvent.click(await screen.findByTestId('school-material-doc-1'));
    fireEvent.click(await screen.findByTestId('school-material-doc-2'));

    await waitFor(() => {
      expect(mockPutEduNamedIds).toHaveBeenCalledWith('c1', ['doc-1', 'doc-2'], '');
    });
  });

  it('splits manage left and followed right; followed stays folded', async () => {
    render(<SchoolMaterialsBar conversationId="c1" />);
    fireEvent.click(screen.getByTestId('school-materials-toggle'));

    expect(await screen.findByTestId('school-materials-mine')).toBeInTheDocument();
    expect(screen.getByText('我负责的')).toBeInTheDocument();
    expect(await screen.findByTestId('school-field-folder-field-1')).toBeInTheDocument();
    expect(screen.getByTestId('school-followed-toggle')).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('school-follow-folder-field-2')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('school-followed-toggle'));
    expect(screen.getByTestId('school-followed-toggle')).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('school-follow-folder-field-2')).toBeInTheDocument();
    expect(screen.queryByTestId('school-field-folder-field-2')).not.toBeInTheDocument();
  });
});
