/**
 * Clipboard file paste: stop the browser from inserting the filename as text.
 *
 * Chromium often leaves clipboardData.types AND .files empty until
 * preventDefault runs. Cancel first, then read files. Empty File[] means
 * a file paste with no bytes — do not restore the filename as text.
 * null means text paste; the caller inserts getData('text/plain').
 */
function clipboardLooksLikeFiles(clipboardData: DataTransfer): boolean {
  const types = Array.from(clipboardData.types || []);
  if (types.some((t) => t === 'Files' || t === 'files' || t === 'application/x-moz-file')) {
    return true;
  }
  return Array.from(clipboardData.items || []).some((item) => item.kind === 'file');
}

function filesFromClipboard(clipboardData: DataTransfer): File[] {
  const out: File[] = [];
  const seen = new Set<string>();
  const add = (file: File | null | undefined) => {
    if (!file) {
      return;
    }
    const key = `${file.name}:${file.size}:${file.type}:${file.lastModified}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    out.push(file);
  };
  for (const file of Array.from(clipboardData.files || [])) {
    add(file);
  }
  for (const item of Array.from(clipboardData.items || [])) {
    if (item.kind === 'file') {
      add(item.getAsFile());
    }
  }
  return out;
}

export function captureClipboardFiles(
  clipboardData: DataTransfer | null | undefined,
  preventDefault: () => void,
): File[] | null {
  if (!clipboardData) {
    return null;
  }
  preventDefault();
  const files = filesFromClipboard(clipboardData);
  if (files.length > 0) {
    return files;
  }
  if (clipboardLooksLikeFiles(clipboardData)) {
    return [];
  }
  return null;
}

export function clipboardPlainText(clipboardData: DataTransfer | null | undefined): string {
  if (!clipboardData) {
    return '';
  }
  return clipboardData.getData('text/plain') || clipboardData.getData('text') || '';
}
