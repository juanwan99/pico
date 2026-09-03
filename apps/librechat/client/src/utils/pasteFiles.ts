/**
 * Clipboard file paste: stop the browser from inserting the filename as text.
 * Text-only paste is unchanged.
 */
export function captureClipboardFiles(
  clipboardData: DataTransfer | null | undefined,
  preventDefault: () => void,
): File[] | null {
  const files = clipboardData?.files;
  if (!files || files.length === 0) {
    return null;
  }
  preventDefault();
  return Array.from(files);
}
