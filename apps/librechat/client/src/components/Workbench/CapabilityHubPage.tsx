/**
 * 技能与连接器 — one page, two tabs. Skills toggle in place; no prompt injection.
 */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useListSkillsQuery } from '~/data-provider';
import { useSkillActiveState } from '~/hooks';
import SkillToggle from '~/components/Skills/buttons/SkillToggle';
import { cn } from '~/utils';
import WorkbenchShell from './WorkbenchShell';

type HubTab = 'skills' | 'connectors';

const TABS: { id: HubTab; label: string }[] = [
  { id: 'skills', label: '技能' },
  { id: 'connectors', label: '连接器' },
];

const CONNECTORS = [
  {
    id: 'school-kb',
    name: '学校知识库',
    desc: '学校场里已挂上的材料，对话里可点名引用',
    status: 'connected' as const,
  },
  {
    id: 'mcp',
    name: 'MCP',
    desc: '通用 MCP 工具桥，当前未接通',
    status: 'disconnected' as const,
  },
];

export default function CapabilityHubPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tabParam = params.get('tab');
  const [tab, setTab] = useState<HubTab>(tabParam === 'connectors' ? 'connectors' : 'skills');
  const [q, setQ] = useState('');

  useEffect(() => {
    setTab(tabParam === 'connectors' ? 'connectors' : 'skills');
  }, [tabParam]);
  const skillQuery = useListSkillsQuery({ limit: 100 });
  const { isActive, toggle, isLoading: statesLoading } = useSkillActiveState();

  const setTabNav = (id: HubTab) => {
    setTab(id);
    setQ('');
    const next = new URLSearchParams(params);
    if (id === 'skills') {
      next.delete('tab');
    } else {
      next.set('tab', id);
    }
    setParams(next);
  };

  const skillCatalog = skillQuery.data?.skills ?? [];
  const skills = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) {
      return skillCatalog;
    }
    return skillCatalog.filter(
      (skill) =>
        skill.name.toLowerCase().includes(s) ||
        (skill.displayTitle || '').toLowerCase().includes(s) ||
        (skill.description || '').toLowerCase().includes(s),
    );
  }, [q, skillCatalog]);

  const connectors = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) {
      return CONNECTORS;
    }
    return CONNECTORS.filter((c) => c.name.includes(s) || c.desc.includes(s));
  }, [q]);

  return (
    <WorkbenchShell title="技能与连接器" subtitle="能力" backTo="/c/new">
      <div className="border-b border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] px-4 dark:bg-surface-primary">
        <div className="flex gap-1" role="tablist" aria-label="技能与连接器">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTabNav(t.id)}
              className={cn(
                'rounded-t-lg px-3.5 py-2.5 text-[13px] font-medium',
                tab === t.id
                  ? 'border-b-2 border-[color:var(--pico-ink)] text-[color:var(--pico-ink)]'
                  : 'text-[color:var(--pico-ink-3)] hover:text-[color:var(--pico-ink)]',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="border-b border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] px-4 py-2">
        <div className="flex items-center gap-2 rounded-lg bg-[color:var(--pico-surface-2)] px-2.5 py-1.5">
          <PicoIcon name="search" size="sm" className="text-[color:var(--pico-ink-3)]" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={tab === 'skills' ? '搜索技能' : '搜索连接器'}
            className="w-full bg-transparent text-[13px] outline-none"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {tab === 'skills' && (
          <div className="mx-auto max-w-2xl space-y-2">
            {skillQuery.isLoading || statesLoading ? (
              <p
                role="status"
                className="rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-4 text-[13px] text-[color:var(--pico-ink-2)]"
              >
                正在读取技能…
              </p>
            ) : skillQuery.isError ? (
              <p
                role="alert"
                className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-[13px] text-amber-900"
              >
                技能目录暂时不可用，请稍后重试。
              </p>
            ) : skills.length === 0 ? (
              <p className="rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-4 text-[13px] text-[color:var(--pico-ink-2)]">
                还没有技能。
              </p>
            ) : (
              skills.map((skill) => {
                const enabled = isActive(skill);
                const title = skill.displayTitle || skill.name;
                return (
                  <div
                    key={skill._id}
                    className="flex w-full items-center gap-3 rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] px-4 py-3"
                    data-testid={`skill-row-${skill._id}`}
                  >
                    <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-[color:var(--pico-surface-2)]">
                      <PicoIcon name="spark" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[14px] font-medium">{title}</p>
                      {skill.description ? (
                        <p className="mt-0.5 line-clamp-2 text-[12.5px] text-[color:var(--pico-ink-2)]">
                          {skill.description}
                        </p>
                      ) : null}
                    </div>
                    <SkillToggle
                      enabled={enabled}
                      onChange={() => toggle(skill)}
                      ariaLabel={`${title} ${enabled ? '已开启' : '已关闭'}`}
                    />
                  </div>
                );
              })
            )}
          </div>
        )}

        {tab === 'connectors' && (
          <div className="mx-auto max-w-2xl space-y-2">
            {connectors.map((c) => (
              <div
                key={c.id}
                className="flex items-start gap-3 rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-4"
                data-testid={`connector-row-${c.id}`}
              >
                <div className="flex size-10 items-center justify-center rounded-xl bg-[color:var(--pico-surface-2)]">
                  <PicoIcon name="plug" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-[14px] font-medium">{c.name}</p>
                    {c.status === 'connected' ? (
                      <span className="rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-800">
                        已接通
                      </span>
                    ) : (
                      <span className="rounded-full bg-[color:var(--pico-surface-2)] px-1.5 py-0.5 text-[10px] text-[color:var(--pico-ink-3)]">
                        未接
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-[12.5px] text-[color:var(--pico-ink-2)]">{c.desc}</p>
                </div>
                {c.id === 'school-kb' ? (
                  <button
                    type="button"
                    onClick={() => navigate('/more/files#school')}
                    className="shrink-0 rounded-md px-2 py-1 text-[12px] text-[color:var(--pico-ink-2)] hover:bg-[color:var(--pico-surface-2)]"
                  >
                    查看
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </WorkbenchShell>
  );
}
