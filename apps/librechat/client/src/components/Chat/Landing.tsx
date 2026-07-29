/**
 * Pico task-workbench landing (WorkBuddy-class IA, clean-room UI).
 * Not a clone of any proprietary skin — functional layout only.
 */
import { useCallback, useMemo, useState } from 'react';
import {
  FileText,
  LineChart,
  Presentation,
  Search,
  Code2,
  GraduationCap,
  Sparkles,
  BookOpen,
  ClipboardList,
  type LucideIcon,
} from 'lucide-react';
import { EModelEndpoint } from 'librechat-data-provider';
import {
  useChatContext,
  useAgentsMapContext,
  useAssistantsMapContext,
  useOptionalChatFormContext,
} from '~/Providers';
import { useGetEndpointsQuery, useGetStartupConfig } from '~/data-provider';
import { getEntity, getIconEndpoint, getModelSpec, cn } from '~/utils';
import ConvoIcon from '~/components/Endpoints/ConvoIcon';
import AgentContact from '~/components/Agents/AgentContact';
import { useLocalize, useAuthContext } from '~/hooks';

type SceneId = 'office' | 'teach' | 'code';

type Chip = {
  id: string;
  label: string;
  icon: LucideIcon;
  prompt: string;
  scenes: SceneId[];
};

const SCENES: { id: SceneId; label: string }[] = [
  { id: 'office', label: '日常办公' },
  { id: 'teach', label: '教学教研' },
  { id: 'code', label: '代码开发' },
];

const CHIPS: Chip[] = [
  {
    id: 'doc',
    label: '文档处理',
    icon: FileText,
    prompt: '请帮我整理并润色这份材料，输出结构清晰的 Markdown 文档。',
    scenes: ['office', 'teach'],
  },
  {
    id: 'lesson',
    label: '教案设计',
    icon: BookOpen,
    prompt: '请根据主题设计一课时教案：目标、重难点、教学步骤、板书与作业。',
    scenes: ['teach'],
  },
  {
    id: 'grade',
    label: '学情分析',
    icon: LineChart,
    prompt: '请根据我提供的成绩或反馈，做学情分析并给出分层教学建议。',
    scenes: ['teach', 'office'],
  },
  {
    id: 'slides',
    label: '课件大纲',
    icon: Presentation,
    prompt: '请生成一份可直接做课件的大纲（分镜标题 + 要点 + 互动设计）。',
    scenes: ['teach', 'office'],
  },
  {
    id: 'research',
    label: '深度研究',
    icon: Search,
    prompt: '请围绕主题做结构化研究：背景、要点、对比、风险与行动建议。',
    scenes: ['office', 'teach', 'code'],
  },
  {
    id: 'code',
    label: '代码助手',
    icon: Code2,
    prompt: '请帮我分析需求并给出可运行的实现方案与关键代码。',
    scenes: ['code'],
  },
  {
    id: 'exam',
    label: '出题组卷',
    icon: ClipboardList,
    prompt: '请按知识点与难度出一套练习题，含参考答案与评分要点。',
    scenes: ['teach'],
  },
  {
    id: 'meeting',
    label: '会议纪要',
    icon: GraduationCap,
    prompt: '请把会议内容整理成纪要：决议、待办、责任人与时间点。',
    scenes: ['office'],
  },
];

const iconBubble =
  'shadow-stroke relative flex h-full items-center justify-center rounded-full bg-white text-black dark:bg-presentation dark:text-white dark:after:shadow-none';

export default function Landing({ centerFormOnLanding }: { centerFormOnLanding: boolean }) {
  const { conversation } = useChatContext();
  const agentsMap = useAgentsMapContext();
  const assistantMap = useAssistantsMapContext();
  const { data: startupConfig } = useGetStartupConfig();
  const { data: endpointsConfig } = useGetEndpointsQuery();
  const { user } = useAuthContext();
  const localize = useLocalize();
  const form = useOptionalChatFormContext();

  const [scene, setScene] = useState<SceneId>('office');

  const endpointType = useMemo(() => {
    let ep = conversation?.endpoint ?? '';
    if (ep === EModelEndpoint.azureOpenAI) {
      ep = EModelEndpoint.openAI;
    }
    return getIconEndpoint({
      endpointsConfig,
      iconURL: conversation?.iconURL,
      endpoint: ep,
    });
  }, [conversation?.endpoint, conversation?.iconURL, endpointsConfig]);

  const { entity, isAgent, isAssistant } = getEntity({
    endpoint: endpointType,
    agentsMap,
    assistantMap,
    agent_id: conversation?.agent_id,
    assistant_id: conversation?.assistant_id,
  });

  const modelSpec = useMemo(
    () => getModelSpec({ specName: conversation?.spec, startupConfig }),
    [conversation?.spec, startupConfig],
  );

  const agentName = entity?.name ?? (modelSpec?.showOnLanding ? modelSpec.label : '');
  const agentDescription =
    (entity?.description ||
      (modelSpec?.showOnLanding ? modelSpec.description : '') ||
      conversation?.greeting) ??
    '';
  const selectedAgent =
    isAgent && conversation?.agent_id != null ? agentsMap?.[conversation.agent_id] : undefined;

  const visibleChips = useMemo(() => CHIPS.filter((c) => c.scenes.includes(scene)), [scene]);

  const fillPrompt = useCallback(
    (prompt: string) => {
      form?.setValue('text', prompt, { shouldDirty: true, shouldTouch: true });
      requestAnimationFrame(() => {
        const el = document.querySelector<HTMLTextAreaElement>(
          '#prompt-textarea, textarea[data-testid="text-input"]',
        );
        el?.focus();
        if (el) {
          // keep RHF and DOM in sync if needed
          const native = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype,
            'value',
          )?.set;
          native?.call(el, prompt);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.selectionStart = el.value.length;
          el.selectionEnd = el.value.length;
        }
      });
    },
    [form],
  );

  if (((isAgent || isAssistant) && agentName) || agentName) {
    return (
      <div
        className={cn(
          'flex h-full transform-gpu flex-col items-center justify-center pb-10 transition-all duration-200',
          'max-h-full',
        )}
      >
        <div className="flex flex-col items-center gap-3 p-2">
          <div className="relative size-12">
            <ConvoIcon
              agentsMap={agentsMap}
              assistantMap={assistantMap}
              conversation={conversation}
              endpointsConfig={endpointsConfig}
              containerClassName={iconBubble}
              context="landing"
              className="h-2/3 w-2/3 text-black dark:text-white"
              size={48}
            />
          </div>
          <h1 className="text-center text-2xl font-semibold tracking-tight text-text-primary sm:text-3xl">
            {agentName}
          </h1>
          {agentDescription ? (
            <p className="max-w-md text-center text-sm text-text-secondary">{agentDescription}</p>
          ) : null}
          {selectedAgent ? (
            <AgentContact
              agent={selectedAgent}
              className="max-w-md justify-center text-center text-sm"
            />
          ) : null}
        </div>
      </div>
    );
  }

  const title = 'Pico，我帮你';
  const subtitle = user?.name
    ? `${user.name}，用一句话描述任务，我来规划并交付结果`
    : '用一句话描述任务，我来规划并交付结果';

  return (
    <div
      className={cn(
        'pico-wb-landing flex w-full transform-gpu flex-col items-center px-4 pb-6 pt-4 transition-all duration-200',
        'max-h-full flex-shrink-0 justify-center pb-2 pt-6 sm:pt-10',
      )}
    >
      <div className="flex w-full max-w-3xl flex-col items-center gap-5 xl:max-w-4xl">
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="mb-1 flex size-11 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-black/5 dark:bg-surface-tertiary dark:ring-white/10">
            <Sparkles className="size-5 text-emerald-600 dark:text-emerald-400" aria-hidden />
          </div>
          <h1 className="text-[1.75rem] font-semibold tracking-tight text-text-primary sm:text-4xl">
            {title}
          </h1>
          <p className="max-w-lg text-sm text-text-secondary sm:text-[15px]">{subtitle}</p>
        </div>

        <div
          className="flex flex-wrap items-center justify-center gap-2"
          role="tablist"
          aria-label="任务场景"
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
                  'rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
                  active
                    ? 'bg-neutral-900 text-white shadow-sm dark:bg-white dark:text-neutral-900'
                    : 'bg-white/80 text-text-secondary ring-1 ring-black/5 hover:bg-white hover:text-text-primary dark:bg-surface-tertiary dark:ring-white/10',
                )}
              >
                {s.label}
              </button>
            );
          })}
        </div>

        <div className="flex w-full max-w-2xl flex-wrap items-center justify-center gap-2">
          {visibleChips.map((chip) => {
            const Icon = chip.icon;
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => fillPrompt(chip.prompt)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[13px] text-text-primary',
                  'shadow-sm ring-1 ring-black/[0.06] transition hover:bg-neutral-50 hover:ring-black/10',
                  'dark:bg-surface-tertiary dark:ring-white/10 dark:hover:bg-surface-hover',
                )}
              >
                <Icon className="size-3.5 shrink-0 opacity-70" aria-hidden />
                <span>{chip.label}</span>
              </button>
            );
          })}
        </div>

        <p className="text-center text-xs text-text-secondary">
          {localize('com_ui_task_chip_hint')}
        </p>
      </div>
    </div>
  );
}
