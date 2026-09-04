import { captureClipboardFiles } from '../pasteFiles';

function dt(files: File[], text = '', types?: string[]): DataTransfer {
  return {
    files,
    types: types ?? (files.length ? ['Files', 'text/plain'] : ['text/plain']),
    items: files.map((file) => ({ kind: 'file', type: file.type, getAsFile: () => file })),
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

  it('cancels before reading files when types says Files (Chromium empty FileList)', () => {
    const doc = new File(['OLE'], '教师教学计划.doc', { type: 'application/msword' });
    let cancelled = false;
    const clipboard = {
      types: ['Files'],
      items: [{ kind: 'file', type: doc.type, getAsFile: () => (cancelled ? doc : null) }],
      get files() {
        return cancelled ? [doc] : [];
      },
      getData: () => '教师教学计划.doc',
    } as unknown as DataTransfer;
    const got = captureClipboardFiles(clipboard, () => {
      cancelled = true;
    });
    expect(got).toHaveLength(1);
    expect(got?.[0].name).toBe('教师教学计划.doc');
  });

  it('leaves text-only paste alone', () => {
    const preventDefault = jest.fn();
    expect(captureClipboardFiles(dt([], '计划.docx'), preventDefault)).toBeNull();
    expect(preventDefault).not.toHaveBeenCalled();
    expect(captureClipboardFiles(null, preventDefault)).toBeNull();
  });
});
