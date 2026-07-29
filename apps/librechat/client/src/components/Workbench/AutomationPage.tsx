/**
 * Automation list + create form shell (clean-room from research).
 * Execution scheduler is server-side (P2); UI first.
 */
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, ArrowLeft } from 'lucide-react';
import { cn } from '~/utils';

type Mode = 'list' | 'create';
type ScheduleKind = 'periodic' | 'interval' | 'once';

const LS_KEY = 'pico:automations';

type AutomationDraft = {
  id: string;
  name: string;
  prompt: string;
  scheduleKind: ScheduleKind;
  scheduleLabel: string;
  createdAt: string;
};

function loadList(): AutomationDraft[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as AutomationDraft[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveList(list: AutomationDraft[]) {
  localStorage.setItem(LS_KEY, JSON.stringify(list));
}

export default function AutomationPage() {
  const [mode, setMode] = useState<Mode>('list');
  const [list, setList] = useState<AutomationDraft[]>(() =>
    typeof window !== 'undefined' ? loadList() : [],
  );
  const [name, setName] = useState('');
  const [prompt, setPrompt] = useState('');
  const [scheduleKind, setScheduleKind] = useState<ScheduleKind>('periodic');
  const [time, setTime] = useState('09:00');

  const scheduleLabel = useMemo(() => {
    if (scheduleKind === 'periodic') {
      return `每天 ${time}`;
    }
    if (scheduleKind === 'interval') {
      return '按间隔';
    }
    return '单次';
  }, [scheduleKind, time]);

  const onSave = () => {
    if (!name.trim() || !prompt.trim()) {
      return;
    }
    const item: AutomationDraft = {
      id: `auto_${Date.now()}`,
      name: name.trim(),
      prompt: prompt.trim(),
      scheduleKind,
      scheduleLabel,
      createdAt: new Date().toISOString(),
    };
    const next = [item, ...list];
    setList(next);
    saveList(next);
    setMode('list');
    setName('');
    setPrompt('');
  };

  if (mode === 'create') {
    return (
      <div className="flex h-full flex-col bg-[#fafafa] text-[#1a1a1a] dark:bg-presentation dark:text-text-primary">
        <header className="flex h-12 items-center justify-between border-b border-black/[0.06] bg-white px-4 dark:border-border-light dark:bg-surface-primary">
          <div className="flex items-center gap-2 text-[14px] font-medium">
            <button
              type="button"
              className="rounded-md p-1 hover:bg-black/[0.04]"
              onClick={() => setMode('list')}
              aria-label="取消"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            自动化 / 添加自动化任务
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded-lg px-3 py-1.5 text-[13px] text-[#6b6b6b] hover:bg-black/[0.04]"
              onClick={() => setMode('list')}
            >
              取消
            </button>
            <button
              type="button"
              className="rounded-lg bg-[#1a1a1a] px-3 py-1.5 text-[13px] font-medium text-white disabled:opacity-40"
              disabled={!name.trim() || !prompt.trim()}
              onClick={onSave}
            >
              保存
            </button>
          </div>
        </header>

        <div className="mx-auto w-full max-w-2xl flex-1 overflow-y-auto px-6 py-6">
          <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-900">
            浏览器版由服务端调度执行；请保持 Pico 服务可用。桌面端「退出客户端即停止」的限制不适用于本产品。
          </div>

          <label className="mb-4 block">
            <span className="mb-1.5 block text-[13px] font-medium">名称</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-xl border border-black/[0.08] bg-white px-3 py-2.5 text-[14px] outline-none focus:border-black/20 dark:bg-surface-secondary"
              placeholder="例如：生成昨日 AI 重点资讯总结"
            />
          </label>

          <label className="mb-4 block">
            <span className="mb-1.5 block text-[13px] font-medium">工作空间（可选）</span>
            <input
              disabled
              className="w-full rounded-xl border border-black/[0.06] bg-[#f5f5f5] px-3 py-2.5 text-[13px] text-[#9a9a9a]"
              value="绑定服务端工作空间（P1）"
              readOnly
            />
          </label>

          <label className="mb-4 block">
            <span className="mb-1.5 block text-[13px] font-medium">提示词</span>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={5}
              className="w-full resize-none rounded-xl border border-black/[0.08] bg-white px-3 py-2.5 text-[14px] outline-none focus:border-black/20 dark:bg-surface-secondary"
              placeholder="描述到点后要执行的任务"
            />
          </label>

          <div className="mb-2 text-[13px] font-medium">执行频率</div>
          <p className="mb-2 text-[12px] text-[#8c8c8c]">
            建议避开上午高峰时段，高峰期容易排队；选择非高峰期更稳定
          </p>
          <div className="mb-4 flex gap-2">
            {(
              [
                ['periodic', '周期'],
                ['interval', '按间隔'],
                ['once', '单次'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setScheduleKind(id)}
                className={cn(
                  'rounded-full px-3.5 py-1.5 text-[13px]',
                  scheduleKind === id
                    ? 'bg-[#1a1a1a] text-white'
                    : 'bg-white text-[#4a4a4a] ring-1 ring-black/[0.06]',
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {scheduleKind === 'periodic' && (
            <label className="mb-4 flex items-center gap-3 text-[13px]">
              <span>每天</span>
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                className="rounded-lg border border-black/[0.08] bg-white px-2 py-1.5"
              />
            </label>
          )}

          <div className="mb-2 text-[13px] font-medium">连接器</div>
          <p className="mb-3 text-[12px] text-[#8c8c8c]">
            勾选即授权该连接器在任务中免确认使用（P1 接 MCP 实例）
          </p>
          <button
            type="button"
            className="rounded-xl border border-dashed border-black/[0.12] px-3 py-2 text-[13px] text-[#6b6b6b]"
          >
            选择连接器
          </button>

          <div className="mt-6 space-y-2 text-[12.5px] text-[#8c8c8c]">
            <label className="flex items-center gap-2">
              <input type="checkbox" disabled className="rounded" />
              推送到微信小程序（后置）
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" disabled className="rounded" />
              推送到企微通知 bot（后置）
            </label>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-[#fafafa] dark:bg-presentation">
      <header className="flex h-12 items-center justify-between border-b border-black/[0.06] bg-white px-4 dark:border-border-light dark:bg-surface-primary">
        <h1 className="text-[15px] font-semibold text-[#1a1a1a] dark:text-text-primary">自动化</h1>
        <button
          type="button"
          onClick={() => setMode('create')}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[#1a1a1a] px-3 py-1.5 text-[13px] font-medium text-white"
        >
          <Plus className="h-3.5 w-3.5" />
          添加自动化任务
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        {list.length === 0 ? (
          <div className="mx-auto flex max-w-md flex-col items-center gap-3 pt-20 text-center">
            <p className="text-[15px] font-medium text-[#1a1a1a] dark:text-text-primary">
              定时任务
            </p>
            <p className="text-[13px] leading-relaxed text-[#8c8c8c]">
              配置名称、提示词与执行频率后，到点由服务端创建正常 Task/Run 并写入运行记录。
            </p>
            <button
              type="button"
              onClick={() => setMode('create')}
              className="mt-2 rounded-lg bg-[#1a1a1a] px-4 py-2 text-[13px] text-white"
            >
              添加自动化任务
            </button>
            <Link to="/c/new" className="text-[12px] text-[#8c8c8c] underline">
              返回新建任务
            </Link>
          </div>
        ) : (
          <ul className="mx-auto max-w-2xl space-y-2">
            {list.map((item) => (
              <li
                key={item.id}
                className="rounded-xl border border-black/[0.06] bg-white px-4 py-3 dark:border-border-light dark:bg-surface-secondary"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-[14px] font-medium text-[#1a1a1a] dark:text-text-primary">
                      {item.name}
                    </p>
                    <p className="mt-1 line-clamp-2 text-[12.5px] text-[#6b6b6b]">{item.prompt}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-[#edf1f4] px-2.5 py-1 text-[11px] text-[#3d3d3d]">
                    {item.scheduleLabel}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
