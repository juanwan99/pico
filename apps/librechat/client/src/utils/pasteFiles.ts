/**
 * Clipboard file paste: stop the browser from inserting the filename as text.
 * Text-only paste is unchanged.
 *
 * Chromium often reports clipboardData.files as empty until preventDefault
 * runs. Detect Files via types/items first, cancel, then read files.
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
  const looksLikeFiles = clipboardLooksLikeFiles(clipboardData);
  if (looksLikeFiles) {
    preventDefault();
  }
  const files = filesFromClipboard(clipboardData);
  if (files.length === 0) {
    return null;
  }
  if (!looksLikeFiles) {
    preventDefault();
  }
  return files;
}
