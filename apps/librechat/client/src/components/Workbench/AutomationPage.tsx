/**
 * Automation list + create form — backed by Pico /v1/automations (server scheduler).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, ArrowLeft, Loader2 } from 'lucide-react';
import { cn } from '~/utils';
import {
  createPicoAutomation,
  deletePicoAutomation,
  listPicoAutomations,
  setPicoAutomationEnabled,
  type PicoAutomation,
} from '~/data-provider/pico/api';

type Mode = 'list' | 'create';
type ScheduleKind = 'periodic' | 'interval' | 'once';

function friendlyError(raw: string): string {
  if (/401|No auth token|Unauthorized/i.test(raw)) {
    return '登录已失效或未带上身份，请刷新页面后重新登录再试。';
  }
  if (/502|unavailable|Failed to fetch/i.test(raw)) {
    return '账本服务暂时不可用，请稍后重试。';
  }
  return raw.slice(0, 200);
}

export default function AutomationPage() {
  const [mode, setMode] = useState<Mode>('list');
  const [list, setList] = useState<PicoAutomation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [prompt, setPrompt] = useState('');
  const [model, setModel] = useState('kimi-k2.6');
  const [scheduleKind, setScheduleKind] = useState<ScheduleKind>('periodic');
  const [time, setTime] = useState('09:00');
  const [intervalMin, setIntervalMin] = useState(60);
  const [onceLocal, setOnceLocal] = useState(() => {
    const d = new Date(Date.now() + 5 * 60_000);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  });
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { automations } = await listPicoAutomations();
      setList(automations || []);
    } catch (e) {
      setError(friendlyError(e instanceof Error ? e.message : String(e)));
      setList([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const schedulePayload = useMemo(() => {
    if (scheduleKind === 'periodic') {
      return { time, model };
    }
    if (scheduleKind === 'interval') {
      return { minutes: intervalMin, model };
    }
    let at = new Date(Date.now() + 60_000).toISOString();
    try {
      const parsed = new Date(onceLocal);
      if (!Number.isNaN(parsed.getTime())) {
        at = parsed.toISOString();
      }
    } catch {
      /* keep default */
    }
    return { at, model };
  }, [scheduleKind, time, intervalMin, onceLocal, model]);

  const scheduleLabel = (a: PicoAutomation) => {
    const m = (a.schedule as { model?: string })?.model;
    const modelBit = m ? ` · ${m}` : '';
    if (a.schedule_kind === 'periodic') {
      return `每天 ${String((a.schedule as { time?: string })?.time || '09:00')}${modelBit}`;
    }
    if (a.schedule_kind === 'interval') {
      return `每 ${(a.schedule as { minutes?: number })?.minutes || 60} 分钟${modelBit}`;
    }
    const at = (a.schedule as { at?: string })?.at;
    if (at) {
      try {
        return `单次 ${new Date(at).toLocaleString()}${modelBit}`;
      } catch {
        /* fallthrough */
      }
    }
    return `单次${modelBit}`;
  };

  const onSave = async () => {
    if (!name.trim() || !prompt.trim() || saving) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const bodyPrompt =
        model && model !== 'Auto'
          ? `【模型偏好：${model}】\n${prompt.trim()}`
          : prompt.trim();
      await createPicoAutomation({
        name: name.trim(),
        prompt: bodyPrompt,
        schedule_kind: scheduleKind,
        schedule: schedulePayload,
      });
      setMode('list');
      setName('');
      setPrompt('');
      await refresh();
    } catch (e) {
      setError(friendlyError(e instanceof Error ? e.message : String(e)));
    } finally {
      setSaving(false);
    }
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
              disabled={!name.trim() || !prompt.trim() || saving}
              onClick={() => void onSave()}
            >
              {saving ? '保存中…' : '保存'}
            </button>
          </div>
        </header>

        <div className="mx-auto w-full max-w-2xl flex-1 overflow-y-auto px-6 py-6">
          <div className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12.5px] text-emerald-900">
            到点由 Pico 服务端创建 Task/Run 并执行，无需保持桌面客户端在线。
          </div>
          {error ? (
            <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-[13px] text-red-700">{error}</p>
          ) : null}

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
            <span className="mb-1.5 block text-[13px] font-medium">提示词</span>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={5}
              className="w-full resize-none rounded-xl border border-black/[0.08] bg-white px-3 py-2.5 text-[14px] outline-none focus:border-black/20 dark:bg-surface-secondary"
              placeholder="描述到点后要执行的任务"
            />
          </label>

          <label className="mb-4 block">
            <span className="mb-1.5 block text-[13px] font-medium">模型</span>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full rounded-xl border border-black/[0.08] bg-white px-3 py-2.5 text-[14px] outline-none dark:bg-surface-secondary"
            >
              <option value="kimi-k2.6">kimi-k2.6</option>
              <option value="Kimi-K3">Kimi-K3</option>
              <option value="moonshot-v1-8k">moonshot-v1-8k</option>
              <option value="pico-agent">pico-agent</option>
            </select>
          </label>

          <div className="mb-2 text-[13px] font-medium">执行频率</div>
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
          {scheduleKind === 'interval' && (
            <label className="mb-4 flex items-center gap-3 text-[13px]">
              <span>每隔</span>
              <input
                type="number"
                min={1}
                max={10080}
                value={intervalMin}
                onChange={(e) => setIntervalMin(Number(e.target.value) || 60)}
                className="w-24 rounded-lg border border-black/[0.08] bg-white px-2 py-1.5"
              />
              <span>分钟</span>
            </label>
          )}
          {scheduleKind === 'once' && (
            <label className="mb-4 block text-[13px]">
              <span className="mb-1.5 block font-medium">触发时间</span>
              <input
                type="datetime-local"
                value={onceLocal}
                onChange={(e) => setOnceLocal(e.target.value)}
                className="rounded-lg border border-black/[0.08] bg-white px-2 py-1.5"
              />
              <p className="mt-1 text-[12px] text-[#8c8c8c]">触发一次后自动停用。</p>
            </label>
          )}

          <p className="text-[12px] leading-relaxed text-[#9a9a9a]">
            工作空间 / 权限 / 技能绑定将在后续版本接入；当前按账号默认工作空间与模型执行。
          </p>
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
        {loading ? (
          <div className="flex items-center justify-center gap-2 pt-20 text-[#8c8c8c]">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载中…
          </div>
        ) : null}
        {error ? (
          <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-[13px] text-red-700">{error}</p>
        ) : null}
        {!loading && list.length === 0 ? (
          <div className="mx-auto flex max-w-md flex-col items-center gap-3 pt-20 text-center">
            <p className="text-[15px] font-medium text-[#1a1a1a] dark:text-text-primary">定时任务</p>
            <p className="text-[13px] leading-relaxed text-[#8c8c8c]">
              配置名称、提示词、模型与执行频率后，到点由服务端创建 Task/Run 并写入运行记录。
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
        ) : null}
        {list.length > 0 ? (
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
                    {item.last_run_at ? (
                      <p className="mt-1 text-[11px] text-[#9a9a9a]">
                        上次：{new Date(item.last_run_at).toLocaleString()}
                      </p>
                    ) : null}
                    {item.next_run_at ? (
                      <p className="mt-0.5 text-[11px] text-[#9a9a9a]">
                        下次：{new Date(item.next_run_at).toLocaleString()}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="rounded-full bg-[#edf1f4] px-2.5 py-1 text-[11px] text-[#3d3d3d]">
                      {scheduleLabel(item)}
                    </span>
                    <span className="text-[10px] text-[#9a9a9a]">
                      {item.enabled ? '已启用' : '已停用'}
                    </span>
                    <button
                      type="button"
                      className="text-[11px] text-[#6b6b6b] underline"
                      onClick={() =>
                        void setPicoAutomationEnabled(item.id, !item.enabled).then(refresh)
                      }
                    >
                      {item.enabled ? '停用' : '启用'}
                    </button>
                    <button
                      type="button"
                      className="text-[11px] text-red-600/80"
                      onClick={() => void deletePicoAutomation(item.id).then(refresh)}
                    >
                      删除
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
