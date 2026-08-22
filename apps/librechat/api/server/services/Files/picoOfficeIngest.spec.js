const { conversationHeader, INGEST_EXT } = require('./picoOfficeIngest');

describe('pico composer ingest (T-AGENT-PLAIN-V1 F2)', () => {
  it('accepts markdown and text plus office', () => {
    expect(INGEST_EXT.has('.md')).toBe(true);
    expect(INGEST_EXT.has('.txt')).toBe(true);
    expect(INGEST_EXT.has('.docx')).toBe(true);
    expect(INGEST_EXT.has('.pptx')).toBe(true);
    expect(INGEST_EXT.has('.png')).toBe(false);
  });

  it('does not stamp reserved conversation ids', () => {
    expect(conversationHeader('new')).toBe('');
    expect(conversationHeader('search')).toBe('');
    expect(conversationHeader('')).toBe('');
    expect(conversationHeader('pending_abc-1')).toBe('pending_abc-1');
    expect(conversationHeader('f2bd2503-a59e-4428-a18e-6d9520b2ae51')).toBe(
      'f2bd2503-a59e-4428-a18e-6d9520b2ae51',
    );
  });
});
