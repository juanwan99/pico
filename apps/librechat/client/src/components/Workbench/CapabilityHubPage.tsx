/**
 * 专家 · 技能 · 连接器 hub — click-through to real secondary screens.
 */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Plus, Search, Plug, Sparkles, UserRound, ChevronRight } from 'lucide-react';
import { cn } from '~/utils';
import WorkbenchShell from './WorkbenchShell';

type HubTab = 'experts' | 'skills' | 'connectors';

const TABS: { id: HubTab; label: string }[] = [
  { id: 'experts', label: '专家' },
  { id: 'skills', label: '技能' },
  { id: 'connectors', label: '连接器' },
];

const DEMO_EXPERTS = [
  {
    id: 'e1',
    name: '文档助理',
    desc: '总结、改写、结构化长文',
    tags: ['办公', '写作'],
    method: '先确认目标与受众 → 大纲 → 成稿 → 可交付清单',
  },
  {
    id: 'e2',
    name: '代码搭档',
    desc: '阅读代码、解释错误、补丁建议',
    tags: ['开发'],
    method: '复现问题 → 定位 → 最小补丁 → 回归建议',
  },
  {
    id: 'e3',
    name: '研究分析',
    desc: '资料检索与对比分析',
    tags: ['研究'],
    method: '界定问题 → 要点对比 → 风险 → 行动建议',
  },
  {
    id: 'e4',
    name: '教务助手',
    desc: '校内事务说明与变更提案（须人工确认）',
    tags: ['校园'],
    method: '澄清需求 → 提案 → S7 确认 → 不写静默库',
  },
];

const DEMO_CONNECTORS = [
  { id: 'c1', name: 'MCP 通用', desc: '已配置的 MCP 服务器', status: 'ready' as const },
  { id: 'c2', name: '自定义连接器', desc: 'OpenAPI / Webhook 后置', status: 'add' as const },
  { id: 'c3', name: '邮箱', desc: '智能体邮箱 · 后置', status: 'add' as const },
  { id: 'c4', name: '知识库', desc: '文档索引连接 · 后置', status: 'add' as const },
];

const DEMO_SKILLS = [
  { id: 's1', name: '会议纪要', desc: '把录音/要点整理成纪要', prompt: '请把我提供的会议要点整理成纪要，含决议与待办。' },
  { id: 's2', name: '周报生成', desc: '结构化本周工作与下周计划', prompt: '请根据我列的事项生成周报：本周完成、风险、下周计划。' },
  { id: 's3', name: '文件产物', desc: '生成可下载 txt/md', prompt: '创建 hello.txt，内容为 hi。请用 file 代码块输出。' },
];

export default function CapabilityHubPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tabParam = params.get('tab') as HubTab | null;
  const [tab, setTab] = useState<HubTab>(
    tabParam && TABS.some((t) => t.id === tabParam) ? tabParam : 'experts',
  );
  const [q, setQ] = useState('');
  const [expertId, setExpertId] = useState<string | null>(null);

  useEffect(() => {
    if (tabParam && TABS.some((t) => t.id === tabParam)) {
      setTab(tabParam);
    }
  }, [tabParam]);

  const setTabNav = (id: HubTab) => {
    setTab(id);
    setQ('');
    setExpertId(null);
    setParams(id === 'experts' ? {} : { tab: id });
  };

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

  const skills = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) {
      return DEMO_SKILLS;
    }
    return DEMO_SKILLS.filter((x) => x.name.includes(s) || x.desc.includes(s));
  }, [q]);

  const selectedExpert = DEMO_EXPERTS.find((e) => e.id === expertId);

  const summonExpert = (name: string, desc: string) => {
    try {
      sessionStorage.setItem('pico:pendingExpert', name);
      sessionStorage.setItem('pico:pendingPrompt', `请以「${name}」专家身份协助：${desc}`);
    } catch {
      /* ignore */
    }
    navigate('/c/new');
  };

  return (
    <WorkbenchShell
      title="专家·技能·连接器"
      subtitle="能力中心"
      actions={
        tab === 'skills' ? (
          <button
            type="button"
            onClick={() => navigate('/skills/new')}
            className="inline-flex items-center gap-1 rounded-lg bg-[#1a1a1a] px-3 py-1.5 text-[12.5px] font-medium text-white"
          >
            <Plus className="h-3.5 w-3.5" />
            添加技能
          </button>
        ) : null
      }
    >
      <div className="border-b border-black/[0.05] bg-white px-4 dark:bg-surface-primary">
        <div className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTabNav(t.id)}
              className={cn(
                'rounded-t-lg px-3.5 py-2.5 text-[13px] font-medium',
                tab === t.id
                  ? 'border-b-2 border-[#1a1a1a] text-[#1a1a1a]'
                  : 'text-[#8c8c8c] hover:text-[#3d3d3d]',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="border-b border-black/[0.05] bg-white px-4 py-2">
        <div className="flex items-center gap-2 rounded-lg bg-[#f5f5f5] px-2.5 py-1.5">
          <Search className="h-3.5 w-3.5 text-[#9a9a9a]" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={
              tab === 'experts' ? '搜索专家' : tab === 'skills' ? '搜索技能' : '搜索连接器'
            }
            className="w-full bg-transparent text-[13px] outline-none"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {tab === 'experts' && !selectedExpert && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {experts.map((e) => (
              <button
                key={e.id}
                type="button"
                onClick={() => setExpertId(e.id)}
                className="rounded-2xl border border-black/[0.06] bg-white p-4 text-left shadow-sm transition hover:border-black/12"
              >
                <div className="mb-2 flex size-9 items-center justify-center rounded-xl bg-[#edf1f4]">
                  <UserRound className="h-4 w-4" />
                </div>
                <p className="text-[14px] font-medium">{e.name}</p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-[#6b6b6b]">{e.desc}</p>
                <div className="mt-3 flex items-center text-[12px] font-medium text-[#1a1a1a]">
                  查看详情
                  <ChevronRight className="h-3.5 w-3.5" />
                </div>
              </button>
            ))}
          </div>
        )}

        {tab === 'experts' && selectedExpert && (
          <div className="mx-auto max-w-lg space-y-3">
            <button
              type="button"
              className="text-[12.5px] text-[#6b6b6b] hover:underline"
              onClick={() => setExpertId(null)}
            >
              ← 返回专家列表
            </button>
            <div className="rounded-2xl border border-black/[0.06] bg-white p-5">
              <p className="text-[17px] font-semibold">{selectedExpert.name}</p>
              <p className="mt-1 text-[13px] text-[#6b6b6b]">{selectedExpert.desc}</p>
              <p className="mt-4 text-[12px] font-medium text-[#8c8c8c]">工作方法</p>
              <p className="mt-1 text-[13px] leading-relaxed text-[#3d3d3d]">{selectedExpert.method}</p>
              <div className="mt-3 flex flex-wrap gap-1">
                {selectedExpert.tags.map((tag) => (
                  <span key={tag} className="rounded-full bg-[#f2f2f2] px-2 py-0.5 text-[11px]">
                    {tag}
                  </span>
                ))}
              </div>
              <button
                type="button"
                className="mt-5 w-full rounded-xl bg-[#1a1a1a] py-2.5 text-[13px] font-medium text-white"
                onClick={() => summonExpert(selectedExpert.name, selectedExpert.desc)}
              >
                在任务中召唤
              </button>
            </div>
          </div>
        )}

        {tab === 'skills' && (
          <div className="mx-auto max-w-2xl space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[12px] text-[#8c8c8c]">推荐技能 · 点击即开任务</p>
              <button
                type="button"
                onClick={() => navigate('/skills/manage')}
                className="text-[12.5px] font-medium underline-offset-2 hover:underline"
              >
                管理全部技能 →
              </button>
            </div>
            {skills.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  try {
                    sessionStorage.setItem('pico:pendingPrompt', s.prompt);
                  } catch {
                    /* ignore */
                  }
                  navigate('/c/new');
                }}
                className="flex w-full items-start gap-3 rounded-2xl border border-black/[0.06] bg-white p-4 text-left hover:border-black/12"
              >
                <div className="flex size-10 items-center justify-center rounded-xl bg-[#edf1f4]">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-medium">{s.name}</p>
                  <p className="mt-0.5 text-[12.5px] text-[#6b6b6b]">{s.desc}</p>
                </div>
                <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-[#b0b0b0]" />
              </button>
            ))}
            <button
              type="button"
              onClick={() => navigate('/skills/new')}
              className="flex w-full items-center justify-center gap-2 rounded-2xl border border-dashed border-black/[0.12] py-4 text-[13px] text-[#6b6b6b]"
            >
              <Plus className="h-4 w-4" />
              添加自定义技能
            </button>
          </div>
        )}

        {tab === 'connectors' && (
          <div className="grid gap-3 sm:grid-cols-2">
            {connectors.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => navigate(`/capability/connectors/${c.id}`)}
                className="flex items-start gap-3 rounded-2xl border border-black/[0.06] bg-white p-4 text-left hover:border-black/12"
              >
                <div className="flex size-10 items-center justify-center rounded-xl bg-[#edf1f4]">
                  <Plug className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-[14px] font-medium">{c.name}</p>
                    {c.status === 'ready' ? (
                      <span className="size-2 rounded-full bg-emerald-500" title="已连接" />
                    ) : (
                      <span className="rounded-full bg-[#edf1f4] px-1.5 text-[10px] text-[#8c8c8c]">
                        后置
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-[12.5px] text-[#6b6b6b]">{c.desc}</p>
                </div>
                <ChevronRight className="mt-1 h-4 w-4 text-[#b0b0b0]" />
              </button>
            ))}
          </div>
        )}
      </div>
    </WorkbenchShell>
  );
}
