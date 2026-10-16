const {
  registerPicoSteer,
  forwardPicoSteers,
  postPicoSteer,
  deliverQueuedSteers,
} = require('./picoSteer');

function fakeSteering(items) {
  const queue = [...items];
  return {
    queue,
    drain: jest.fn(async () => queue.splice(0)),
    enqueue: jest.fn(async (_id, item) => queue.push(item)),
  };
}

describe('pico steer (pico#1318)', () => {
  it('hands each steer to pico in order and applies it inline', async () => {
    const steering = fakeSteering([
      { steerId: 'a', text: '改成表格' },
      { steerId: 'b', text: '再短一点' },
    ]);
    const post = jest.fn().mockResolvedValue(true);
    const apply = jest.fn();
    await deliverQueuedSteers({ steering, streamId: 'c1', jobCreatedAt: 1, post, apply });
    expect(steering.drain).toHaveBeenCalledWith('c1', 1);
    expect(post.mock.calls.map((c) => c[0])).toEqual(['改成表格', '再短一点']);
    expect(apply.mock.calls.map((c) => c[0].steerId)).toEqual(['a', 'b']);
    expect(steering.queue).toEqual([]);
  });

  it('puts refused steers back in order for the run-end path', async () => {
    const steering = fakeSteering([
      { steerId: 'a', text: 'x' },
      { steerId: 'f', text: '看图', files: [{ file_id: 'f1' }] },
      { steerId: 'b', text: 'y' },
    ]);
    const post = jest.fn().mockResolvedValue(true);
    const apply = jest.fn();
    await deliverQueuedSteers({ steering, streamId: 'c1', post, apply });
    // Files stay with the stock path, and nothing after them jumps the line.
    expect(post).toHaveBeenCalledTimes(1);
    expect(apply.mock.calls.map((c) => c[0].steerId)).toEqual(['a']);
    expect(steering.queue.map((i) => i.steerId)).toEqual(['f', 'b']);

    const refused = fakeSteering([{ steerId: 'c', text: 'z' }]);
    await deliverQueuedSteers({
      steering: refused,
      streamId: 'c1',
      post: jest.fn().mockResolvedValue(false),
      apply,
    });
    expect(refused.queue.map((i) => i.steerId)).toEqual(['c']);
  });

  it('forwards only while a pico call is registered', async () => {
    const forward = jest.fn().mockResolvedValue(undefined);
    const unregister = registerPicoSteer('c1', forward);
    await forwardPicoSteers('c1');
    unregister();
    await forwardPicoSteers('c1');
    expect(forward).toHaveBeenCalledTimes(1);
  });

  it('posts to pico with the chat identity headers; only 202 counts', async () => {
    const req = { user: { id: 'u1', eduId: 'teacher-1', eduSchoolId: 'school-1' } };
    const fetchImpl = jest.fn().mockResolvedValue({ status: 202 });
    expect(await postPicoSteer({ req, conversationId: 'conv-1', text: '改', fetchImpl })).toBe(
      true,
    );
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://127.0.0.1:18765/v1/chat/steer');
    expect(init.headers['X-Pico-Membership-Id']).toBe('school-1:teacher-1');
    expect(init.headers['X-Conversation-Id']).toBe('conv-1');
    expect(JSON.parse(init.body)).toEqual({ text: '改' });

    fetchImpl.mockResolvedValue({ status: 409 });
    expect(await postPicoSteer({ req, conversationId: 'conv-1', text: '改', fetchImpl })).toBe(
      false,
    );
    fetchImpl.mockRejectedValue(new Error('down'));
    expect(await postPicoSteer({ req, conversationId: 'conv-1', text: '改', fetchImpl })).toBe(
      false,
    );
    expect(await postPicoSteer({ req, conversationId: 'new', text: '改', fetchImpl })).toBe(false);
  });
});
