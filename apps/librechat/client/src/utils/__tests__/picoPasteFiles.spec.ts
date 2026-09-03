import { captureClipboardFiles } from '../pasteFiles';

function dt(files: File[], text = ''): DataTransfer {
  return {
    files,
    getData: (type: string) => (type === 'text/plain' ? text : ''),
  } as unknown as DataTransfer;
}

describe('captureClipboardFiles', () => {
  it('prevents default and returns files when the clipboard has files', () => {
    const preventDefault = jest.fn();
    const doc = new File(['PK'], '计划.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });
    const got = captureClipboardFiles(dt([doc], '计划.docx'), preventDefault);
    expect(preventDefault).toHaveBeenCalledTimes(1);
    expect(got).toHaveLength(1);
    expect(got?.[0].name).toBe('计划.docx');
  });

  it('leaves text-only paste alone', () => {
    const preventDefault = jest.fn();
    expect(captureClipboardFiles(dt([], '计划.docx'), preventDefault)).toBeNull();
    expect(preventDefault).not.toHaveBeenCalled();
    expect(captureClipboardFiles(null, preventDefault)).toBeNull();
  });
});
