/**
 * Automation list + create form backed by Pico /v1/automations.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  Check,
  Clock3,
  FolderKanban,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
} from 'lucide-react';
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
type PermissionMode = 'account-default' | 'read-only' | 'restricted';
type BindingKind = 'none' | 'skill' | 'expert';

type AutomationUiMeta = {
  schema: 'pico.automation-ui/v1';
  model: string;
  workspace: {
    id: string;
    label: string;
  };
  permission: PermissionMode;
  binding: {
    kind: BindingKind;
    id: string;
    label: string;
  };
  requested_enabled: boolean;
};

const MODELS = ['kimi-k2.6', 'Kimi-K3', 'moonshot-v1-8k', 'pico-agent'] as const;

const WORKSPACES = [
  { id: 'account-default', label: '账号默认工作空间', supported: true },
  { id: 'personal', label: '个人工作空间', supported: false },
  { id: 'current-project', label: '当前项目空间', supported: false },
] as const;

const PERMISSIONS: {
  id: PermissionMode;
  label: string;
  detail: string;
  supported: boolean;
}[] = [
  {
    id: 'account-default',
    label: '账号默认权限',
    detail: '按服务端当前 ai:run / ai:read 权限执行',
    supported: true,
  },
  {
    id: 'read-only',
    label: '只读审阅',
    detail: '保存为权限偏好，服务端暂未强制',
    supported: false,
  },
  {
    id: 'restricted',
    label: '受限执行',
    detail: '保存为权限偏好，服务端暂未强制',
    supported: false,
  },
];

const BINDINGS: {
  id: string;
  kind: BindingKind;
  label: string;
  detail: string;
}[] = [
  { id: 'none', kind: 'none', label: '不绑定', detail: '直接执行提示词' },
  { id: 'skill-meeting', kind: 'skill', label: '技能 · 会议纪要', detail: '保存技能偏好' },
  { id: 'skill-weekly', kind: 'skill', label: '技能 · 周报生成', detail: '保存技能偏好' },
  { id: 'expert-docs', kind: 'expert', label: '专家 · 文档助理', detail: '保存专家偏好' },
  { id: 'expert-research', kind: 'expert', label: '专家 · 研究分析', detail: '保存专家偏好' },
];

function friendlyError(raw: string): string {
  if (/401|No auth token|Unauthorized/i.test(raw)) {
    return '登录已失效或未带上身份，请刷新页面后重新登录再试。';
  }
  if (/502|unavailable|Failed to fetch/i.test(raw)) {
    return '自动化服务暂时不可用，请稍后重试。';
  }
  if (/404|not found/i.test(raw)) {
    return '该自动化任务已不存在，请刷新列表。';
  }
  return raw.slice(0, 200);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function readUiMeta(automation: PicoAutomation): AutomationUiMeta | null {
  const raw = asRecord(automation.schedule?.pico_ui);
  const workspace = asRecord(raw?.workspace);
  const binding = asRecord(raw?.binding);
  if (!raw || raw.schema !== 'pico.automation-ui/v1' || !workspace || !binding) {
    return null;
  }

  const permission = asString(raw.permission) as PermissionMode;
  const kind = asString(binding.kind) as BindingKind;
  if (
    !['account-default', 'read-only', 'restricted'].includes(permission) ||
    !['none', 'skill', 'expert'].includes(kind)
  ) {
    return null;
  }

  return {
    schema: 'pico.automation-ui/v1',
    model: asString(raw.model, 'Auto'),
    workspace: {
      id: asString(workspace.id, 'account-default'),
      label: asString(workspace.label, '账号默认工作空间'),
    },
    permission,
    binding: {
      kind,
      id: asString(binding.id, 'none'),
      label: asString(binding.label, '不绑定'),
    },
    requested_enabled: raw.requested_enabled !== false,
  };
}

function promptWithoutModelPrefix(prompt: string): string {
  return prompt.replace(/^【模型偏好：[^】]+】\r?\n/, '');
}

function formatDate(value?: string | null): string {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString();
}

function scheduleLabel(automation: PicoAutomation): string {
  if (automation.schedule_kind === 'periodic') {
    return `每天 ${asString(automation.schedule?.time, '09:00')}`;
  }
  if (automation.schedule_kind === 'interval') {
    const minutes =
      typeof automation.schedule?.minutes === 'number' ? automation.schedule.minutes : 60;
    return `每 ${minutes} 分钟`;
  }
  const at = asString(automation.schedule?.at);
  return at ? `单次 ${formatDate(at)}` : '单次执行';
}

function Toggle({
  checked,
  disabled,
  label,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  label: string;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onChange}
      className={cn(
        'relative h-5 w-9 shrink-0 rounded-full transition-colors disabled:cursor-wait disabled:opacity-50',
        checked ? 'bg-[#1a1a1a]' : 'bg-[#d8d8d8]',
      )}
    >
      <span
        className={cn(
          'absolute top-0.5 size-4 rounded-full bg-white shadow-sm transition-transform',
          checked ? 'translate-x-[18px]' : 'translate-x-0.5',
        )}
      />
    </button>
  );
}

export default function AutomationPage() {
  const [mode, setMode] = useState<Mode>('list');
  const [list, setList] = useState<PicoAutomation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PicoAutomation | null>(null);

  const [name, setName] = useState('');
  const [prompt, setPrompt] = useState('');
  const [model, setModel] = useState('kimi-k2.6');
  const [scheduleKind, setScheduleKind] = useState<ScheduleKind>('periodic');
  const [time, setTime] = useState('09:00');
  const [intervalMin, setIntervalMin] = useState(60);
  const [workspaceId, setWorkspaceId] = useState('account-default');
  const [permission, setPermission] = useState<PermissionMode>('account-default');
  const [bindingId, setBindingId] = useState('none');
  const [createEnabled, setCreateEnabled] = useState(true);
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
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectedWorkspace =
    WORKSPACES.find((workspace) => workspace.id === workspaceId) ?? WORKSPACES[0];
  const selectedPermission =
    PERMISSIONS.find((item) => item.id === permission) ?? PERMISSIONS[0];
  const selectedBinding = BINDINGS.find((binding) => binding.id === bindingId) ?? BINDINGS[0];

  const uiMeta = useMemo<AutomationUiMeta>(
    () => ({
      schema: 'pico.automation-ui/v1',
      model,
      workspace: {
        id: selectedWorkspace.id,
        label: selectedWorkspace.label,
      },
      permission,
      binding: {
        kind: selectedBinding.kind,
        id: selectedBinding.id,
        label: selectedBinding.label,
      },
      requested_enabled: createEnabled,
    }),
    [createEnabled, model, permission, selectedBinding, selectedWorkspace],
  );

  const schedulePayload = useMemo<Record<string, unknown>>(() => {
    const common = { model, pico_ui: uiMeta };
    if (scheduleKind === 'periodic') {
      return { time, ...common };
    }
    if (scheduleKind === 'interval') {
      return { minutes: intervalMin, ...common };
    }
    const parsed = new Date(onceLocal);
    const at = Number.isNaN(parsed.getTime())
      ? new Date(Date.now() + 60_000).toISOString()
      : parsed.toISOString();
    return { at, ...common };
  }, [scheduleKind, time, intervalMin, onceLocal, model, uiMeta]);

  const resetForm = () => {
    setName('');
    setPrompt('');
    setModel('kimi-k2.6');
    setScheduleKind('periodic');
    setTime('09:00');
    setIntervalMin(60);
    setWorkspaceId('account-default');
    setPermission('account-default');
    setBindingId('none');
    setCreateEnabled(true);
  };

  const closeCreate = () => {
    setActionError(null);
    setMode('list');
  };

  const onSave = async () => {
    if (!name.trim() || !prompt.trim() || saving) {
      return;
    }

    setSaving(true);
    setActionError(null);
    let created: PicoAutomation | null = null;
    try {
      const bodyPrompt =
        model && model !== 'Auto'
          ? `【模型偏好：${model}】\n${prompt.trim()}`
          : prompt.trim();
      const result = await createPicoAutomation({
        name: name.trim(),
        prompt: bodyPrompt,
        schedule_kind: scheduleKind,
        schedule: schedulePayload,
      });
      created = result.automation;
      if (!createEnabled) {
        await setPicoAutomationEnabled(created.id, false);
      }
      resetForm();
      setMode('list');
      await refresh();
    } catch (e) {
      const message = friendlyError(e instanceof Error ? e.message : String(e));
      if (created && !createEnabled) {
        setMode('list');
        await refresh();
        setError(`任务已创建，但初始停用失败，当前可能仍在运行。请立即手动停用。${message}`);
      } else {
        setActionError(message);
      }
    } finally {
      setSaving(false);
    }
  };

  const onToggle = async (item: PicoAutomation) => {
    if (pendingId) {
      return;
    }
    setPendingId(item.id);
    setActionError(null);
    try {
      const { automation } = await setPicoAutomationEnabled(item.id, !item.enabled);
      setList((current) =>
        current.map((entry) => (entry.id === item.id ? automation : entry)),
      );
    } catch (e) {
      setActionError(friendlyError(e instanceof Error ? e.message : String(e)));
    } finally {
      setPendingId(null);
    }
  };

  const onDelete = async () => {
    if (!deleteTarget || pendingId) {
      return;
    }
    setPendingId(deleteTarget.id);
    setActionError(null);
    try {
      await deletePicoAutomation(deleteTarget.id);
      setList((current) => current.filter((item) => item.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (e) {
      setActionError(friendlyError(e instanceof Error ? e.message : String(e)));
    } finally {
      setPendingId(null);
    }
  };

  if (mode === 'create') {
    return (
      <div className="flex h-full min-h-0 flex-col bg-[#f5f5f5] text-[#1a1a1a] dark:bg-presentation dark:text-text-primary">
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-black/[0.06] bg-white px-4 dark:border-border-light dark:bg-surface-primary">
          <div className="flex min-w-0 items-center gap-2 text-[14px] font-medium">
            <button
              type="button"
              className="rounded-md p-1 hover:bg-black/[0.04]"
              onClick={closeCreate}
              aria-label="返回自动化列表"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <span className="truncate">自动化 / 添加任务</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded-md px-3 py-1.5 text-[13px] text-[#6b6b6b] hover:bg-black/[0.04]"
              onClick={closeCreate}
            >
              取消
            </button>
            <button
              type="button"
              className="inline-flex min-w-[72px] items-center justify-center gap-1.5 rounded-md bg-[#1a1a1a] px-3 py-1.5 text-[13px] font-medium text-white disabled:opacity-40"
              disabled={!name.trim() || !prompt.trim() || saving}
              onClick={() => void onSave()}
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
              {saving ? '保存中' : '保存'}
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto grid w-full max-w-5xl gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_280px]">
            <main className="min-w-0 overflow-hidden rounded-lg border border-black/[0.06] bg-white dark:border-border-light dark:bg-surface-primary">
              {actionError ? (
                <div
                  role="alert"
                  className="flex items-start gap-2 border-b border-red-100 bg-red-50 px-4 py-2.5 text-[12.5px] text-red-700"
                >
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  {actionError}
                </div>
              ) : null}

              <section className="border-b border-black/[0.05] p-4">
                <h2 className="text-[13px] font-semibold">任务内容</h2>
                <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_190px]">
                  <label className="block">
                    <span className="mb-1 block text-[12px] text-[#6b6b6b]">名称</span>
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="h-9 w-full rounded-md border border-black/[0.1] bg-white px-3 text-[13px] outline-none focus:border-black/30 dark:bg-surface-secondary"
                      placeholder="例如：生成昨日 AI 资讯总结"
                      maxLength={256}
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-[12px] text-[#6b6b6b]">模型偏好</span>
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      className="h-9 w-full rounded-md border border-black/[0.1] bg-white px-2.5 text-[13px] outline-none dark:bg-surface-secondary"
                    >
                      {MODELS.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="mt-3 block">
                  <span className="mb-1 block text-[12px] text-[#6b6b6b]">提示词</span>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    rows={6}
                    className="w-full resize-y rounded-md border border-black/[0.1] bg-white px-3 py-2 text-[13px] leading-5 outline-none focus:border-black/30 dark:bg-surface-secondary"
                    placeholder="描述触发后要执行的任务、输入范围和期望产物"
                  />
                </label>
              </section>

              <section className="border-b border-black/[0.05] p-4">
                <div className="flex items-center gap-2">
                  <Clock3 className="h-4 w-4 text-[#6b6b6b]" />
                  <h2 className="text-[13px] font-semibold">执行频率</h2>
                </div>
                <div className="mt-3 inline-flex rounded-md bg-[#f2f2f2] p-0.5">
                  {(
                    [
                      ['periodic', '每天'],
                      ['interval', '按间隔'],
                      ['once', '单次'],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setScheduleKind(id)}
                      className={cn(
                        'h-7 rounded px-3 text-[12.5px]',
                        scheduleKind === id
                          ? 'bg-white font-medium text-[#1a1a1a] shadow-sm'
                          : 'text-[#6b6b6b]',
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <div className="mt-3 flex min-h-9 items-center">
                  {scheduleKind === 'periodic' && (
                    <label className="flex items-center gap-2 text-[12.5px]">
                      <span className="text-[#6b6b6b]">每天</span>
                      <input
                        aria-label="每天执行时间"
                        type="time"
                        value={time}
                        onChange={(e) => setTime(e.target.value)}
                        className="h-9 rounded-md border border-black/[0.1] bg-white px-2.5 outline-none"
                      />
                      <span className="text-[#8c8c8c]">按浏览器本地时区配置</span>
                    </label>
                  )}
                  {scheduleKind === 'interval' && (
                    <label className="flex items-center gap-2 text-[12.5px]">
                      <span className="text-[#6b6b6b]">每隔</span>
                      <input
                        aria-label="执行间隔分钟"
                        type="number"
                        min={1}
                        max={10080}
                        value={intervalMin}
                        onChange={(e) =>
                          setIntervalMin(Math.min(10080, Math.max(1, Number(e.target.value) || 60)))
                        }
                        className="h-9 w-24 rounded-md border border-black/[0.1] bg-white px-2.5 outline-none"
                      />
                      <span className="text-[#6b6b6b]">分钟</span>
                    </label>
                  )}
                  {scheduleKind === 'once' && (
                    <label className="flex flex-wrap items-center gap-2 text-[12.5px]">
                      <span className="text-[#6b6b6b]">触发时间</span>
                      <input
                        aria-label="单次触发时间"
                        type="datetime-local"
                        value={onceLocal}
                        onChange={(e) => setOnceLocal(e.target.value)}
                        className="h-9 rounded-md border border-black/[0.1] bg-white px-2.5 outline-none"
                      />
                      <span className="text-[#8c8c8c]">执行后自动停用</span>
                    </label>
                  )}
                </div>
              </section>

              <section className="border-b border-black/[0.05] p-4">
                <div className="flex items-center gap-2">
                  <FolderKanban className="h-4 w-4 text-[#6b6b6b]" />
                  <h2 className="text-[13px] font-semibold">工作空间</h2>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  {WORKSPACES.map((workspace) => (
                    <button
                      key={workspace.id}
                      type="button"
                      onClick={() => setWorkspaceId(workspace.id)}
                      className={cn(
                        'min-h-14 rounded-md border px-3 py-2 text-left',
                        workspaceId === workspace.id
                          ? 'border-[#1a1a1a] bg-[#fafafa]'
                          : 'border-black/[0.08] hover:bg-[#fafafa]',
                      )}
                    >
                      <span className="block text-[12.5px] font-medium">{workspace.label}</span>
                      <span className="mt-0.5 block text-[11px] text-[#8c8c8c]">
                        {workspace.supported ? '当前执行空间' : '仅保存选择'}
                      </span>
                    </button>
                  ))}
                </div>
              </section>

              <section className="border-b border-black/[0.05] p-4">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-[#6b6b6b]" />
                  <h2 className="text-[13px] font-semibold">权限</h2>
                </div>
                <div className="mt-3 divide-y divide-black/[0.05] rounded-md border border-black/[0.08]">
                  {PERMISSIONS.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setPermission(item.id)}
                      className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-[#fafafa]"
                    >
                      <span
                        className={cn(
                          'flex size-4 shrink-0 items-center justify-center rounded-full border',
                          permission === item.id ? 'border-[#1a1a1a]' : 'border-black/20',
                        )}
                      >
                        {permission === item.id ? (
                          <span className="size-2 rounded-full bg-[#1a1a1a]" />
                        ) : null}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[12.5px] font-medium">{item.label}</span>
                        <span className="block text-[11px] text-[#8c8c8c]">{item.detail}</span>
                      </span>
                      {!item.supported ? (
                        <span className="rounded bg-[#f2f2f2] px-1.5 py-0.5 text-[10px] text-[#7a7a7a]">
                          元数据
                        </span>
                      ) : null}
                    </button>
                  ))}
                </div>
              </section>

              <section className="p-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-[#6b6b6b]" />
                  <h2 className="text-[13px] font-semibold">技能 / 专家</h2>
                </div>
                <label className="mt-3 block">
                  <span className="mb-1 block text-[12px] text-[#6b6b6b]">绑定偏好</span>
                  <select
                    value={bindingId}
                    onChange={(e) => setBindingId(e.target.value)}
                    className="h-9 w-full rounded-md border border-black/[0.1] bg-white px-2.5 text-[13px] outline-none dark:bg-surface-secondary"
                  >
                    {BINDINGS.map((binding) => (
                      <option key={binding.id} value={binding.id}>
                        {binding.label}
                      </option>
                    ))}
                  </select>
                  <span className="mt-1 block text-[11px] text-[#8c8c8c]">
                    {selectedBinding.detail}；服务端暂未自动注入对应技能或专家。
                  </span>
                </label>
              </section>
            </main>

            <aside className="h-fit overflow-hidden rounded-lg border border-black/[0.06] bg-white dark:border-border-light dark:bg-surface-primary lg:sticky lg:top-4">
              <div className="border-b border-black/[0.05] px-4 py-3">
                <h2 className="text-[13px] font-semibold">执行摘要</h2>
              </div>
              <dl className="divide-y divide-black/[0.05] px-4">
                {[
                  ['模型偏好', model],
                  ['频率', scheduleKind === 'periodic' ? `每天 ${time}` : scheduleKind === 'interval' ? `每 ${intervalMin} 分钟` : '单次执行'],
                  ['工作空间', selectedWorkspace.label],
                  ['权限', selectedPermission.label],
                  ['能力', selectedBinding.label],
                ].map(([label, value]) => (
                  <div key={label} className="grid grid-cols-[72px_minmax(0,1fr)] gap-2 py-2.5">
                    <dt className="text-[11.5px] text-[#8c8c8c]">{label}</dt>
                    <dd className="break-words text-right text-[12px] text-[#3d3d3d]">{value}</dd>
                  </div>
                ))}
              </dl>
              <div className="flex items-center justify-between border-t border-black/[0.05] px-4 py-3">
                <div>
                  <p className="text-[12.5px] font-medium">创建后启用</p>
                  <p className="text-[10.5px] text-[#8c8c8c]">关闭时会在创建后调用停用接口</p>
                </div>
                <Toggle
                  checked={createEnabled}
                  label="创建后启用"
                  onChange={() => setCreateEnabled((current) => !current)}
                />
              </div>
              <div className="border-t border-amber-100 bg-amber-50 px-4 py-3 text-[11px] leading-4 text-amber-900">
                调度频率与启用状态由服务端真实执行。工作空间、权限、技能/专家保存在
                schedule.pico_ui，当前仅作兼容元数据，不代表服务端已应用这些绑定。
              </div>
            </aside>
          </div>
        </div>
      </div>
    );
  }

  const enabledCount = list.filter((item) => item.enabled).length;

  return (
    <div className="flex h-full min-h-0 flex-col bg-[#f5f5f5] dark:bg-presentation">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-black/[0.06] bg-white px-4 dark:border-border-light dark:bg-surface-primary">
        <div className="min-w-0">
          <h1 className="text-[15px] font-semibold text-[#1a1a1a] dark:text-text-primary">自动化</h1>
        </div>
        <button
          type="button"
          onClick={() => {
            setActionError(null);
            setMode('create');
          }}
          className="inline-flex items-center gap-1.5 rounded-md bg-[#1a1a1a] px-3 py-1.5 text-[13px] font-medium text-white"
        >
          <Plus className="h-3.5 w-3.5" />
          添加任务
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-5xl px-4 py-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-[12px] text-[#6b6b6b]">
            <div className="flex items-center gap-3">
              <span>全部 {list.length}</span>
              <span className="h-3 w-px bg-black/10" />
              <span>运行中 {enabledCount}</span>
              <span className="h-3 w-px bg-black/10" />
              <span>已停用 {list.length - enabledCount}</span>
            </div>
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 hover:bg-black/[0.04] disabled:opacity-50"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
              刷新
            </button>
          </div>

          {error || actionError ? (
            <div
              role="alert"
              className="mb-3 flex items-start justify-between gap-3 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-[12.5px] text-red-700"
            >
              <span className="flex items-start gap-2">
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {actionError || error}
              </span>
              <button
                type="button"
                onClick={() => {
                  setActionError(null);
                  void refresh();
                }}
                className="shrink-0 font-medium underline"
              >
                重试
              </button>
            </div>
          ) : null}

          <div className="overflow-hidden rounded-lg border border-black/[0.06] bg-white dark:border-border-light dark:bg-surface-primary">
            <div className="hidden grid-cols-[minmax(0,1fr)_150px_170px_104px] gap-3 border-b border-black/[0.05] bg-[#fafafa] px-4 py-2 text-[11px] text-[#8c8c8c] md:grid">
              <span>任务</span>
              <span>执行频率</span>
              <span>运行记录</span>
              <span className="text-right">状态与操作</span>
            </div>

            {loading && list.length === 0 ? (
              <div className="flex items-center justify-center gap-2 py-20 text-[13px] text-[#8c8c8c]">
                <Loader2 className="h-4 w-4 animate-spin" />
                加载中
              </div>
            ) : null}

            {!loading && list.length === 0 ? (
              <div className="flex flex-col items-center px-4 py-16 text-center">
                <div className="flex size-10 items-center justify-center rounded-md bg-[#f2f2f2]">
                  <Clock3 className="h-5 w-5 text-[#6b6b6b]" />
                </div>
                <p className="mt-3 text-[14px] font-medium text-[#1a1a1a] dark:text-text-primary">
                  暂无自动化任务
                </p>
                <p className="mt-1 max-w-sm text-[12.5px] leading-5 text-[#8c8c8c]">
                  配置提示词与频率后，Pico 会在服务端按时创建并执行任务。
                </p>
                <button
                  type="button"
                  onClick={() => setMode('create')}
                  className="mt-4 rounded-md bg-[#1a1a1a] px-3 py-1.5 text-[12.5px] text-white"
                >
                  添加任务
                </button>
                <Link to="/c/new" className="mt-3 text-[11.5px] text-[#8c8c8c] underline">
                  返回新建任务
                </Link>
              </div>
            ) : null}

            {list.length > 0 ? (
              <ul className="divide-y divide-black/[0.05]">
                {list.map((item) => {
                  const meta = readUiMeta(item);
                  const itemModel = meta?.model || asString(item.schedule?.model, 'Auto');
                  return (
                    <li
                      key={item.id}
                      className="grid gap-3 px-4 py-3 hover:bg-[#fcfcfc] md:grid-cols-[minmax(0,1fr)_150px_170px_104px]"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className={cn(
                              'size-2 shrink-0 rounded-full',
                              item.enabled ? 'bg-emerald-500' : 'bg-[#c7c7c7]',
                            )}
                          />
                          <p className="truncate text-[13.5px] font-medium text-[#1a1a1a] dark:text-text-primary">
                            {item.name}
                          </p>
                        </div>
                        <p className="mt-1 line-clamp-2 pl-4 text-[12px] leading-[18px] text-[#6b6b6b]">
                          {promptWithoutModelPrefix(item.prompt)}
                        </p>
                        <div className="mt-1.5 flex flex-wrap gap-1.5 pl-4 text-[10.5px] text-[#6b6b6b]">
                          <span className="inline-flex items-center gap-1 rounded bg-[#f2f2f2] px-1.5 py-0.5">
                            <Bot className="h-3 w-3" />
                            {itemModel}
                          </span>
                          <span className="rounded bg-[#f2f2f2] px-1.5 py-0.5">
                            {meta?.workspace.label || '账号默认工作空间'}
                          </span>
                          {meta?.binding.kind && meta.binding.kind !== 'none' ? (
                            <span className="rounded bg-[#f2f2f2] px-1.5 py-0.5">
                              {meta.binding.label}
                            </span>
                          ) : null}
                        </div>
                      </div>

                      <div className="text-[12px] md:pt-0.5">
                        <span className="mr-2 text-[#8c8c8c] md:hidden">频率</span>
                        <span className="text-[#3d3d3d]">{scheduleLabel(item)}</span>
                      </div>

                      <div className="space-y-1 text-[11px] text-[#8c8c8c] md:pt-0.5">
                        <p>上次 {formatDate(item.last_run_at)}</p>
                        <p>下次 {formatDate(item.next_run_at)}</p>
                      </div>

                      <div className="flex items-center justify-between gap-2 md:justify-end">
                        <div className="flex items-center gap-2">
                          {pendingId === item.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-[#8c8c8c]" />
                          ) : (
                            <Toggle
                              checked={item.enabled}
                              disabled={pendingId !== null}
                              label={`${item.enabled ? '停用' : '启用'} ${item.name}`}
                              onChange={() => void onToggle(item)}
                            />
                          )}
                          <span className="w-9 text-[10.5px] text-[#8c8c8c]">
                            {item.enabled ? '已启用' : '已停用'}
                          </span>
                        </div>
                        <button
                          type="button"
                          aria-label={`删除 ${item.name}`}
                          title="删除"
                          disabled={pendingId !== null}
                          onClick={() => {
                            setActionError(null);
                            setDeleteTarget(item);
                          }}
                          className="rounded p-1.5 text-[#8c8c8c] hover:bg-red-50 hover:text-red-600 disabled:opacity-40"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </div>
        </div>
      </div>

      {deleteTarget ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target && pendingId !== deleteTarget.id) {
              setDeleteTarget(null);
            }
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="automation-delete-title"
            className="w-full max-w-sm rounded-lg border border-black/[0.08] bg-white p-4 shadow-xl"
          >
            <h2 id="automation-delete-title" className="text-[14px] font-semibold">
              删除自动化任务？
            </h2>
            <p className="mt-2 text-[12.5px] leading-5 text-[#6b6b6b]">
              “{deleteTarget.name}”将被永久删除，已有任务与运行记录不会随之删除。
            </p>
            {actionError ? (
              <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-[12px] text-red-700">
                {actionError}
              </p>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                disabled={pendingId === deleteTarget.id}
                onClick={() => setDeleteTarget(null)}
                className="rounded-md px-3 py-1.5 text-[12.5px] text-[#6b6b6b] hover:bg-black/[0.04] disabled:opacity-50"
              >
                取消
              </button>
              <button
                type="button"
                disabled={pendingId === deleteTarget.id}
                onClick={() => void onDelete()}
                className="inline-flex min-w-[76px] items-center justify-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-[12.5px] font-medium text-white disabled:opacity-60"
              >
                {pendingId === deleteTarget.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
                确认删除
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
