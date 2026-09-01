import { splitSchoolFields, splitSchoolGroups } from '~/utils/picoSchoolTree';

jest.mock('~/data-provider/pico/api', () => ({
  listEduFields: jest.fn(),
  searchEduSchoolMaterials: jest.fn(),
}));

describe('splitSchoolFields', () => {
  it('puts manage fields left and followed fields right', () => {
    const split = splitSchoolFields([
      { id: 'mine-1', name: '生物教研组' },
      { id: 'follow-1', name: '校长', followed: true },
      { id: 'mine-2', name: '高三年级组', followed: false },
    ]);
    expect(split.mine.map((row) => row.id)).toEqual(['mine-1', 'mine-2']);
    expect(split.followed.map((row) => row.id)).toEqual(['follow-1']);
  });

  it('keeps missing followed on the left and de-dupes', () => {
    const split = splitSchoolFields([
      { id: 'a', name: '书记' },
      { id: 'a', name: '书记', followed: true },
      { id: 'b', name: '后勤', followed: true },
    ]);
    expect(split.mine.map((row) => row.id)).toEqual(['a']);
    expect(split.followed.map((row) => row.id)).toEqual(['b']);
  });
});

describe('splitSchoolGroups', () => {
  it('does not leak followed documents into 其他 on the left', () => {
    const { mine, followed } = splitSchoolGroups(
      [
        { id: 'mine-1', name: '生物教研组' },
        { id: 'follow-1', name: '校长', followed: true },
      ],
      [
        { id: 'doc-mine', title: '课时.docx', fieldId: 'mine-1' },
        { id: 'doc-follow', title: '通知.docx', fieldId: 'follow-1' },
        { id: 'doc-loose', title: '散页.docx' },
      ],
    );
    expect(mine.map((row) => row.field.id)).toEqual(['mine-1', 'other']);
    expect(mine.find((row) => row.field.id === 'mine-1')?.items.map((item) => item.id)).toEqual([
      'doc-mine',
    ]);
    expect(mine.find((row) => row.field.id === 'other')?.items.map((item) => item.id)).toEqual([
      'doc-loose',
    ]);
    expect(followed.map((row) => row.field.id)).toEqual(['follow-1']);
    expect(followed[0].items.map((item) => item.id)).toEqual(['doc-follow']);
  });
});
