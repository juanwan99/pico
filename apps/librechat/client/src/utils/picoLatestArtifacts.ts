/** Newest-first list: keep the first chip per filename. Observe loops must not stack identical names. */
export function latestArtifactsByFilename<
  T extends { id: string; title?: string; user_label?: string },
>(items: T[] | null | undefined): T[] {
  if (!items?.length) {
    return [];
  }
  const seen = new Set<string>();
  const out: T[] = [];
  for (const item of items) {
    const name = (item.user_label || item.title || '').trim().toLowerCase();
    const key = name || item.id;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    out.push(item);
  }
  return out;
}
