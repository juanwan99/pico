/**
 * 助理 — list + detail actions (click-through WorkBuddy-class).
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bot, Smartphone, Plus, MessageSquare, ChevronRight, Sparkles } from 'lucide-react';
import WorkbenchShell from './WorkbenchShell';
import {
  preferredModelForExpert,
  setActiveExpert,
  setPicoModelMode,
} from '~/utils/picoModelPref';

const ASSISTANTS = [
  {
    id: 'pico-default',
    name: 'Pico 本地助理',
    desc: '默认任务执行者。Kimi + Pico 编排，产物进账本与结果区。',
    model: 'kimi-k2.6 / pico-agent',
    ready: true,
  },
  {
    id: 'doc',
    name: '文档助理',
    desc: '长文整理与可交付稿',
    model: '专家预设',
    ready: true,
    expert: '文档助理',
  },
  {
    id: 'code',
    name: '代码搭档',
    desc: '读代码、解释错误、补丁建议',
    model: '专家预设',
    ready: true,
    expert: '代码搭档',
  },
];

export default function AssistantPage() {
  const navigate = useNavigate();
  const [openId, setOpenId] = useState<string | null>('pico-default');
  const open = ASSISTANTS.find((a) => a.id === openId);

  const start = (a: (typeof ASSISTANTS)[0]) => {
    try {
      if (a.expert) {
        sessionStorage.setItem('pico:pendingExpert', a.expert);
        sessionStorage.setItem('pico:pendingPrompt', `请以「${a.expert}」的角色协助完成任务：`);
        setActiveExpert(a.expert);
        setPicoModelMode(preferredModelForExpert(a.expert));
      } else {
        setActiveExpert(null);
        setPicoModelMode(a.model?.includes('pico-agent') ? 'pico-agent' : 'kimi-k2.6');
      }
    } catch {
      /* ignore */
    }
    navigate('/c/new');
  };

  return (
    <WorkbenchShell
      title="助理"
      subtitle="本地执行者"
      actions={
        <button
          type="button"
          onClick={() => navigate('/agents')}
          className="rounded-lg border border-black/[0.08] px-3 py-1.5 text-[12.5px] text-[#3d3d3d]"
        >
          Agent 市场
        </button>
      }
    >
      <div className="mx-auto grid w-full max-w-4xl gap-4 p-6 lg:grid-cols-[1fr_1.1fr]">
        <div className="space-y-2">
          {ASSISTANTS.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setOpenId(a.id)}
              className={
                openId === a.id
                  ? 'flex w-full items-center gap-3 rounded-2xl border border-[#1a1a1a] bg-white p-3.5 text-left shadow-sm'
                  : 'flex w-full items-center gap-3 rounded-2xl border border-black/[0.06] bg-white p-3.5 text-left hover:border-black/12'
              }
            >
              <div className="flex size-10 items-center justify-center rounded-2xl bg-[#1a1a1a] text-white">
                <Bot className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-medium">{a.name}</p>
                <p className="truncate text-[12px] text-[#8c8c8c]">{a.desc}</p>
              </div>
              <ChevronRight className="h-4 w-4 text-[#b0b0b0]" />
            </button>
          ))}

          <button
            type="button"
            className="flex w-full items-center justify-center gap-2 rounded-2xl border border-dashed border-black/[0.12] py-4 text-[13px] text-[#6b6b6b]"
            onClick={() => navigate('/agents')}
          >
            <Plus className="h-4 w-4" />
            添加助理（市场）
          </button>

          <div className="rounded-2xl border border-black/[0.06] bg-white p-4">
            <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-[#9a9a9a]">
              已连接
            </p>
            <div className="flex items-center gap-3 rounded-xl bg-[#fafafa] px-3 py-3">
              <Smartphone className="h-5 w-5 text-[#6b6b6b]" />
              <div className="min-w-0 flex-1">
                <p className="text-[13.5px] font-medium">微信小程序遥控</p>
                <p className="text-[12px] text-[#8c8c8c]">桌面专属 · 浏览器版后置</p>
              </div>
              <span className="rounded-full bg-[#edf1f4] px-2 py-0.5 text-[11px] text-[#6b6b6b]">
                后置
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-black/[0.06] bg-white p-5">
          {open ? (
            <>
              <div className="flex items-start gap-3">
                <div className="flex size-12 items-center justify-center rounded-2xl bg-[#1a1a1a] text-white">
                  <Bot className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-[16px] font-semibold">{open.name}</p>
                  <p className="mt-1 text-[13px] leading-relaxed text-[#6b6b6b]">{open.desc}</p>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-2 rounded-xl bg-[#f5f5f5] px-3 py-2 text-[12.5px] text-[#3d3d3d]">
                <Sparkles className="h-3.5 w-3.5" />
                模型：{open.model}
              </div>
              <ul className="mt-4 space-y-2 text-[12.5px] text-[#4a4a4a]">
                <li>· 对话与多步（选 pico-agent）走 Pico API</li>
                <li>· 产物进入任务右栏「结果区」与「我的文件」</li>
                <li>· 业务变更须 S7 人工确认，无静默写库</li>
              </ul>
              <button
                type="button"
                onClick={() => start(open)}
                className="mt-5 inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-[#1a1a1a] py-2.5 text-[13px] font-medium text-white"
              >
                <MessageSquare className="h-4 w-4" />
                用此助理新建任务
              </button>
            </>
          ) : (
            <p className="text-[13px] text-[#8c8c8c]">选择左侧助理查看详情</p>
          )}
        </div>
      </div>
    </WorkbenchShell>
  );
}
