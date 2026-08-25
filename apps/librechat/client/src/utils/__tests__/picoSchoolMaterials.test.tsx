/**
 * T-FILES-PLACE: school materials are venue folders; check across venues.
 * Dialog has no landing destination.
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

describe('SchoolMaterialsBar venue folders + cross-venue check', () => {
  beforeEach(() => {
    mockGetEduNamedIds.mockResolvedValue({ ids: [] });
    mockListEduFields.mockResolvedValue({
      fields: [
        { id: 'field-1', name: '本学期排课' },
        { id: 'field-2', name: '一年级语文' },
      ],
    });
    mockPutEduNamedIds.mockResolvedValue({ ids: [] });
    mockSearch.mockResolvedValue({ items: [] });
  });

  it('lists documents under venue folders without a landing picker', async () => {
    mockSearch.mockResolvedValue({
      items: [
        { id: 'doc-1', title: '课时计划.docx', fieldId: 'field-1' },
        { id: 'doc-2', title: '课文.docx', fieldId: 'field-2' },
      ],
    });

    render(<SchoolMaterialsBar conversationId="c1" />);
    fireEvent.click(screen.getByTestId('school-materials-toggle'));

    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith('', '');
    });
    expect(await screen.findByTestId('school-material-doc-1')).toBeInTheDocument();
    expect(screen.getByTestId('school-material-doc-2')).toBeInTheDocument();
    expect(screen.getByTestId('school-field-folder-field-1')).toBeInTheDocument();
    expect(screen.getByTestId('school-field-folder-field-2')).toBeInTheDocument();
    expect(screen.queryByText('落到哪一场')).not.toBeInTheDocument();
    expect(screen.queryByTestId('school-land-field')).not.toBeInTheDocument();
  });

  it('can check documents from two venues', async () => {
    mockSearch.mockResolvedValue({
      items: [
        { id: 'doc-1', title: '课时计划.docx', fieldId: 'field-1' },
        { id: 'doc-2', title: '课文.docx', fieldId: 'field-2' },
      ],
    });
    mockPutEduNamedIds.mockImplementation(async (_convo: string, ids: string[]) => ({ ids }));

    render(<SchoolMaterialsBar conversationId="c1" />);
    fireEvent.click(screen.getByTestId('school-materials-toggle'));
    fireEvent.click(await screen.findByTestId('school-material-doc-1'));
    fireEvent.click(await screen.findByTestId('school-material-doc-2'));

    await waitFor(() => {
      expect(mockPutEduNamedIds).toHaveBeenCalledWith('c1', ['doc-1', 'doc-2'], '');
    });
  });
});
