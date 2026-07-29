/**
 * Pico home — pixel-aligned WorkBuddy task home (clean-room layout).
 */
import { useCallback, useMemo, useState } from 'react';
import {
  FileText,
  Landmark,
  LineChart,
  Search,
  Clapperboard,
  Presentation,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';
import { useOptionalChatFormContext } from '~/Providers';
import { useLocalize, useAuthContext } from '~/hooks';
import { cn } from '~/utils';

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

export default function Landing({ centerFormOnLanding: _centerFormOnLanding }: { centerFormOnLanding: boolean }) {
  const { user } = useAuthContext();
  const localize = useLocalize();
  const form = useOptionalChatFormContext();
  const [scene, setScene] = useState<SceneId>('office');

  const visibleChips = useMemo(() => CHIPS.filter((c) => c.scenes.includes(scene)), [scene]);

  const fillPrompt = useCallback(
    (prompt: string) => {
      form?.setValue('text', prompt, { shouldDirty: true, shouldTouch: true });
      requestAnimationFrame(() => {
        const el = document.querySelector<HTMLTextAreaElement>(
          'textarea[data-testid="text-input"]',
        );
        if (!el) {
          return;
        }
        const native = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype,
          'value',
        )?.set;
        native?.call(el, prompt);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.focus();
        el.selectionStart = el.value.length;
        el.selectionEnd = el.value.length;
      });
    },
    [form],
  );

  const name = user?.name?.split(' ')[0] || user?.username || '';

  return (
    <div className="pico-wb-landing pointer-events-auto flex w-full flex-shrink-0 flex-col items-center px-4 pt-8 sm:pt-14">
      <div className="flex w-full max-w-[720px] flex-col items-center">
        {/* Title — WorkBuddy-scale hero */}
        <h1 className="text-center text-[32px] font-semibold leading-tight tracking-[-0.02em] text-[#1a1a1a] sm:text-[36px] dark:text-text-primary">
          Pico，我帮你
        </h1>
        {name ? (
          <p className="mt-2 text-center text-[13px] text-[#8c8c8c]">
            {name}，描述任务即可开始
          </p>
        ) : null}

        {/* Scene pills */}
        <div
          className="mt-6 flex flex-wrap items-center justify-center gap-2"
          role="tablist"
          aria-label="场景"
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
                  'inline-flex h-8 items-center gap-1.5 rounded-full px-3.5 text-[13px] transition-colors',
                  active
                    ? 'bg-[#1a1a1a] font-medium text-white'
                    : 'bg-white font-normal text-[#4a4a4a] ring-1 ring-black/[0.06] hover:bg-[#fafafa]',
                )}
              >
                {s.id === 'office' && <Sparkles className="h-3.5 w-3.5 opacity-80" />}
                {s.label}
              </button>
            );
          })}
        </div>

        {/* Capability chips — single row wrap like reference */}
        <div className="mt-5 flex w-full max-w-[680px] flex-wrap items-center justify-center gap-2">
          {visibleChips.map((chip) => {
            const Icon = chip.icon;
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => fillPrompt(chip.prompt)}
                className="inline-flex h-8 items-center gap-1.5 rounded-full bg-white px-3 text-[12.5px] text-[#3d3d3d] ring-1 ring-black/[0.06] transition hover:bg-[#fafafa] hover:ring-black/10"
              >
                <Icon className="h-3.5 w-3.5 shrink-0 text-[#6b6b6b]" strokeWidth={1.75} />
                {chip.label}
              </button>
            );
          })}
        </div>

        <p className="mt-3 text-[11px] text-[#b0b0b0]">{localize('com_ui_task_chip_hint')}</p>
      </div>
    </div>
  );
}
