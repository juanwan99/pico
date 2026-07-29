/**
 * 专家 · 技能 · 连接器 hub (clean-room IA).
 * Skills deep-link into existing LibreChat skills when possible.
 */
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, Search, Plug, Sparkles, UserRound } from 'lucide-react';
import { cn } from '~/utils';

type HubTab = 'experts' | 'skills' | 'connectors';

const TABS: { id: HubTab; label: string }[] = [
  { id: 'experts', label: '专家' },
  { id: 'skills', label: '技能' },
  { id: 'connectors', label: '连接器' },
];

const DEMO_EXPERTS = [
  { id: 'e1', name: '文档助理', desc: '总结、改写、结构化长文', tags: ['办公', '写作'] },
  { id: 'e2', name: '代码搭档', desc: '阅读代码、解释错误、补丁建议', tags: ['开发'] },
  { id: 'e3', name: '研究分析', desc: '资料检索与对比分析', tags: ['研究'] },
];

const DEMO_CONNECTORS = [
  { id: 'c1', name: 'MCP 通用', desc: '已配置的 MCP 服务器', status: 'ready' as const },
  { id: 'c2', name: '自定义连接器', desc: 'OpenAPI / Webhook 后置', status: 'add' as const },
  { id: 'c3', name: '邮箱', desc: '智能体邮箱 · 后置', status: 'add' as const },
  { id: 'c4', name: '知识库', desc: '文档索引连接 · 后置', status: 'add' as const },
];

export default function CapabilityHubPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<HubTab>('skills');
  const [q, setQ] = useState('');

  const experts = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) {
      return DEMO_EXPERTS;
    }
    return DEMO_EXPERTS.filter(
      (e) => e.name.includes(s) || e.desc.includes(s) || e.tags.some((t) => t.includes(s)),
    );
  }, [q]);

  const connectors = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) {
      return DEMO_CONNECTORS;
    }
    return DEMO_CONNECTORS.filter((c) => c.name.includes(s) || c.desc.includes(s));
  }, [q]);

  return (
    <div className="flex h-full flex-col bg-[#fafafa] dark:bg-presentation" data-testid="capability-hub">
      <header className="border-b border-black/[0.06] bg-white px-4 pt-3 dark:border-border-light dark:bg-surface-primary">
        <div className="mb-3 flex items-center justify-between">
          <h1 className="text-[15px] font-semibold text-[#1a1a1a] dark:text-text-primary">
            专家·技能·连接器
          </h1>
          {tab === 'skills' ? (
            <button
              type="button"
              onClick={() => navigate('/skills/new')}
              className="inline-flex items-center gap-1 rounded-lg bg-[#1a1a1a] px-3 py-1.5 text-[12.5px] font-medium text-white"
            >
              <Plus className="h-3.5 w-3.5" />
              添加技能
            </button>
          ) : null}
          {tab === 'connectors' ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-lg border border-black/[0.08] bg-white px-3 py-1.5 text-[12.5px] font-medium text-[#3d3d3d]"
            >
              <Plus className="h-3.5 w-3.5" />
              自定义连接器
            </button>
          ) : null}
        </div>
        <div className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setTab(t.id);
                setQ('');
              }}
              className={cn(
                'rounded-t-lg px-3.5 py-2 text-[13px] font-medium',
                tab === t.id
                  ? 'border-b-2 border-[#1a1a1a] text-[#1a1a1a] dark:border-white dark:text-text-primary'
                  : 'text-[#8c8c8c] hover:text-[#3d3d3d]',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </header>

      <div className="border-b border-black/[0.05] bg-white px-4 py-2 dark:bg-surface-primary">
        <div className="flex items-center gap-2 rounded-lg bg-[#f5f5f5] px-2.5 py-1.5 dark:bg-surface-tertiary">
          <Search className="h-3.5 w-3.5 text-[#9a9a9a]" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={
              tab === 'experts'
                ? '搜索专家职称或描述'
                : tab === 'skills'
                  ? '搜索技能'
                  : '搜索连接器'
            }
            className="w-full bg-transparent text-[13px] outline-none"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {tab === 'experts' && (
          <div>
            <p className="mb-3 text-[12px] text-[#8c8c8c]">我的专家 · 精选场景（容器壳，可调用后接 Agent）</p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {experts.map((e) => (
                <div
                  key={e.id}
                  className="rounded-2xl border border-black/[0.06] bg-white p-4 shadow-sm dark:border-border-light dark:bg-surface-secondary"
                >
                  <div className="mb-2 flex size-9 items-center justify-center rounded-xl bg-[#edf1f4]">
                    <UserRound className="h-4 w-4 text-[#3d3d3d]" />
                  </div>
                  <p className="text-[14px] font-medium">{e.name}</p>
                  <p className="mt-1 text-[12.5px] leading-relaxed text-[#6b6b6b]">{e.desc}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {e.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full bg-[#f2f2f2] px-2 py-0.5 text-[11px] text-[#6b6b6b]"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="mt-3 text-[12.5px] font-medium text-[#1a1a1a] underline-offset-2 hover:underline"
                    onClick={() => {
                      try {
                        sessionStorage.setItem('pico:pendingExpert', e.name);
                        sessionStorage.setItem(
                          'pico:pendingPrompt',
                          `请以「${e.name}」专家身份协助：${e.desc}`,
                        );
                      } catch {
                        /* ignore */
                      }
                      navigate('/c/new');
                    }}

                  >
                    在任务中召唤
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'skills' && (
          <div className="mx-auto max-w-2xl space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-[13px] text-[#6b6b6b]">我安装的 · 推荐</p>
              <Link
                to="/skills"
                className="text-[12.5px] font-medium text-[#1a1a1a] underline-offset-2 hover:underline"
                onClick={(e) => {
                  // already on hub at /capability; link to full skills manager
                  e.preventDefault();
                  navigate('/skills/manage');
                }}
              >
                管理全部技能 →
              </Link>
            </div>
            <div className="rounded-2xl border border-black/[0.06] bg-white p-5 dark:border-border-light dark:bg-surface-secondary">
              <div className="flex items-start gap-3">
                <div className="flex size-10 items-center justify-center rounded-xl bg-[#edf1f4]">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-medium">技能库</p>
                  <p className="mt-1 text-[12.5px] leading-relaxed text-[#6b6b6b]">
                    浏览、安装与编辑技能。详情含版本、预览与代码入口（LibreChat Skills）。
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => navigate('/skills/manage')}
                      className="rounded-lg bg-[#1a1a1a] px-3 py-1.5 text-[12.5px] text-white"
                    >
                      打开技能管理
                    </button>
                    <button
                      type="button"
                      onClick={() => navigate('/skills/new')}
                      className="rounded-lg border border-black/[0.08] px-3 py-1.5 text-[12.5px]"
                    >
                      添加技能
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              {['推荐', 'SkillHub', '套件'].map((label) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => navigate('/skills/manage')}
                  className="rounded-xl border border-black/[0.06] bg-white px-3 py-3 text-left text-[13px] font-medium hover:bg-[#f5f5f5] dark:border-border-light dark:bg-surface-secondary"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {tab === 'connectors' && (
          <div className="grid gap-3 sm:grid-cols-2">
            {connectors.map((c) => (
              <div
                key={c.id}
                className="flex items-start gap-3 rounded-2xl border border-black/[0.06] bg-white p-4 dark:border-border-light dark:bg-surface-secondary"
              >
                <div className="flex size-10 items-center justify-center rounded-xl bg-[#edf1f4]">
                  <Plug className="h-5 w-5 text-[#3d3d3d]" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-[14px] font-medium">{c.name}</p>
                    {c.status === 'ready' ? (
                      <span className="size-2 rounded-full bg-emerald-500" title="已连接" />
                    ) : null}
                  </div>
                  <p className="mt-1 text-[12.5px] text-[#6b6b6b]">{c.desc}</p>
                </div>
                <button
                  type="button"
                  className="shrink-0 rounded-lg border border-black/[0.08] px-2 py-1 text-[12px] text-[#3d3d3d]"
                >
                  {c.status === 'ready' ? '›' : '+'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
