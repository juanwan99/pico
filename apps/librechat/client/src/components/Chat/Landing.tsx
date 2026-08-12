/**
 * Pico home — pixel layout aligned to WorkBuddy reference (clean-room).
 * Owns hero + scene chips + primary composer chrome on landing.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { PicoIcon, type PicoIconName } from '~/components/ui/pico-icons';
import { useOptionalChatFormContext } from '~/Providers';
import { useAuthContext } from '~/hooks';
import useSubmitMessage from '~/hooks/Messages/useSubmitMessage';
import WorkspaceSelector from '~/components/Chat/Input/WorkspaceSelector';
import { cn } from '~/utils';
import {
  consumePendingModel,
  getPicoModelMode,
  labelForPicoModel,
  normalizePicoModelMode,
  PICO_DUAL_MODELS,
  setPicoModelMode,
} from '~/utils/picoModelPref';
import { useOptionalChatContext } from '~/Providers';

type SceneId = 'office' | 'code' | 'design';

type Chip = {
  id: string;
  label: string;
  icon: PicoIconName;
  prompt: string;
  scenes: SceneId[];
};

const SCENES: { id: SceneId; label: string }[] = [
  { id: 'office', label: '日常办公' },
  { id: 'code', label: '代码开发' },
  { id: 'design', label: '设计创意' },
];

const CHIPS: Chip[] = [
  {
    id: 'doc',
    label: '文档处理',
    icon: 'doc',
    prompt: '请帮我整理并润色这份材料，输出结构清晰、可直接交付的文档。',
    scenes: ['office', 'code', 'design'],
  },
  {
    id: 'finance',
    label: '金融服务',
    icon: 'chart',
    prompt: '请根据我提供的财务或经营数据，给出分析结论与可执行建议。',
    scenes: ['office'],
  },
  {
    id: 'data',
    label: '数据分析及可视化',
    icon: 'chart',
    prompt: '请对数据做分析，并用表格/图表建议说明关键结论。',
    scenes: ['office', 'code'],
  },
  {
    id: 'research',
    label: '深度研究',
    icon: 'search',
    prompt: '请围绕主题做结构化深度研究：背景、要点、对比、风险与行动建议。',
    scenes: ['office', 'code', 'design'],
  },
  {
    id: 'video',
    label: '视频生成',
    icon: 'spark',
    prompt: '请为我规划一条视频脚本：分镜、旁白、节奏与交付清单。',
    scenes: ['design', 'office'],
  },
  {
    id: 'slides',
    label: '幻灯片',
    icon: 'grid',
    prompt: '请生成一份可直接做幻灯片的大纲：每页标题、要点与视觉建议。',
    scenes: ['office', 'design'],
  },
];

const PLACEHOLDER = '今天帮你做些什么？ @ 引用对话文件，/ 调用技能与指令';

export default function Landing({ centerFormOnLanding: _c }: { centerFormOnLanding: boolean }) {
  const { user } = useAuthContext();
  const form = useOptionalChatFormContext();
  const { submitMessage } = useSubmitMessage();
  const [scene, setScene] = useState<SceneId>('office');
  const [text, setText] = useState('');
  const [permOpen, setPermOpen] = useState(false);
  const [fullAccess, setFullAccess] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const [model, setModel] = useState(() => {
    try {
      return normalizePicoModelMode(getPicoModelMode());
    } catch {
      return 'pico-fast';
    }
  });
  const chatCtx = useOptionalChatContext();
  const applyModel = useCallback(
    (raw: string) => {
      const id = normalizePicoModelMode(raw);
      setModel(id);
      setPicoModelMode(id);
      setModelOpen(false);
      chatCtx?.setConversation?.((prev) =>
        prev
          ? {
              ...prev,
              endpoint: prev.endpoint ?? 'openAI',
              model: id,
            }
          : prev,
      );
    },
    [chatCtx],
  );
  const [expertBadge, setExpertBadge] = useState<string | null>(null);
  const [connectorBadge, setConnectorBadge] = useState<string | null>(null);
  const [skillBadge, setSkillBadge] = useState<string | null>(null);

  const visibleChips = useMemo(() => CHIPS.filter((c) => c.scenes.includes(scene)), [scene]);

  const syncForm = useCallback(
    (value: string) => {
      setText(value);
      form?.setValue('text', value, { shouldDirty: true, shouldTouch: true });
    },
    [form],
  );

  const fillPrompt = useCallback(
    (prompt: string) => {
      syncForm(prompt);
      requestAnimationFrame(() => {
        document.getElementById('pico-wb-home-input')?.focus();
      });
    },
    [syncForm],
  );

  const sendTask = useCallback(() => {
    const value = text.trim();
    if (!value) {
      return;
    }
    // Single submit path — no DOM bridge to hidden ChatForm
    submitMessage({ text: value });
    syncForm('');
  }, [text, submitMessage, syncForm]);

  // Expert / skill "summon" prefill from capability hub
  useEffect(() => {
    try {
      const pendingModel = consumePendingModel();
      if (pendingModel) {
        applyModel(pendingModel);
      }
      const expert = sessionStorage.getItem('pico:pendingExpert');
      if (expert) {
        sessionStorage.removeItem('pico:pendingExpert');
        setExpertBadge(expert);
      }
      const connector = sessionStorage.getItem('pico:pendingConnector');
      if (connector) {
        sessionStorage.removeItem('pico:pendingConnector');
        setConnectorBadge(connector);
      }
      const skill = sessionStorage.getItem('pico:pendingSkillLabel');
      if (skill) {
        sessionStorage.removeItem('pico:pendingSkillLabel');
        setSkillBadge(skill);
      }
      const pre = sessionStorage.getItem('pico:pendingPrompt');
      if (pre) {
        sessionStorage.removeItem('pico:pendingPrompt');
        fillPrompt(pre);
      }
      const active = sessionStorage.getItem('pico:activeExpert');
      if (active) {
        setExpertBadge(active);
      }
    } catch {
      /* ignore */
    }
  }, [applyModel, fillPrompt]);

  const name = user?.name?.split(/\s+/)[0] || '';

  return (
    <div className="pico-wb-landing flex w-full flex-col items-center px-6 pb-6 pt-10 sm:pt-[156px]">
      <div className="flex w-full max-w-[797px] flex-col items-center">
        <h1 className="text-center text-[30px] font-semibold leading-none tracking-normal text-[color:var(--pico-ink)] dark:text-text-primary sm:text-[34px]">
          Pico，我帮你
        </h1>
        {name ? (
          <p className="mt-2.5 text-[13px] text-[color:var(--pico-ink-3)]">{name}，描述任务即可开始</p>
        ) : null}
        {expertBadge || connectorBadge || skillBadge ? (
          <div className="mt-2 flex flex-wrap items-center justify-center gap-1.5">
            {skillBadge ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[color:var(--pico-surface-2)] px-3 py-1 text-[12px] font-medium text-[color:var(--pico-ink)]">
                <ScrollText className="h-3.5 w-3.5" />
                技能 · {skillBadge}
              </span>
            ) : null}
            {expertBadge ? (
              <span className="rounded-full bg-[color:var(--pico-surface-2)] px-3 py-1 text-[12px] font-medium text-[color:var(--pico-ink)]">
                专家 · {expertBadge}
              </span>
            ) : null}
            {connectorBadge ? (
              <span className="rounded-full bg-[color:var(--pico-surface-2)] px-3 py-1 text-[12px] font-medium text-[color:var(--pico-ink)]">
                连接器 · {connectorBadge}
              </span>
            ) : null}
            <span className="rounded-full bg-[color:var(--pico-surface-2)] px-3 py-1 text-[12px] text-[color:var(--pico-ink-3)]">
              模型 {labelForPicoModel(model)}
            </span>
          </div>
        ) : null}

        {/* Scene pills */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2" role="tablist">
          {SCENES.map((s) => {
            const active = scene === s.id;
            return (
              <button
                key={s.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setScene(s.id)}
                className={cn(
                  'inline-flex h-[32px] items-center gap-1.5 rounded-full px-3.5 text-[13px]',
                  active
                    ? 'pico-chip-active font-medium'
                    : 'pico-chip',
                )}
              >
                {s.id === 'office' ? <PicoIcon name="spark" size="sm" className="opacity-90" /> : null}
                {s.label}
              </button>
            );
          })}
        </div>

        {/* Capability chips */}
        <div className="mt-4 flex w-full flex-wrap items-center justify-center gap-2">
          {visibleChips.map((chip) => {
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => fillPrompt(chip.prompt)}
                className="pico-chip inline-flex h-[32px] items-center gap-1.5 px-3 text-[12.5px] text-[color:var(--pico-ink)]"
              >
                <PicoIcon name={chip.icon} size="sm" className="text-[color:var(--pico-ink-2)]" />
                {chip.label}
              </button>
            );
          })}
        </div>

        {/* PIXEL composer card — matches reference input block */}
        <div className="mt-5 w-full max-w-[797px]">
          <div
            className="rounded-[var(--pico-radius)] border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] shadow-[var(--pico-shadow)]"
            data-testid="pico-wb-home-composer"
          >
            <div className="min-h-[138px] px-4 pb-3 pt-3.5">
              <textarea
                id="pico-wb-home-input"
                value={text}
                onChange={(e) => syncForm(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendTask();
                  }
                }}
                placeholder={PLACEHOLDER}
                rows={3}
                className="w-full resize-none border-0 bg-transparent text-[14px] leading-[1.55] text-[color:var(--pico-ink)] outline-none placeholder:text-[color:var(--pico-ink-3)]"
              />
              <div className="mt-1 flex items-center justify-between gap-2">
                <button
                  type="button"
                  className="flex h-8 w-8 items-center justify-center rounded-full text-[color:var(--pico-ink-2)] hover:bg-black/[0.04]"
                  aria-label="添加"
                  onClick={() =>
                    document
                      .querySelector<HTMLButtonElement>('[data-testid="attach-file"]')
                      ?.click()
                  }
                >
                  <PicoIcon name="plus" className="text-[color:var(--pico-ink-2)]" />
                </button>
                <div className="flex items-center gap-1.5">
                  <div className="relative">
                    <button
                      type="button"
                      className="inline-flex h-8 items-center gap-1 rounded-full bg-[color:var(--pico-surface-2)] px-2.5 text-[12.5px] font-medium text-[color:var(--pico-ink)]"
                      onClick={() => setModelOpen((v) => !v)}
                    >
                      {labelForPicoModel(model)}
                      <PicoIcon name="chevron" size="sm" className="opacity-60" />
                    </button>
                    {modelOpen && (
                      <div className="absolute bottom-full right-0 z-50 mb-2 w-52 overflow-hidden rounded-xl border border-black/[0.08] bg-white py-1 shadow-lg">
                        {PICO_DUAL_MODELS.map((m) => (
                          <button
                            key={m.id}
                            type="button"
                            className="flex w-full px-3 py-2 text-left text-[13px] hover:bg-[color:var(--pico-surface-2)]"
                            onClick={() => applyModel(m.id)}
                          >
                            {m.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    className="flex h-8 w-8 items-center justify-center rounded-full text-[color:var(--pico-ink-2)] hover:bg-black/[0.04]"
                    aria-label="语音"
                  >
                    <PicoIcon name="mic" size="sm" />
                  </button>
                  <button
                    type="button"
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-full transition-colors',
                      text.trim() ? 'pico-cta-accent' : 'bg-[color:var(--pico-line)] text-[color:var(--pico-ink-3)]',
                    )}
                    aria-label="发送"
                    disabled={!text.trim()}
                    onClick={() => sendTask()}
                  >
                    <PicoIcon name="arrow" size="sm" />
                  </button>
                </div>
              </div>
            </div>

            <div className="flex min-h-10 flex-wrap items-center gap-1 border-t border-[color:var(--pico-line)] px-3">
              <WorkspaceSelector />
              <div className="relative">
                <button
                  type="button"
                  className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2 text-[12.5px] font-medium text-[color:var(--pico-ink-2)] hover:bg-black/[0.04]"
                  onClick={() => setPermOpen((v) => !v)}
                >
                  <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-current text-[9px] opacity-70">
                    ✓
                  </span>
                  {fullAccess ? '完全访问' : '默认权限'}
                </button>
                {permOpen && (
                  <div className="absolute bottom-full left-0 z-50 mb-2 w-72 rounded-xl border border-black/[0.08] bg-white p-3 shadow-lg">
                    <p className="text-[12.5px] leading-relaxed text-[color:var(--pico-ink-2)]">
                      当前为默认权限，所有操作都会在安全沙箱约束内进行，超出范围会请求你的允许。
                    </p>
                    <label className="mt-3 flex items-center justify-between gap-2 text-[13px]">
                      <span>允许完全访问</span>
                      <input
                        type="checkbox"
                        checked={fullAccess}
                        onChange={(e) => {
                          setFullAccess(e.target.checked);
                          try {
                            localStorage.setItem(
                              'pico:permissionMode',
                              e.target.checked ? 'full' : 'default',
                            );
                          } catch {}
                        }}
                      />
                    </label>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
