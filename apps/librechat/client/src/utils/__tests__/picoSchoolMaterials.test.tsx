/**
 * T-NAV-LAYOUT: chat school-materials picker must list documents for the
 * named field, not only the venue dropdown.
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

describe('SchoolMaterialsBar field + document checkboxes', () => {
  beforeEach(() => {
    mockGetEduNamedIds.mockResolvedValue({ ids: [], field_id: '' });
    mockListEduFields.mockResolvedValue({
      fields: [{ id: 'field-1', name: '本学期排课' }],
    });
    mockPutEduNamedIds.mockResolvedValue({ ids: [], field_id: 'field-1' });
    mockSearch.mockResolvedValue({ items: [] });
  });

  it('loads documents for the named field when opened', async () => {
    mockGetEduNamedIds.mockResolvedValue({ ids: [], field_id: 'field-1' });
    mockSearch.mockResolvedValue({
      items: [{ id: 'doc-1', title: '课时计划.docx' }],
    });

    render(<SchoolMaterialsBar conversationId="c1" />);
    fireEvent.click(screen.getByTestId('school-materials-toggle'));

    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith('', 'field-1');
    });
    expect(await screen.findByTestId('school-material-doc-1')).toBeInTheDocument();
    expect(screen.getByText('课时计划.docx')).toBeInTheDocument();
  });

  it('re-lists that field\'s documents after picking a venue', async () => {
    mockSearch
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ items: [{ id: 'doc-2', title: '教案.md' }] });

    render(<SchoolMaterialsBar conversationId="c1" />);
    fireEvent.click(screen.getByTestId('school-materials-toggle'));
    await waitFor(() => expect(mockListEduFields).toHaveBeenCalled());

    fireEvent.change(screen.getByTestId('school-land-field'), { target: { value: 'field-1' } });

    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith('', 'field-1');
    });
    expect(await screen.findByTestId('school-material-doc-2')).toBeInTheDocument();
    expect(mockPutEduNamedIds).toHaveBeenCalledWith('c1', [], 'field-1');
  });
});
