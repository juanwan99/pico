/**
 * 助理 — list + detail actions (click-through WorkBuddy-class).
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PicoIcon } from '~/components/ui/pico-icons';
import WorkbenchShell from './WorkbenchShell';
import { preferredModelForExpert, queuePendingModel, setActiveExpert } from '~/utils/picoModelPref';
import { appendPendingPrompt } from './workbenchSession';

const ASSISTANTS = [
  {
    id: 'pico-default',
    name: 'Pico 本地助理',
    desc: '默认任务执行者。Pi + Pico 编排，产物进账本与结果区。',
    model: 'DeepSeek / Pi',
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
        appendPendingPrompt(`请以「${a.expert}」的角色协助完成任务：`);
        setActiveExpert(a.expert);
        queuePendingModel(preferredModelForExpert(a.expert));
      } else {
        setActiveExpert(null);
        queuePendingModel(a.model?.includes('pico-deep') ? 'pico-deep' : 'pico-fast');
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
          className="pico-chip px-3 py-1.5 text-[12.5px]"
        >
          Agent 市场
        </button>
      }
    >
      <div className="mx-auto grid w-full min-w-0 max-w-4xl gap-3 p-4 sm:p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="min-w-0 space-y-2">
          {ASSISTANTS.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setOpenId(a.id)}
              className={
                openId === a.id
                  ? 'pico-card flex w-full items-center gap-3 border-[color:var(--pico-violet-line)] p-4 text-left shadow-[0_0_0_2px_var(--pico-violet-wash)]'
                  : 'pico-card pico-card-interactive flex w-full items-center gap-3 p-4 text-left'
              }
            >
              <div className="pico-icon-medallion">
                <PicoIcon name="bot" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-medium">{a.name}</p>
                <p className="truncate text-[12px] text-[color:var(--pico-ink-2)]">{a.desc}</p>
              </div>
              <PicoIcon name="arrow" size="sm" className="text-[color:var(--pico-ink-3)]" />
            </button>
          ))}

          <button
            type="button"
            className="flex w-full items-center justify-center gap-2 rounded-[var(--pico-radius-sm)] border border-dashed border-[color:var(--pico-line-2)] py-4 text-[13px] text-[color:var(--pico-ink-2)] transition-colors hover:bg-[color:var(--pico-surface-2)]"
            onClick={() => navigate('/agents')}
          >
            <PicoIcon name="plus" size="sm" />
            添加助理（市场）
          </button>

          <div className="pico-panel p-4">
            <p className="mb-2 text-[12px] font-medium uppercase tracking-[0.08em] text-[color:var(--pico-ink-3)]">
              已连接
            </p>
            <div className="flex items-center gap-3 rounded-xl bg-[color:var(--pico-surface-2)] px-3 py-3">
              <PicoIcon name="link" className="text-[color:var(--pico-ink-2)]" />
              <div className="min-w-0 flex-1">
                <p className="text-[13.5px] font-medium">微信小程序遥控</p>
                <p className="text-[12px] text-[color:var(--pico-ink-2)]">
                  桌面专属 · 浏览器版后置
                </p>
              </div>
              <span className="rounded-full bg-[color:var(--pico-violet-wash)] px-2 py-0.5 text-[11px] text-[color:var(--pico-violet-dark)]">
                后置
              </span>
            </div>
          </div>
        </div>

        <div className="pico-card min-w-0 overflow-hidden p-5">
          {open ? (
            <>
              <div className="flex items-start gap-3">
                <div className="pico-icon-medallion size-12">
                  <PicoIcon name="bot" size="lg" />
                </div>
                <div className="min-w-0">
                  <p className="text-[16px] font-semibold">{open.name}</p>
                  <p className="mt-1 break-words text-[13px] leading-relaxed text-[color:var(--pico-ink-2)]">
                    {open.desc}
                  </p>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-2 rounded-xl bg-[color:var(--pico-violet-wash)] px-3 py-2 text-[12.5px] text-[color:var(--pico-violet-dark)]">
                <PicoIcon name="spark" size="sm" />
                模型：{open.model}
              </div>
              <ul className="mt-4 space-y-2 text-[12.5px] text-[color:var(--pico-ink-2)]">
                <li>· 对话与多步（选 pico-agent）走 Pico API</li>
                <li>· 产物进入任务右栏「结果区」与「我的文件」</li>
                <li>· 业务变更须 S7 人工确认，无静默写库</li>
              </ul>
              <button
                type="button"
                onClick={() => start(open)}
                className="pico-cta-accent mt-5 inline-flex w-full items-center justify-center gap-1.5 py-2.5 text-[13px] font-medium"
              >
                <PicoIcon name="message" size="sm" />
                用此助理新建任务
              </button>
            </>
          ) : (
            <p className="text-[13px] text-[color:var(--pico-ink-3)]">选择左侧助理查看详情</p>
          )}
        </div>
      </div>
    </WorkbenchShell>
  );
}
