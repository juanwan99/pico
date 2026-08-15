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

const PLACEHOLDER = '今天帮你做些什么？';

export default function Landing({ centerFormOnLanding: _c }: { centerFormOnLanding: boolean }) {
  const { user } = useAuthContext();
  const form = useOptionalChatFormContext();
  const { submitMessage } = useSubmitMessage();
  const [scene, setScene] = useState<SceneId>('office');
  const [text, setText] = useState('');
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
    <div className="pico-wb-landing pico-shell-bg flex min-h-full w-full flex-col items-center px-4 pb-8 pt-10 sm:px-6 sm:pt-[132px]">
      <div className="flex w-full max-w-[797px] flex-col items-center">
        <h1 className="pico-type-medium text-center text-[30px] leading-none tracking-normal text-[color:var(--pico-ink)] dark:text-text-primary sm:text-[34px]">
          Pico，我帮你
        </h1>
        {name ? (
          <p className="pico-type-sidebar mt-2.5 text-[color:var(--pico-ink-3)]">
            {name}，描述任务即可开始
          </p>
        ) : null}
        {expertBadge || connectorBadge || skillBadge ? (
          <div className="mt-2 flex flex-wrap items-center justify-center gap-1.5">
            {skillBadge ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[color:var(--pico-surface-2)] px-3 py-1 text-[12px] font-medium text-[color:var(--pico-ink)]">
                <PicoIcon name="doc" size="sm" />
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
        <div
          className="mt-7 flex max-w-full flex-wrap items-center justify-center gap-2"
          role="tablist"
        >
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
                  active ? 'pico-chip-active font-medium' : 'pico-chip',
                )}
              >
                {s.id === 'office' ? (
                  <PicoIcon name="spark" size="sm" className="opacity-90" />
                ) : null}
                {s.label}
              </button>
            );
          })}
        </div>

        {/* Capability chips */}
        <div className="mt-3.5 flex w-full flex-wrap items-center justify-center gap-2">
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

        {/* One-row composer: + · input · send arrow */}
        <div className="mt-6 w-full max-w-[797px]">
          <div
            className="pico-wb-composer rounded-[var(--pico-radius)] border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] shadow-[var(--pico-shadow)]"
            data-testid="pico-wb-home-composer"
          >
            <div
              className="pico-wb-composer-row relative flex items-end gap-0.5 px-1 py-1"
              data-testid="composer-one-row"
            >
              <div className="relative shrink-0 self-end">
                <button
                  type="button"
                  data-testid="composer-plus"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[color:var(--pico-ink-2)] hover:bg-black/[0.04]"
                  aria-label="更多输入选项"
                  aria-expanded={modelOpen}
                  onClick={() => {
                    setModelOpen((v) => !v);
                  }}
                >
                  <PicoIcon name="plus" className="text-[color:var(--pico-ink-2)]" />
                </button>
                {modelOpen ? (
                  <div
                    data-testid="composer-plus-menu"
                    className="pico-card absolute bottom-full left-0 z-50 mb-2 w-56 overflow-hidden py-1 shadow-[var(--pico-shadow-raised)]"
                  >
                    {PICO_DUAL_MODELS.map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        className="pico-type-sidebar flex w-full px-3 py-2 text-left hover:bg-[color:var(--pico-surface-2)]"
                        onClick={() => applyModel(m.id)}
                      >
                        {m.label}
                      </button>
                    ))}
                    <div className="border-t border-[color:var(--pico-line)] px-3 py-2">
                      <WorkspaceSelector />
                    </div>
                    <button
                      type="button"
                      className="pico-type-sidebar flex w-full px-3 py-2 text-left hover:bg-[color:var(--pico-surface-2)]"
                      onClick={() => {
                        setFullAccess((v) => !v);
                        try {
                          localStorage.setItem(
                            'pico:permissionMode',
                            !fullAccess ? 'full' : 'default',
                          );
                        } catch {
                          /* ignore */
                        }
                      }}
                    >
                      {fullAccess ? '完全访问' : '默认权限'}
                    </button>
                  </div>
                ) : null}
              </div>
              <textarea
                id="pico-wb-home-input"
                data-testid="text-input"
                value={text}
                onChange={(e) => syncForm(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendTask();
                  }
                }}
                placeholder={PLACEHOLDER}
                rows={1}
                className="pico-type-body min-h-8 min-w-0 flex-1 resize-none border-0 bg-transparent py-2 leading-[1.55] text-[color:var(--pico-ink)] outline-none placeholder:text-[color:var(--pico-ink-3)]"
              />
              <button
                type="button"
                data-testid="send-button"
                className={cn(
                  'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md self-end transition-colors',
                  text.trim()
                    ? 'text-[color:var(--pico-ink)] hover:bg-black/[0.04]'
                    : 'text-[color:var(--pico-ink-3)]',
                )}
                aria-label="发送"
                disabled={!text.trim()}
                onClick={() => sendTask()}
              >
                <PicoIcon name="arrow-up" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
