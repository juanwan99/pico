const createSpaFallback = require('./fallback');

describe('createSpaFallback', () => {
  const sendIndexHtml = jest.fn((_req, res) => res.status(200).send('<div id="root"></div>'));
  const build = () => createSpaFallback(sendIndexHtml);
  const call = (path) => {
    const res = { status: jest.fn().mockReturnThis(), end: jest.fn(), send: jest.fn() };
    build()({ path }, res);
    return res;
  };

  it('serves index.html for app routes', () => {
    const res = call('/c/new');
    expect(res.status).not.toHaveBeenCalledWith(404);
    expect(sendIndexHtml).toHaveBeenCalled();
  });

  it('404s missing static assets instead of the SPA shell', () => {
    for (const path of ['/assets/app.js', '/fonts/a.woff2', '/img/x.png']) {
      const res = call(path);
      expect(res.status).toHaveBeenCalledWith(404);
    }
  });

  it('404s document/binary paths so stale attachment URLs never get index.html', () => {
    for (const path of [
      '/uploads/user1/abc__通知.pdf',
      '/uploads/user1/abc__file.docx',
      '/uploads/user1/abc__deck.pptx',
      '/uploads/user1/abc__sheet.xlsx',
      '/files/old.zip',
    ]) {
      const res = call(path);
      expect(res.status).toHaveBeenCalledWith(404);
      expect(sendIndexHtml).not.toHaveBeenCalled();
    }
  });
});
