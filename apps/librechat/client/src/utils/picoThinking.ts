import { ContentTypes } from 'librechat-data-provider';
import type { TMessageContentParts } from 'librechat-data-provider';

function thinkValue(part: TMessageContentParts): string {
  if (part.type !== ContentTypes.THINK) {
    return '';
  }
  const raw = typeof part.think === 'string' ? part.think : part.think?.value;
  return typeof raw === 'string' ? raw : '';
}

/** Join THINK parts. Strip wrapping <think> tags. Empty if none. */
export function collectThinkText(
  content?: Array<TMessageContentParts | undefined> | null,
): string {
  if (!content?.length) {
    return '';
  }
  const joined = content
    .map((part) => (part ? thinkValue(part) : ''))
    .join('')
    .replace(/^<think>\s*/, '')
    .replace(/\s*<\/think>$/, '')
    .trim();
  return joined;
}
