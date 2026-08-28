import { latestArtifactsByFilename, primaryDeliverables } from '../picoLatestArtifacts';

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
