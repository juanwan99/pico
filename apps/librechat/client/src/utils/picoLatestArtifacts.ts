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

const OFFICE_EXT = /\.(pptx|docx|xlsx)$/i;
const IMAGE_EXT = /\.(png|jpe?g|gif|webp)$/i;
const OFFICE_KIND = /^(pptx|docx|xlsx)$/i;
const IMAGE_KIND = /^(png|jpe?g|gif|webp|image)$/i;

type NamedArtifact = {
  id: string;
  title?: string;
  user_label?: string;
  kind?: string;
};

function displayName(item: NamedArtifact): string {
  return (item.user_label || item.title || '').trim();
}

export function isOfficeDeliverable(item: NamedArtifact): boolean {
  const name = displayName(item);
  const kind = (item.kind || '').trim();
  return OFFICE_EXT.test(name) || OFFICE_KIND.test(kind);
}

export function isImageSidecar(item: NamedArtifact): boolean {
  const name = displayName(item);
  const kind = (item.kind || '').trim();
  return IMAGE_EXT.test(name) || IMAGE_KIND.test(kind);
}

/** Finished office file is the deliverable. Embedded cover/diagram images stay inside it. */
export function primaryDeliverables<T extends NamedArtifact>(
  items: T[] | null | undefined,
): T[] {
  const latest = latestArtifactsByFilename(items);
  if (!latest.some(isOfficeDeliverable)) {
    return latest;
  }
  return latest.filter((item) => !isImageSidecar(item));
}
