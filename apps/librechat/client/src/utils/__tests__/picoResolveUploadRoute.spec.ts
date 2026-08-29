import { EToolResources } from 'librechat-data-provider';
import { resolveUploadRoute } from '../files';

jest.mock(
  '@librechat/client',
  () => ({
    TextPaths: () => null,
    FilePaths: () => null,
    CodePaths: () => null,
    AudioPaths: () => null,
    VideoPaths: () => null,
    SheetPaths: () => null,
  }),
  { virtual: true },
);

const file = (type: string, name: string) => new File(['x'], name, { type });

describe('resolveUploadRoute (Pico paste/drop)', () => {
  const png = file('image/png', 'shot.png');
  const pdf = file('application/pdf', 'doc.pdf');
  const xlsx = file(
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'report.xlsx',
  );
  const messageAttach = { kind: 'route' as const, toolResource: undefined };

  it('rejects empty files or empty options', () => {
    expect(resolveUploadRoute([], [undefined])).toEqual({ kind: 'reject' });
    expect(resolveUploadRoute([png], [])).toEqual({ kind: 'reject' });
  });

  it('routes images, PDFs, and mixed sets to the same message attach', () => {
    expect(
      resolveUploadRoute([png], [undefined, EToolResources.execute_code, EToolResources.context]),
    ).toEqual(messageAttach);
    expect(
      resolveUploadRoute(
        [pdf],
        [undefined, EToolResources.file_search, EToolResources.execute_code, EToolResources.context],
      ),
    ).toEqual(messageAttach);
    expect(
      resolveUploadRoute([png, pdf], [undefined, EToolResources.context]),
    ).toEqual(messageAttach);
    expect(resolveUploadRoute([xlsx], [EToolResources.execute_code])).toEqual(messageAttach);
  });
});
