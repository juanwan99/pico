/**
 * Chat school materials: venue folder tree. Open = see folders and documents.
 * No landing destination, no search-first, no venue dropdown.
 * Tree load = fields + one unscoped search (no N× field_id fan-out).
 * Empty venues refill lazily on expand.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getEduNamedIds,
  putEduNamedIds,
  type EduSchoolField,
  type EduSchoolMaterial,
} from '~/data-provider/pico/api';
import { PicoIcon } from '~/components/ui/pico-icons';
import {
  groupSchoolTree,
  loadSchoolFieldItems,
  loadSchoolFieldTree,
} from '~/utils/picoSchoolTree';
import { cn } from '~/utils';

function asNamedIds(row: { ids?: string[] }) {
  return {
    ids: Array.isArray(row.ids) ? row.ids : [],
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
  const [loadingField, setLoadingField] = useState<string | null>(null);
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
        const [namedRow, tree] = await Promise.all([
          getEduNamedIds(convo).catch(() => ({ ids: [] as string[] })),
          loadSchoolFieldTree(),
        ]);
        if (cancelled) {
          return;
        }
        setNamed(asNamedIds(namedRow).ids);
        setFields(tree.fields);
        setItems(tree.items);
        const openMap: Record<string, boolean> = {};
        const byField = new Set(
          tree.items
            .map((row) => (typeof row.fieldId === 'string' ? row.fieldId : ''))
            .filter(Boolean),
        );
        for (const field of tree.fields) {
          if (field.id) openMap[field.id] = byField.has(field.id);
        }
        openMap.other = tree.items.some((row) => !row.fieldId);
        setExpanded(openMap);
        if (tree.configured === false) {
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

  const toggleField = useCallback(
    async (fieldKey: string) => {
      const nextOpen = !expanded[fieldKey];
      setExpanded((prev) => ({ ...prev, [fieldKey]: nextOpen }));
      if (!nextOpen || !fieldKey || fieldKey === 'other') return;
      const hasItems = items.some((row) => row.fieldId === fieldKey);
      if (hasItems) return;
      setLoadingField(fieldKey);
      try {
        const row = await loadSchoolFieldItems(fieldKey);
        setItems((prev) => {
          const kept = prev.filter((item) => item.fieldId !== fieldKey);
          return [...kept, ...row.items];
        });
      } catch {
        /* leave empty */
      } finally {
        setLoadingField(null);
      }
    },
    [expanded, items],
  );

  const groups = useMemo(() => groupSchoolTree(fields, items), [fields, items]);

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
            const isOpen = !!expanded[fieldKey];
            return (
              <section key={fieldKey} className="py-0.5" data-testid={`school-field-folder-${fieldKey}`}>
                <button
                  type="button"
                  className="pico-type-sidebar flex w-full items-center gap-1 py-0.5 text-left text-[color:var(--pico-ink)]"
                  aria-expanded={isOpen}
                  onClick={() => void toggleField(fieldKey)}
                >
                  <span className="w-4 shrink-0 text-[color:var(--pico-ink-2)]">{isOpen ? '▾' : '▸'}</span>
                  <PicoIcon
                    name={isOpen ? 'folder-open' : 'folder'}
                    size="sm"
                    className="shrink-0 text-[color:var(--pico-ink-2)]"
                  />
                  <span>{group.field.name || group.field.id}</span>
                </button>
                {isOpen ? (
                  loadingField === fieldKey && group.items.length === 0 ? (
                    <p className="pico-type-aux py-0.5 pl-5 text-[color:var(--pico-ink-3)]">正在列出文档…</p>
                  ) : group.items.length === 0 ? (
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
                            <PicoIcon
                              name="file"
                              size="sm"
                              className="mt-0.5 shrink-0 text-[color:var(--pico-ink-2)]"
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
