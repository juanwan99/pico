/**
 * Chat school materials: venue folder tree. Open = see folders and documents.
 * No landing destination, no search-first, no venue dropdown.
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

const FIELD_FETCH_CAP = 24;

function asNamedIds(row: { ids?: string[] }) {
  return {
    ids: Array.isArray(row.ids) ? row.ids : [],
  };
}

function materialFieldId(row: EduSchoolMaterial) {
  return typeof row.fieldId === 'string' && row.fieldId ? row.fieldId : '';
}

async function loadDocumentsForFields(fields: EduSchoolField[]) {
  const scoped = fields.filter((field) => field.id).slice(0, FIELD_FETCH_CAP);
  if (scoped.length === 0) {
    const row = await searchEduSchoolMaterials('', '');
    return {
      items: Array.isArray(row.items) ? row.items : [],
      configured: row.configured,
    };
  }
  const chunks = await Promise.all(
    scoped.map(async (field) => {
      try {
        const row = await searchEduSchoolMaterials('', field.id);
        const items = Array.isArray(row.items) ? row.items : [];
        return {
          configured: row.configured,
          items: items.map((item) => ({
            ...item,
            fieldId: materialFieldId(item) || field.id,
          })),
        };
      } catch {
        return { configured: true, items: [] as EduSchoolMaterial[] };
      }
    }),
  );
  const configured = chunks.every((chunk) => chunk.configured !== false);
  return {
    configured,
    items: chunks.flatMap((chunk) => chunk.items),
  };
}

export default function SchoolMaterialsBar({ conversationId }: { conversationId?: string | null }) {
  const convo = conversationId && conversationId !== 'new' ? conversationId : '';
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<EduSchoolMaterial[]>([]);
  const [named, setNamed] = useState<string[]>([]);
  const [fields, setFields] = useState<EduSchoolField[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    void (async () => {
      setBusy(true);
      setError(null);
      try {
        const [namedRow, fieldsRow] = await Promise.all([
          getEduNamedIds(convo).catch(() => ({ ids: [] as string[] })),
          listEduFields().catch(() => ({ fields: [] as EduSchoolField[] })),
        ]);
        if (cancelled) {
          return;
        }
        const nextFields = Array.isArray(fieldsRow.fields) ? fieldsRow.fields : [];
        setNamed(asNamedIds(namedRow).ids);
        setFields(nextFields);
        const listed = await loadDocumentsForFields(nextFields);
        if (cancelled) {
          return;
        }
        setItems(listed.items);
        const openMap: Record<string, boolean> = {};
        for (const field of nextFields) {
          if (field.id) openMap[field.id] = true;
        }
        openMap.other = true;
        setExpanded(openMap);
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
        field: { id: 'other', name: '其他' },
        items: other,
      });
    }
    return listed;
  }, [fields, items]);

  return (
    <div className="mb-1 w-full text-left" data-testid="school-materials-bar">
      <button
        type="button"
        className="pico-type-body inline-flex items-center gap-2 py-0.5 text-[color:var(--pico-ink)]"
        data-testid="school-materials-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span>学校材料</span>
        {named.length ? (
          <span className="pico-type-aux text-[color:var(--pico-ink-2)]">{named.length}</span>
        ) : (
          <span className="pico-type-aux text-[color:var(--pico-ink-3)]">未勾选不读正文</span>
        )}
      </button>
      {open ? (
        <div className="mt-1" data-testid="school-materials-tree">
          {error ? (
            <p className="pico-type-body text-[#b42318]" role="status">
              {error}
            </p>
          ) : null}
          {busy && groups.length === 0 ? (
            <p className="pico-type-aux text-[color:var(--pico-ink-3)]">正在列出有权的场…</p>
          ) : null}
          {groups.map((group) => {
            const fieldKey = group.field.id || 'other';
            const isOpen = expanded[fieldKey] !== false;
            return (
              <section key={fieldKey} className="py-0.5" data-testid={`school-field-folder-${fieldKey}`}>
                <button
                  type="button"
                  className="pico-type-sidebar flex w-full items-center gap-1 py-0.5 text-left text-[color:var(--pico-ink)]"
                  aria-expanded={isOpen}
                  onClick={() => setExpanded((prev) => ({ ...prev, [fieldKey]: !isOpen }))}
                >
                  <span className="w-4 shrink-0 text-[color:var(--pico-ink-2)]">{isOpen ? '▾' : '▸'}</span>
                  <span>{group.field.name || group.field.id}</span>
                </button>
                {isOpen ? (
                  group.items.length === 0 ? (
                    <p className="pico-type-aux py-0.5 pl-5 text-[color:var(--pico-ink-3)]">这场没有文档</p>
                  ) : (
                    <ul className="pl-5">
                      {group.items.map((row) => {
                        const id = row.id;
                        if (!id) return null;
                        const checked = named.includes(id);
                        return (
                          <li key={id} className="flex items-start gap-2 py-0.5">
                            <input
                              type="checkbox"
                              className="mt-1.5"
                              checked={checked}
                              onChange={() => void toggle(id)}
                              data-testid={`school-material-${id}`}
                            />
                            <span
                              className={cn(
                                'pico-type-body min-w-0',
                                checked ? 'text-[color:var(--pico-ink)]' : 'text-[color:var(--pico-ink-2)]',
                              )}
                            >
                              {row.title || id}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  )
                ) : null}
              </section>
            );
          })}
          {!busy && groups.length === 0 && !error ? (
            <p className="pico-type-body text-[color:var(--pico-ink-2)]">还没有有权的场</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
