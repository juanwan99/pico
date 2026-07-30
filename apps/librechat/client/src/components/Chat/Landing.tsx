/**
 * Pico home — pixel layout aligned to WorkBuddy reference (clean-room).
 * Owns hero + scene chips + primary composer chrome on landing.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  FileText,
  Landmark,
  LineChart,
  Search,
  Clapperboard,
  Presentation,
  Sparkles,
  Plus,
  Mic,
  ArrowUp,
  ChevronDown,
  type LucideIcon,
} from 'lucide-react';
import { useOptionalChatFormContext } from '~/Providers';
import { useAuthContext } from '~/hooks';
import useSubmitMessage from '~/hooks/Messages/useSubmitMessage';
import WorkspaceSelector from '~/components/Chat/Input/WorkspaceSelector';
import { cn } from '~/utils';
import { consumePendingModel, getPicoModelMode, setPicoModelMode } from '~/utils/picoModelPref';

type SceneId = 'office' | 'code' | 'design';

type Chip = {
  id: string;
  label: string;
  icon: LucideIcon;
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
    icon: FileText,
    prompt: '请帮我整理并润色这份材料，输出结构清晰、可直接交付的文档。',
    scenes: ['office', 'code', 'design'],
  },
  {
    id: 'finance',
    label: '金融服务',
    icon: Landmark,
    prompt: '请根据我提供的财务或经营数据，给出分析结论与可执行建议。',
    scenes: ['office'],
  },
  {
    id: 'data',
    label: '数据分析及可视化',
    icon: LineChart,
    prompt: '请对数据做分析，并用表格/图表建议说明关键结论。',
    scenes: ['office', 'code'],
  },
  {
    id: 'research',
    label: '深度研究',
    icon: Search,
    prompt: '请围绕主题做结构化深度研究：背景、要点、对比、风险与行动建议。',
    scenes: ['office', 'code', 'design'],
  },
  {
    id: 'video',
    label: '视频生成',
    icon: Clapperboard,
    prompt: '请为我规划一条视频脚本：分镜、旁白、节奏与交付清单。',
    scenes: ['design', 'office'],
  },
  {
    id: 'slides',
    label: '幻灯片',
    icon: Presentation,
    prompt: '请生成一份可直接做幻灯片的大纲：每页标题、要点与视觉建议。',
    scenes: ['office', 'design'],
  },
];

const PLACEHOLDER = '今天帮你做些什么？ @ 引用对话文件，/ 调用技能与指令';

export default function Landing({
  centerFormOnLanding: _c,
}: {
  centerFormOnLanding: boolean;
}) {
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
      return getPicoModelMode() || 'Auto';
    } catch {
      return 'Auto';
    }
  });
  const [expertBadge, setExpertBadge] = useState<string | null>(null);


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
        setModel(pendingModel);
      }
      const expert = sessionStorage.getItem('pico:pendingExpert');
      if (expert) {
        sessionStorage.removeItem('pico:pendingExpert');
        setExpertBadge(expert);
        fillPrompt(`请以「${expert}」的角色协助完成任务：`);
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
  }, [fillPrompt]);

  const name = user?.name?.split(/\s+/)[0] || '';

  return (
    <div className="pico-wb-landing flex w-full flex-col items-center px-6 pb-6 pt-14 sm:pt-20">
      <div className="flex w-full max-w-[797px] flex-col items-center">
        <h1 className="text-center text-[30px] font-semibold leading-none tracking-[-0.02em] text-[#1a1a1a] sm:text-[34px] dark:text-text-primary">
          Pico，我帮你
        </h1>
        {name ? (
          <p className="mt-2.5 text-[13px] text-[#8c8c8c]">{name}，描述任务即可开始</p>
        ) : null}
        {expertBadge ? (
          <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-[#edf1f4] px-3 py-1 text-[12px] font-medium text-[#3d3d3d]">
            专家 · {expertBadge}
            <span className="text-[#8c8c8c]">· 模型 {model}</span>
          </div>
        ) : null}

        {/* Scene pills */}
        <div className="mt-7 flex flex-wrap items-center justify-center gap-2" role="tablist">
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
                    ? 'bg-[#1a1a1a] font-medium text-white'
                    : 'bg-white text-[#4a4a4a] shadow-[0_0_0_1px_rgba(0,0,0,0.06)] hover:bg-[#fafafa]',
                )}
              >
                {s.id === 'office' ? <Sparkles className="h-3.5 w-3.5 opacity-90" /> : null}
                {s.label}
              </button>
            );
          })}
        </div>

        {/* Capability chips */}
        <div className="mt-5 flex w-full flex-wrap items-center justify-center gap-2">
          {visibleChips.map((chip) => {
            const Icon = chip.icon;
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => fillPrompt(chip.prompt)}
                className="inline-flex h-[32px] items-center gap-1.5 rounded-full bg-white px-3 text-[12.5px] text-[#3d3d3d] shadow-[0_0_0_1px_rgba(0,0,0,0.06)] hover:bg-[#fafafa]"
              >
                <Icon className="h-3.5 w-3.5 text-[#6b6b6b]" strokeWidth={1.75} />
                {chip.label}
              </button>
            );
          })}
        </div>

        {/* PIXEL composer card — matches reference input block */}
        <div className="mt-7 w-full max-w-[720px]">
          <div
            className="rounded-[20px] border border-black/[0.08] bg-white px-4 pb-3 pt-3.5 shadow-[0_8px_28px_rgba(15,23,42,0.07)]"
            data-testid="pico-wb-home-composer"
          >
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
              className="w-full resize-none border-0 bg-transparent text-[14px] leading-[1.55] text-[#1a1a1a] outline-none placeholder:text-[#a0a0a0]"
            />
            <div className="mt-1 flex items-center justify-between gap-2">
              <button
                type="button"
                className="flex h-8 w-8 items-center justify-center rounded-full text-[#6b6b6b] hover:bg-black/[0.04]"
                aria-label="添加"
                onClick={() =>
                  document.querySelector<HTMLButtonElement>('[data-testid="attach-file"]')?.click()
                }
              >
                <Plus className="h-5 w-5" strokeWidth={1.75} />
              </button>
              <div className="flex items-center gap-1.5">
                <div className="relative">
                  <button
                    type="button"
                    className="inline-flex h-8 items-center gap-1 rounded-full bg-[#f3f3f3] px-2.5 text-[12.5px] font-medium text-[#3d3d3d]"
                    onClick={() => setModelOpen((v) => !v)}
                  >
                    {model}
                    <ChevronDown className="h-3.5 w-3.5 opacity-60" />
                  </button>
                  {modelOpen && (
                    <div className="absolute bottom-full right-0 z-50 mb-2 w-52 overflow-hidden rounded-xl border border-black/[0.08] bg-white py-1 shadow-lg">
                      {['Auto', 'kimi-k2.6', 'Kimi-K3'].map((m) => (
                        <button
                          key={m}
                          type="button"
                          className="flex w-full px-3 py-2 text-left text-[13px] hover:bg-[#f5f5f5]"
                          onClick={() => {
                            setModel(m);
                            setModelOpen(false);
                            setPicoModelMode(m);
                          }}
                        >
                          {m}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className="flex h-8 w-8 items-center justify-center rounded-full text-[#6b6b6b] hover:bg-black/[0.04]"
                  aria-label="语音"
                >
                  <Mic className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  className={cn(
                    'flex h-8 w-8 items-center justify-center rounded-full transition-colors',
                    text.trim()
                      ? 'bg-[#1a1a1a] text-white'
                      : 'bg-[#e8e8e8] text-[#9a9a9a]',
                  )}
                  aria-label="发送"
                  disabled={!text.trim()}
                  onClick={() => sendTask()}
                >
                  <ArrowUp className="h-4 w-4" strokeWidth={2.25} />
                </button>
              </div>
            </div>
          </div>

          {/* Under-card: 选择工作空间 + 默认权限 */}
          <div className="mt-2.5 flex flex-wrap items-center gap-1">
            <WorkspaceSelector />
            <div className="relative">
              <button
                type="button"
                className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2 text-[12.5px] font-medium text-[#6b6b6b] hover:bg-black/[0.04]"
                onClick={() => setPermOpen((v) => !v)}
              >
                <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-current text-[9px] opacity-70">
                  ✓
                </span>
                {fullAccess ? '完全访问' : '默认权限'}
              </button>
              {permOpen && (
                <div className="absolute bottom-full left-0 z-50 mb-2 w-72 rounded-xl border border-black/[0.08] bg-white p-3 shadow-lg">
                  <p className="text-[12.5px] leading-relaxed text-[#4a4a4a]">
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
  );
}
