/**
 * Workbench picker: list/search school materials the membership can see, then check
 * which ones enter this round. Unchecked bodies never go to the model.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  getEduNamedIds,
  listEduFields,
  putEduNamedIds,
  searchEduSchoolMaterials,
  type EduSchoolField,
  type EduSchoolMaterial,
} from '~/data-provider/pico/api';
import { cn } from '~/utils';

export default function SchoolMaterialsBar({ conversationId }: { conversationId?: string | null }) {
  const convo = conversationId && conversationId !== 'new' ? conversationId : '';
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [items, setItems] = useState<EduSchoolMaterial[]>([]);
  const [named, setNamed] = useState<string[]>([]);
  const [fieldId, setFieldId] = useState('');
  const [fields, setFields] = useState<EduSchoolField[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshNamed = useCallback(async () => {
    try {
      const row = await getEduNamedIds(convo);
      setNamed(Array.isArray(row.ids) ? row.ids : []);
      setFieldId(typeof row.field_id === 'string' ? row.field_id : '');
    } catch {
      setNamed([]);
      setFieldId('');
    }
  }, [convo]);

  useEffect(() => {
    if (!open) return;
    void refreshNamed();
    void listEduFields()
      .then((row) => setFields(Array.isArray(row.fields) ? row.fields : []))
      .catch(() => setFields([]));
  }, [open, refreshNamed]);

  const search = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const row = await searchEduSchoolMaterials(q.trim());
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

  const toggle = useCallback(
    async (id: string) => {
      const next = named.includes(id) ? named.filter((x) => x !== id) : [...named, id].slice(0, 12);
      setNamed(next);
      try {
        const row = await putEduNamedIds(convo, next, fieldId);
        setNamed(Array.isArray(row.ids) ? row.ids : next);
        if (typeof row.field_id === 'string') setFieldId(row.field_id);
      } catch {
        setError('勾选没写上');
      }
    },
    [convo, named, fieldId],
  );

  const pickField = useCallback(
    async (nextField: string) => {
      setFieldId(nextField);
      try {
        const row = await putEduNamedIds(convo, named, nextField);
        if (typeof row.field_id === 'string') setFieldId(row.field_id);
      } catch {
        setError('落点场没写上');
      }
    },
    [convo, named],
  );

  return (
    <div className="mb-2 w-full" data-testid="school-materials-bar">
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[12px] text-[#555] hover:bg-black/[0.04]"
        data-testid="school-materials-toggle"
        aria-expanded={open}
        onClick={() => {
          setOpen((v) => {
            const next = !v;
            if (next) void search();
            return next;
          });
        }}
      >
        学校材料
        {named.length ? (
          <span className="rounded-full bg-[#3b6fd9] px-1.5 text-[10px] font-semibold text-white">
            {named.length}
          </span>
        ) : (
          <span className="text-[#999]">未勾选不读正文</span>
        )}
      </button>
      {open ? (
        <div className="mt-1 rounded-lg border border-black/[0.08] bg-white p-2 text-[12px]">
          <label className="mb-1 block text-[11px] text-[#666]">
            落到哪一场
            <select
              className="mt-0.5 h-8 w-full rounded-md border border-black/[0.08] px-2 outline-none"
              value={fieldId}
              data-testid="school-land-field"
              onChange={(e) => void pickField(e.target.value)}
            >
              <option value="">请点名一场（没点名学校看不见）</option>
              {fields.map((field) =>
                field.id ? (
                  <option key={field.id} value={field.id}>
                    {field.name || field.id}
                  </option>
                ) : null,
              )}
            </select>
          </label>
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
          <ul className="mt-1 max-h-40 overflow-y-auto">
            {items.map((row) => {
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
          {!busy && items.length === 0 ? (
            <p className="mt-1 text-[#999]">没有列出材料。搜一下，或确认学校侧有权。</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
