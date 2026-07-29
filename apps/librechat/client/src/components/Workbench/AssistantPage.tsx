/**
 * 助理 — local assistants + connection status (not marketplace dump).
 */
import { useNavigate } from 'react-router-dom';
import { Bot, Smartphone, Plus, MessageSquare } from 'lucide-react';

export default function AssistantPage() {
  const navigate = useNavigate();

  return (
    <div className="flex h-full flex-col bg-[#fafafa] dark:bg-presentation">
      <header className="flex h-12 items-center justify-between border-b border-black/[0.06] bg-white px-4 dark:border-border-light dark:bg-surface-primary">
        <h1 className="text-[15px] font-semibold text-[#1a1a1a] dark:text-text-primary">助理</h1>
        <button
          type="button"
          onClick={() => navigate('/agents')}
          className="rounded-lg border border-black/[0.08] px-3 py-1.5 text-[12.5px] text-[#3d3d3d]"
        >
          高级 Agent 市场
        </button>
      </header>

      <div className="mx-auto w-full max-w-2xl space-y-4 p-6">
        <section className="rounded-2xl border border-black/[0.06] bg-white p-5 dark:border-border-light dark:bg-surface-secondary">
          <div className="flex items-start gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-[#1a1a1a] text-white">
              <Bot className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-medium">Pico 本地助理</p>
              <p className="mt-1 text-[13px] leading-relaxed text-[#6b6b6b]">
                默认任务执行者。通过 Kimi 模型与 Pico 编排完成规划、执行与产物沉淀。
              </p>
              <button
                type="button"
                onClick={() => navigate('/c/new')}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[#1a1a1a] px-3 py-1.5 text-[12.5px] font-medium text-white"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                新建任务
              </button>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-black/[0.06] bg-white p-5 dark:border-border-light dark:bg-surface-secondary">
          <p className="mb-3 text-[12px] font-medium uppercase tracking-wide text-[#9a9a9a]">
            已连接
          </p>
          <div className="flex items-center gap-3 rounded-xl bg-[#fafafa] px-3 py-3 dark:bg-surface-tertiary">
            <Smartphone className="h-5 w-5 text-[#6b6b6b]" />
            <div className="min-w-0 flex-1">
              <p className="text-[13.5px] font-medium">微信小程序遥控</p>
              <p className="text-[12px] text-[#8c8c8c]">桌面专属 · 浏览器版后置</p>
            </div>
            <span className="rounded-full bg-[#edf1f4] px-2 py-0.5 text-[11px] text-[#6b6b6b]">
              后置
            </span>
          </div>
        </section>

        <button
          type="button"
          className="flex w-full items-center justify-center gap-2 rounded-2xl border border-dashed border-black/[0.12] py-4 text-[13px] text-[#6b6b6b] hover:bg-white"
        >
          <Plus className="h-4 w-4" />
          添加本地助理（P1）
        </button>
      </div>
    </div>
  );
}
