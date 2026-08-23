import { picoPromptUserMarker } from '../picoMembership';

describe('picoPromptUserMarker', () => {
  it('stamps school:edu when both tenant keys exist', () => {
    expect(
      picoPromptUserMarker({
        id: '6a89177627f74adf4b5487b4',
        eduId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
        eduSchoolId: '627bcf3a-a9a8-4047-afcc-3d4878e2a7af',
      }),
    ).toBe('627bcf3a-a9a8-4047-afcc-3d4878e2a7af:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee');
  });

  it('does not stamp LibreChat id (header is school:edu; mismatch 403s)', () => {
    expect(picoPromptUserMarker({ id: '6a89177627f74adf4b5487b4' })).toBe('');
  });
});
