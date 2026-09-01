/**
 * Chat school materials: venue folder tree. Open = see folders; documents lazy on expand.
 * Left = I manage; right = I follow (collapsed). No landing destination.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  getEduNamedIds,
  putEduNamedIds,
  type EduSchoolField,
  type EduSchoolMaterial,
} from '~/data-provider/pico/api';
import { PicoIcon } from '~/components/ui/pico-icons';
import {
  loadSchoolFieldItems,
  loadSchoolFields,
  splitSchoolGroups,
  type SchoolFieldGroup,
} from '~/utils/picoSchoolTree';
import { cn } from '~/utils';
import ComposerChromeRow from '~/components/Chat/ComposerChromeRow';

function asNamedIds(row: { ids?: string[] }) {
  return {
    ids: Array.isArray(row.ids) ? row.ids : [],
  };
}

function FieldFolderList({
  groups,
  expanded,
  loadingFields,
  loadedFields,
  named,
  testPrefix,
  onToggleField,
  onToggleItem,
}: {
  groups: SchoolFieldGroup[];
  expanded: Record<string, boolean>;
  loadingFields: Record<string, boolean>;
  loadedFields: Record<string, boolean>;
  named: string[];
  testPrefix: string;
  onToggleField: (fieldKey: string) => void;
  onToggleItem: (id: string) => void;
}) {
  return (
    <>
      {groups.map((group) => {
        const fieldKey = group.field.id || 'other';
        const isOpen = !!expanded[fieldKey];
        const isLoading = !!loadingFields[fieldKey];
        const hasLoaded = !!loadedFields[fieldKey] || fieldKey === 'other';
        return (
          <section key={fieldKey} className="py-0.5" data-testid={`${testPrefix}-folder-${fieldKey}`}>
            <button
              type="button"
              className="pico-type-sidebar flex w-full items-center gap-1 py-0.5 text-left text-[color:var(--pico-ink)]"
              aria-expanded={isOpen}
              data-testid={`${testPrefix}-toggle-${fieldKey}`}
              onClick={() => onToggleField(fieldKey)}
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
              isLoading || !hasLoaded ? (
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
                          onChange={() => onToggleItem(id)}
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
    </>
  );
}

export default function SchoolMaterialsBar({ conversationId }: { conversationId?: string | null }) {
  const convo = conversationId && conversationId !== 'new' ? conversationId : '';
  const [open, setOpen] = useState(false);
  const [itemsByField, setItemsByField] = useState<Record<string, EduSchoolMaterial[]>>({});
  const [loadedFields, setLoadedFields] = useState<Record<string, boolean>>({});
  const [loadingFields, setLoadingFields] = useState<Record<string, boolean>>({});
  const [named, setNamed] = useState<string[]>([]);
  const [fields, setFields] = useState<EduSchoolField[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [followOpen, setFollowOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inflight = useRef<Record<string, Promise<void>>>({});
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (rootRef.current && target && !rootRef.current.contains(target)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

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
          loadSchoolFields(),
        ]);
        if (cancelled) {
          return;
        }
        setNamed(asNamedIds(namedRow).ids);
        setFields(fieldsRow.fields);
        setItemsByField({});
        setLoadedFields({});
        setExpanded({});
        setFollowOpen(false);
        if (fieldsRow.configured === false) {
          setError('学校材料口还没接通');
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        const status = err instanceof Error ? err.message : String(err);
        setError(/\b403\b/.test(status) ? '无权看这份材料' : '学校材料现在列不出');
        setFields([]);
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

  const ensureFieldLoaded = useCallback(async (fieldId: string) => {
    if (!fieldId || fieldId === 'other') return;
    if (loadedFields[fieldId]) return;
    if (inflight.current[fieldId]) {
      await inflight.current[fieldId];
      return;
    }
    setLoadingFields((prev) => ({ ...prev, [fieldId]: true }));
    const task = (async () => {
      try {
        const row = await loadSchoolFieldItems(fieldId);
        setItemsByField((prev) => ({ ...prev, [fieldId]: row.items }));
        setLoadedFields((prev) => ({ ...prev, [fieldId]: true }));
        if (row.configured === false) {
          setError('学校材料口还没接通');
        }
      } catch {
        setItemsByField((prev) => ({ ...prev, [fieldId]: [] }));
        setLoadedFields((prev) => ({ ...prev, [fieldId]: true }));
      } finally {
        setLoadingFields((prev) => ({ ...prev, [fieldId]: false }));
        delete inflight.current[fieldId];
      }
    })();
    inflight.current[fieldId] = task;
    await task;
  }, [loadedFields]);

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
    (fieldKey: string) => {
      setExpanded((prev) => {
        const nextOpen = !prev[fieldKey];
        if (nextOpen) {
          void ensureFieldLoaded(fieldKey);
        }
        return { ...prev, [fieldKey]: nextOpen };
      });
    },
    [ensureFieldLoaded],
  );

  const items = useMemo(() => Object.values(itemsByField).flat(), [itemsByField]);
  const { mine: mineGroups, followed: followGroups } = useMemo(
    () => splitSchoolGroups(fields, items),
    [fields, items],
  );
  const folderProps = {
    expanded,
    loadingFields,
    loadedFields,
    named,
    onToggleField: toggleField,
    onToggleItem: (id: string) => void toggle(id),
  };

  return (
    <div ref={rootRef} className="w-full text-left" data-testid="school-materials-bar">
      <ComposerChromeRow label="学校材料">
        <button
          type="button"
          className="pico-type-body pico-chrome-control"
          data-testid="school-materials-toggle"
          aria-expanded={open}
          aria-haspopup="true"
          onClick={() => setOpen((v) => !v)}
        >
          {named.length ? (
            <span className="pico-type-aux min-w-0 truncate text-[color:var(--pico-ink-2)]">
              {named.length}
            </span>
          ) : (
            <span className="pico-type-aux min-w-0 truncate text-[color:var(--pico-ink-3)]">
              未勾选不读正文
            </span>
          )}
          <span aria-hidden className="pico-type-aux pico-chrome-caret">
            ▾
          </span>
        </button>
      </ComposerChromeRow>
      {open ? (
        <div className="mt-1" data-testid="school-materials-tree">
          {error ? (
            <p className="pico-type-body text-[#b42318]" role="status">
              {error}
            </p>
          ) : null}
          {busy && mineGroups.length === 0 && followGroups.length === 0 ? (
            <p className="pico-type-aux text-[color:var(--pico-ink-3)]">正在列出有权的场…</p>
          ) : null}
          <div className="grid grid-cols-2 gap-3">
            <div data-testid="school-materials-mine">
              <p className="pico-type-aux py-0.5 text-[color:var(--pico-ink-2)]">我负责的</p>
              <FieldFolderList groups={mineGroups} testPrefix="school-field" {...folderProps} />
              {!busy && mineGroups.length === 0 && !error ? (
                <p className="pico-type-body text-[color:var(--pico-ink-2)]">还没有负责的场</p>
              ) : null}
            </div>
            <div data-testid="school-materials-followed">
              <button
                type="button"
                className="pico-type-aux flex w-full items-center gap-1 py-0.5 text-left text-[color:var(--pico-ink-2)]"
                aria-expanded={followOpen}
                data-testid="school-followed-toggle"
                onClick={() => setFollowOpen((v) => !v)}
              >
                <span className="w-4 shrink-0">{followOpen ? '▾' : '▸'}</span>
                <span>订阅</span>
              </button>
              {followOpen ? (
                <>
                  <FieldFolderList groups={followGroups} testPrefix="school-follow" {...folderProps} />
                  {followGroups.length === 0 && !error ? (
                    <p className="pico-type-body text-[color:var(--pico-ink-2)]">还没有订阅的场</p>
                  ) : null}
                </>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
