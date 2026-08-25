/**
 * Personal folder hierarchy helpers (Windows Explorer tree).
 */
import type { PicoPersonalFolder } from '~/data-provider/pico/api';

export function folderParentId(folder: PicoPersonalFolder | undefined): string {
  return folder?.parent_id || '';
}

export function childrenOf(
  folders: PicoPersonalFolder[],
  parentId: string,
): PicoPersonalFolder[] {
  return folders.filter((row) => folderParentId(row) === parentId);
}

export function folderPath(
  folders: PicoPersonalFolder[],
  folderId: string,
): PicoPersonalFolder[] {
  if (!folderId) return [];
  const byId = new Map(folders.map((row) => [row.id, row]));
  const chain: PicoPersonalFolder[] = [];
  let cursor: string | undefined = folderId;
  const guard = new Set<string>();
  while (cursor) {
    if (guard.has(cursor)) break;
    guard.add(cursor);
    const row = byId.get(cursor);
    if (!row) break;
    chain.unshift(row);
    cursor = folderParentId(row) || undefined;
  }
  return chain;
}

export function folderLabelPath(
  folders: PicoPersonalFolder[],
  folderId: string,
): string {
  const chain = folderPath(folders, folderId);
  if (chain.length === 0) return '我的文件';
  return chain.map((row) => row.name || '新建文件夹').join(' / ');
}
