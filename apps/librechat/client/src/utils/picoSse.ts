/** Split an SSE text buffer into `data:` JSON events + the unfinished tail (#1215). */
export function splitSseEvents<T>(buf: string): { events: T[]; rest: string } {
  const events: T[] = [];
  let rest = buf;
  let cut = rest.indexOf('\n\n');
  while (cut >= 0) {
    const block = rest.slice(0, cut);
    rest = rest.slice(cut + 2);
    if (block.startsWith('data: ')) {
      try {
        events.push(JSON.parse(block.slice(6)) as T);
      } catch {
        /* skip a torn event */
      }
    }
    cut = rest.indexOf('\n\n');
  }
  return { events, rest };
}
