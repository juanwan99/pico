/**
 * 专家 · 技能 · 连接器 hub — click-through to real secondary screens.
 */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Plus, Search, Plug, Sparkles, UserRound, ChevronRight } from 'lucide-react';
import { cn } from '~/utils';
import WorkbenchShell from './WorkbenchShell';
import {
  preferredModelForExpert,
  preferredModelForSkill,
  setActiveExpert,
  setPicoModelMode,
} from '~/utils/picoModelPref';

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
  { id: 'c5', name: '腾讯文档', desc: '文档授权连接 · 后置', status: 'add' as const },
];

const DEMO_SKILLS = [
  {
    id: 'skill-chat',
    name: 'skill.chat',
    desc: '少工具或无工具的普通问答',
    prompt: '请直接回答我的问题，不要臆造学校数据。',
    tools: '无工具',
    risk: 'low',
  },
  {
    id: 'skill-read',
    name: 'skill.read',
    desc: '只读工具子集，适合查询演示班级数据',
    prompt: '请读取可用的班级信息并用一句话概括。',
    tools: 'fake_edu_list_classes',
    risk: 'read',
  },
  {
    id: 'skill-write-s7',
    name: 'skill.write_s7',
    desc: '业务变更提案进入现有 S7 人工确认',
    prompt: '请提出一个把一班名称改为星辰一班的变更申请。',
    tools: 'pico_propose_change',
    risk: 'write_s7',
  },
  {
    id: 'skill-summarize',
    name: 'skill.summarize',
    desc: 'Pico 快路径预设：提炼要点、结论与待办',
    prompt: '请总结以下内容，列出要点、结论与待办；不要补充原文没有的事实：',
    tools: '无工具',
    risk: 'low',
  },
  {
    id: 'skill-lesson-outline',
    name: 'skill.lesson_outline',
    desc: 'Pico 快路径预设：生成目标明确的课程大纲',
    prompt: '请按教学目标、重点难点、课堂活动和检查点起草课程大纲。',
    tools: '无工具',
    risk: 'low',
  },
  {
    id: 'skill-quiz-draft',
    name: 'skill.quiz_draft',
    desc: 'Pico 快路径预设：基于材料生成测验草稿',
    prompt: '请根据我提供的材料起草测验题、答案和简短解析，并标明这是待复核草稿。',
    tools: '无工具',
    risk: 'low',
  },
  {
    id: 'skill-translate',
    name: 'skill.translate',
    desc: 'Pico 快路径预设：忠实翻译并保留格式语气',
    prompt: '请忠实翻译以下内容，保留格式、专名和语气；不确定术语请标注：',
    tools: '无工具',
    risk: 'low',
  },
  {
    id: 'skill-meeting-notes',
    name: 'skill.meeting_notes',
    desc: 'Pico 快路径预设：整理会议决定、负责人和待办',
    prompt: '请把以下会议内容整理为议题、决定、负责人和待办；未明确负责人时标为待确认：',
    tools: '无工具',
    risk: 'low',
  },
];

export default function CapabilityHubPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tabParam = params.get('tab') as HubTab | null;
  const projectId = params.get('projectId');
  const returnTo = params.get('return');
  const [tab, setTab] = useState<HubTab>(
    tabParam && TABS.some((t) => t.id === tabParam) ? tabParam : 'experts',
  );
  const [q, setQ] = useState('');
  const [expertId, setExpertId] = useState<string | null>(null);
  const [skillId, setSkillId] = useState<string | null>(null);

  useEffect(() => {
    if (tabParam && TABS.some((t) => t.id === tabParam)) {
      setTab(tabParam);
    }
  }, [tabParam]);

  const setTabNav = (id: HubTab) => {
    setTab(id);
    setQ('');
    setExpertId(null);
    setSkillId(null);
    const next = new URLSearchParams(params);
    if (id === 'experts') {
      next.delete('tab');
    } else {
      next.set('tab', id);
    }
    setParams(next);
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
  const selectedSkill = DEMO_SKILLS.find((skill) => skill.id === skillId);

  const bindProjectCapability = (kind: 'expert' | 'skill', value: string) => {
    if (!projectId || !returnTo) {
      return false;
    }
    try {
      const key = `pico:projectBindings:${projectId}`;
      const current = JSON.parse(localStorage.getItem(key) || '{}') as Record<string, string>;
      localStorage.setItem(key, JSON.stringify({ ...current, [kind]: value }));
    } catch {
      /* return navigation still works */
    }
    navigate(returnTo);
    return true;
  };

  const summonExpert = (name: string, desc: string) => {
    if (bindProjectCapability('expert', name)) {
      return;
    }
    try {
      sessionStorage.setItem('pico:pendingExpert', name);
      sessionStorage.setItem('pico:pendingPrompt', `请以「${name}」专家身份协助：${desc}`);
      setActiveExpert(name);
      setPicoModelMode(preferredModelForExpert(name));
    } catch {
      /* ignore */
    }
    navigate('/c/new');
  };

  const startSkill = (skill: (typeof DEMO_SKILLS)[number]) => {
    if (bindProjectCapability('skill', skill.name)) {
      return;
    }
    try {
      sessionStorage.setItem('pico:pendingSkillLabel', skill.name);
      sessionStorage.setItem('pico:pendingPrompt', `【Pico-Skill:${skill.id}】\n${skill.prompt}`);
      setActiveExpert(null);
      setPicoModelMode(preferredModelForSkill(skill.id));
    } catch {
      /* ignore */
    }
    navigate('/c/new');
  };

  const connectorHref = (connectorId: string) => {
    const next = new URLSearchParams();
    if (projectId) {
      next.set('projectId', projectId);
    }
    if (returnTo) {
      next.set('return', returnTo);
    }
    const suffix = next.toString();
    return `/capability/connectors/${connectorId}${suffix ? `?${suffix}` : ''}`;
  };

  return (
    <WorkbenchShell
      title="专家·技能·连接器"
      subtitle="能力中心"
      backTo={returnTo || '/c/new'}
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
                className="rounded-lg border border-black/[0.06] bg-white p-4 text-left shadow-sm transition hover:border-black/12"
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
            <div className="rounded-lg border border-black/[0.06] bg-white p-5">
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
                className="mt-5 w-full rounded-lg bg-[#1a1a1a] py-2.5 text-[13px] font-medium text-white"
                onClick={() => summonExpert(selectedExpert.name, selectedExpert.desc)}
              >
                {projectId ? '绑定到项目' : '在任务中召唤'}
              </button>
            </div>
          </div>
        )}

        {tab === 'skills' && !selectedSkill && (
          <div className="mx-auto max-w-2xl space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[12px] text-[#8c8c8c]">
                Pico 技能快路径 · 完整目录与自定义技能请前往 /skills
              </p>
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
                onClick={() => setSkillId(s.id)}
                className="flex w-full items-start gap-3 rounded-lg border border-black/[0.06] bg-white p-4 text-left hover:border-black/12"
              >
                <div className="flex size-10 items-center justify-center rounded-xl bg-[#edf1f4]">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-medium">{s.name}</p>
                  <p className="mt-0.5 text-[12.5px] text-[#6b6b6b]">{s.desc}</p>
                  <p className="mt-1 truncate text-[11px] text-[#8c8c8c]">
                    tools: {s.tools} · risk: {s.risk}
                  </p>
                </div>
                <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-[#b0b0b0]" />
              </button>
            ))}
            <button
              type="button"
              onClick={() => navigate('/skills/new')}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-black/[0.12] py-4 text-[13px] text-[#6b6b6b]"
            >
              <Plus className="h-4 w-4" />
              添加自定义技能
            </button>
          </div>
        )}

        {tab === 'skills' && selectedSkill && (
          <div className="mx-auto max-w-lg space-y-3">
            <button
              type="button"
              className="text-[12.5px] text-[#6b6b6b] hover:underline"
              onClick={() => setSkillId(null)}
            >
              ← 返回技能列表
            </button>
            <div className="rounded-lg border border-black/[0.06] bg-white p-5">
              <div className="mb-4 flex items-start gap-3">
                <div className="flex size-10 items-center justify-center rounded-lg bg-[#edf1f4]">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-[17px] font-semibold">{selectedSkill.name}</p>
                  <p className="mt-1 text-[13px] text-[#6b6b6b]">{selectedSkill.desc}</p>
                </div>
              </div>
              <p className="text-[12px] font-medium text-[#8c8c8c]">任务模板</p>
              <p className="mt-1 rounded-lg bg-[#f5f5f5] p-3 text-[13px] leading-relaxed text-[#3d3d3d]">
                {selectedSkill.prompt}
              </p>
              <p className="mt-3 text-[11.5px] text-[#8c8c8c]">
                推荐模型：{preferredModelForSkill(selectedSkill.id)}
              </p>
              <p className="mt-1 text-[11.5px] text-[#8c8c8c]">
                发送时写入 Pico Run 快照：{selectedSkill.id} · tools: {selectedSkill.tools}
              </p>
              <button
                type="button"
                className="mt-5 w-full rounded-lg bg-[#1a1a1a] py-2.5 text-[13px] font-medium text-white"
                onClick={() => startSkill(selectedSkill)}
              >
                {projectId ? '绑定到项目' : '用此技能新建任务'}
              </button>
            </div>
          </div>
        )}

        {tab === 'connectors' && (
          <div className="grid gap-3 sm:grid-cols-2">
            {connectors.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => navigate(connectorHref(c.id))}
                className="flex items-start gap-3 rounded-lg border border-black/[0.06] bg-white p-4 text-left hover:border-black/12"
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
