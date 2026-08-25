/**
 * Workbench picker: school materials as venue folders. Check documents across
 * venues. Unchecked bodies never go to the model. No landing destination here.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getEduNamedIds,
  listEduFields,
  putEduNamedIds,
  searchEduSchoolMaterials,
  type EduSchoolField,
  type EduSchoolMaterial,
} from '~/data-provider/pico/api';
import { cn } from '~/utils';

function asNamedIds(row: { ids?: string[] }) {
  return {
    ids: Array.isArray(row.ids) ? row.ids : [],
  };
}

function materialFieldId(row: EduSchoolMaterial) {
  return typeof row.fieldId === 'string' ? row.fieldId : '';
}

export default function SchoolMaterialsBar({ conversationId }: { conversationId?: string | null }) {
  const convo = conversationId && conversationId !== 'new' ? conversationId : '';
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [items, setItems] = useState<EduSchoolMaterial[]>([]);
  const [named, setNamed] = useState<string[]>([]);
  const [fields, setFields] = useState<EduSchoolField[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async (nextQ = q) => {
    setBusy(true);
    setError(null);
    try {
      const row = await searchEduSchoolMaterials(nextQ.trim(), '');
      setItems(Array.isArray(row.items) ? row.items : []);
      if (row.configured === false) {
        setError('学校材料口还没接通');
      }
    } catch (err) {
      const status = err instanceof Error ? err.message : String(err);
      if (/\b403\b/.test(status)) {
        setError('无权看这份材料');
      } else {
        setError('学校材料现在列不出');
      }
      setItems([]);
    } finally {
      setBusy(false);
    }
  }, [q]);

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    void (async () => {
      setBusy(true);
      setError(null);
      try {
        const [namedRow, fieldsRow, listed] = await Promise.all([
          getEduNamedIds(convo).catch(() => ({ ids: [] as string[] })),
          listEduFields().catch(() => ({ fields: [] as EduSchoolField[] })),
          searchEduSchoolMaterials(q.trim(), ''),
        ]);
        if (cancelled) {
          return;
        }
        setNamed(asNamedIds(namedRow).ids);
        setFields(Array.isArray(fieldsRow.fields) ? fieldsRow.fields : []);
        setItems(Array.isArray(listed.items) ? listed.items : []);
        if (listed.configured === false) {
          setError('学校材料口还没接通');
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        const status = err instanceof Error ? err.message : String(err);
        setError(/\b403\b/.test(status) ? '无权看这份材料' : '学校材料现在列不出');
        setItems([]);
      } finally {
        if (!cancelled) {
          setBusy(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // Open-load uses the query at the moment the panel opens; typing then 搜.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, convo]);

  const toggle = useCallback(
    async (id: string) => {
      const next = named.includes(id) ? named.filter((x) => x !== id) : [...named, id].slice(0, 12);
      setNamed(next);
      try {
        const row = await putEduNamedIds(convo, next, '');
        setNamed(Array.isArray(row.ids) ? row.ids : next);
      } catch {
        setError('勾选没写上');
      }
    },
    [convo, named],
  );

  const groups = useMemo(() => {
    const byField = new Map<string, { field: EduSchoolField; items: EduSchoolMaterial[] }>();
    for (const field of fields) {
      if (!field.id) continue;
      byField.set(field.id, { field, items: [] });
    }
    const other: EduSchoolMaterial[] = [];
    for (const item of items) {
      if (!item.id) continue;
      const fid = materialFieldId(item);
      const bucket = fid ? byField.get(fid) : undefined;
      if (bucket) {
        bucket.items.push(item);
      } else {
        other.push(item);
      }
    }
    const listed = [...byField.values()];
    if (other.length) {
      listed.push({
        field: { id: '', name: '其他' },
        items: other,
      });
    }
    if (q.trim()) {
      return listed.filter((group) => group.items.length > 0);
    }
    return listed;
  }, [fields, items, q]);

  return (
    <div className="mb-2 w-full" data-testid="school-materials-bar">
      <button
        type="button"
        className="pico-type-sidebar inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[color:var(--pico-ink-2)] hover:bg-black/[0.04]"
        data-testid="school-materials-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        学校材料
        {named.length ? (
          <span className="pico-type-aux rounded-full bg-[#3b6fd9] px-1.5 font-semibold text-white">
            {named.length}
          </span>
        ) : (
          <span className="pico-type-aux text-[color:var(--pico-ink-3)]">未勾选不读正文</span>
        )}
      </button>
      {open ? (
        <div className="pico-type-body mt-1 rounded-lg border border-black/[0.08] bg-white p-2">
          <div className="flex gap-1">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void search();
                }
              }}
              placeholder="搜索有权看见的材料"
              className="h-8 min-w-0 flex-1 rounded-md border border-black/[0.08] px-2 outline-none"
              data-testid="school-materials-q"
            />
            <button
              type="button"
              className="h-8 rounded-md border border-black/[0.08] px-2"
              onClick={() => void search()}
              disabled={busy}
            >
              {busy ? '…' : '搜'}
            </button>
          </div>
          {error ? (
            <p className="mt-1 text-[#b42318]" role="status">
              {error}
            </p>
          ) : null}
          <div className="mt-1 max-h-56 overflow-y-auto" data-testid="school-materials-tree">
            {groups.map((group) => {
              const fieldKey = group.field.id || 'other';
              return (
                <section
                  key={fieldKey}
                  className="mb-1.5"
                  data-testid={`school-field-folder-${fieldKey}`}
                >
                  <p className="pico-type-aux px-0.5 py-0.5 font-medium text-[color:var(--pico-ink-2)]">
                    {group.field.name || group.field.id || '其他'}
                  </p>
                  {group.items.length === 0 ? (
                    <p className="pico-type-aux px-0.5 text-[color:var(--pico-ink-3)]">
                      这场还没有列出文档
                    </p>
                  ) : (
                    <ul>
                      {group.items.map((row) => {
                        const id = row.id;
                        if (!id) return null;
                        const checked = named.includes(id);
                        return (
                          <li key={id} className="flex items-start gap-2 py-1">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => void toggle(id)}
                              data-testid={`school-material-${id}`}
                            />
                            <span className={cn('min-w-0', checked ? 'text-[#111]' : 'text-[#555]')}>
                              {row.title || id}
                              {row.unread ? <span className="ml-1 text-[#999]">未读懂</span> : null}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
          {!busy && groups.length === 0 ? (
            <p className="pico-type-aux mt-1 text-[color:var(--pico-ink-3)]">
              还没有列出学校材料。搜一下，或确认学校侧有权。
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
