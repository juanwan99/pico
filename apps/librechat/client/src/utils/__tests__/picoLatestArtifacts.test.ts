import { latestArtifactsByFilename } from '../picoLatestArtifacts';

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
