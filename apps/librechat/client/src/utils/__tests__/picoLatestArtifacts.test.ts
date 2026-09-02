import {
  artifactsForRun,
  latestArtifactsByFilename,
  primaryDeliverables,
} from '../picoLatestArtifacts';

describe('artifactsForRun', () => {
  it('keeps only files from the given run', () => {
    const out = artifactsForRun(
      [
        { id: 'a', run_id: 'run-1' },
        { id: 'b', run_id: 'run-2' },
        { id: 'c', run_id: 'run-1' },
      ],
      'run-1',
    );
    expect(out.map((item) => item.id)).toEqual(['a', 'c']);
  });

  it('returns the full list when no run id is given', () => {
    const items = [{ id: 'a', run_id: 'run-1' }];
    expect(artifactsForRun(items, null).map((item) => item.id)).toEqual(['a']);
  });

  it('keeps unlabeled files when the ledger has no run_id yet', () => {
    const out = artifactsForRun([{ id: 'a' }, { id: 'b' }], 'run-1');
    expect(out.map((item) => item.id)).toEqual(['a', 'b']);
  });

  it('hides other-run files when the latest run produced none', () => {
    const out = artifactsForRun([{ id: 'old', run_id: 'run-old' }], 'run-new');
    expect(out).toEqual([]);
  });
});

describe('latestArtifactsByFilename', () => {
  it('keeps the newest chip when the same filename repeats', () => {
    const out = latestArtifactsByFilename([
      { id: 'new', title: 'Live Observe.pptx', user_label: 'Live Observe.pptx' },
      { id: 'old', title: 'Live Observe.pptx', user_label: 'Live Observe.pptx' },
      { id: 'other', title: 'notes.docx', user_label: 'notes.docx' },
    ]);
    expect(out.map((item) => item.id)).toEqual(['new', 'other']);
  });
});

describe('primaryDeliverables', () => {
  it('hides sidecar images when an office file is present', () => {
    const out = primaryDeliverables([
      { id: 'deck', title: '办公尺752.pptx', kind: 'pptx' },
      { id: 'cover', title: '决策会封面图.jpg', kind: 'jpg' },
      { id: 'diagram', title: '传导图.png', kind: 'png' },
    ]);
    expect(out.map((item) => item.id)).toEqual(['deck']);
  });

  it('keeps images when they are the only deliverable', () => {
    const out = primaryDeliverables([{ id: 'cover', title: '示意图.jpg', kind: 'jpg' }]);
    expect(out.map((item) => item.id)).toEqual(['cover']);
  });
});
