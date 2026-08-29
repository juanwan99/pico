import { EToolResources } from 'librechat-data-provider';
import { resolveUploadRoute } from '../files';

const file = (type: string, name: string) => new File(['x'], name, { type });

describe('resolveUploadRoute (Pico paste/drop)', () => {
  const png = file('image/png', 'shot.png');
  const pdf = file('application/pdf', 'doc.pdf');
  const xlsx = file(
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'report.xlsx',
  );
  const threeImageDestinations = [
    undefined,
    EToolResources.execute_code,
    EToolResources.context,
  ];

  it('rejects empty files or empty options', () => {
    expect(resolveUploadRoute([], [undefined])).toEqual({ kind: 'reject' });
    expect(resolveUploadRoute([png], [])).toEqual({ kind: 'reject' });
  });

  it('sends image-only pastes to the provider without asking', () => {
    expect(resolveUploadRoute([png], threeImageDestinations)).toEqual({
      kind: 'route',
      toolResource: undefined,
    });
    expect(
      resolveUploadRoute([png, file('image/jpeg', 'two.jpg')], threeImageDestinations),
    ).toEqual({ kind: 'route', toolResource: undefined });
  });

  it('routes a PDF to context instead of asking', () => {
    expect(
      resolveUploadRoute(
        [pdf],
        [
          undefined,
          EToolResources.file_search,
          EToolResources.execute_code,
          EToolResources.context,
        ],
      ),
    ).toEqual({ kind: 'route', toolResource: EToolResources.context });
  });

  it('routes mixed image + document to context instead of asking', () => {
    expect(resolveUploadRoute([png, pdf], threeImageDestinations)).toEqual({
      kind: 'route',
      toolResource: EToolResources.context,
    });
  });

  it('auto-routes a single leftover destination', () => {
    expect(resolveUploadRoute([xlsx], [EToolResources.execute_code])).toEqual({
      kind: 'route',
      toolResource: EToolResources.execute_code,
    });
  });

  it('routes images to context when the provider cannot take them', () => {
    expect(
      resolveUploadRoute([png], [EToolResources.execute_code, EToolResources.context]),
    ).toEqual({ kind: 'route', toolResource: EToolResources.context });
  });
});
