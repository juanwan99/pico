import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useRecoilValue } from 'recoil';
import { useForm } from 'react-hook-form';
import { Spinner } from '@librechat/client';
import { PanelRightOpen } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { Constants, buildTree } from 'librechat-data-provider';
import type { TChatProject, TMessage } from 'librechat-data-provider';
import type { ChatFormValues } from '~/common';
import {
  useAddedResponse,
  useResumeOnLoad,
  useAdaptiveSSE,
  useChatHelpers,
  useQueueDrain,
  useLocalize,
} from '~/hooks';
import { ChatContext, AddedChatContext, ChatFormProvider, useFileMapContext } from '~/Providers';
import ConversationStarters from './Input/ConversationStarters';
import { useGetMessagesByConvoId } from '~/data-provider';
import ProjectLandingChip from './ProjectLandingChip';
import MessagesView from './Messages/MessagesView';
import Presentation from './Presentation';
import ChatForm from './Input/ChatForm';
import Landing from './Landing';
import ResultPanel from './ResultPanel';
import TaskRunBar from './TaskRunBar';
import ChangeConfirmBanner from './ChangeConfirmBanner';
import Header from './Header';
import Footer from './Footer';
import { cn } from '~/utils';
import store from '~/store';
import { usePicoTaskLedger } from '~/hooks/Pico/usePicoTaskLedger';

function LoadingSpinner() {
  return (
    <div className="relative flex-1 overflow-hidden overflow-y-auto">
      <div className="relative flex h-full items-center justify-center">
        <Spinner className="text-text-primary" />
      </div>
    </div>
  );
}

function ChatView({ index = 0, project }: { index?: number; project?: TChatProject }) {
  const { conversationId } = useParams();
  const localize = useLocalize();
  const rootSubmission = useRecoilValue(store.submissionByIndex(index));
  const isSubmitting = useRecoilValue(store.isSubmittingFamily(index));
  const centerFormOnLanding = useRecoilValue(store.centerFormOnLanding);

  const methods = useForm<ChatFormValues>({
    defaultValues: { text: '' },
  });

  const fileMap = useFileMapContext();

  const {
    data: messagesTree = null,
    isLoading,
    isFetching,
  } = useGetMessagesByConvoId(
    conversationId ?? '',
    {
      select: useCallback(
        (data: TMessage[]) => {
          const dataTree = buildTree({ messages: data, fileMap });
          return dataTree?.length === 0 ? null : (dataTree ?? null);
        },
        [fileMap],
      ),
      enabled: !!conversationId && conversationId !== Constants.SEARCH,
      /** Refetch stale caches on mount: navigation invalidates (not removes)
       * messages now, so a warm conversation renders instantly from cache and
       * reconciles in the background instead of unmounting into a spinner. */
      refetchOnMount: true,
    },
    { isStreaming: isSubmitting },
  );

  const chatHelpers = useChatHelpers(index, conversationId);
  const addedChatHelpers = useAddedResponse();

  useAdaptiveSSE(rootSubmission, chatHelpers, false, index);

  // Auto-resume if navigating back to conversation with active job.
  // Wait for messages to load AND the warm-cache background revalidation to
  // settle: a stale invalidated cache mounts with isLoading false while the
  // refetch is in flight, and resume must not build from (or race) it.
  useResumeOnLoad(conversationId, chatHelpers.getMessages, index, !isLoading && !isFetching);

  // Auto-send queued follow-up messages once a run finishes cleanly.
  useQueueDrain(index, conversationId, chatHelpers.ask);

  let content: JSX.Element | null | undefined;
  const isLandingPage =
    (!messagesTree || messagesTree.length === 0) &&
    (conversationId === Constants.NEW_CONVO || !conversationId);
  const isNavigating = (!messagesTree || messagesTree.length === 0) && conversationId != null;
  const isProjectLandingPage = isLandingPage && project != null;
  const [compactResult, setCompactResult] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(max-width: 1024px)').matches,
  );
  const [resultOpen, setResultOpen] = useState(
    () => typeof window === 'undefined' || !window.matchMedia('(max-width: 1024px)').matches,
  );
  const flatMessages = useMemo(
    () => chatHelpers.getMessages?.() ?? null,
    [chatHelpers, messagesTree, isSubmitting],
  );
  const taskTitle =
    chatHelpers.conversation?.title && chatHelpers.conversation.title !== 'New Chat'
      ? chatHelpers.conversation.title
      : undefined;
  const ledger = usePicoTaskLedger(conversationId, isSubmitting);
  const runStatusLabel = ledger.statusLabel ?? (isSubmitting ? '等待模型响应' : undefined);
  const showResultPanel = resultOpen && !isLandingPage && conversationId !== Constants.SEARCH;

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1024px)');
    const syncResultLayout = (event: MediaQueryListEvent) => {
      setCompactResult(event.matches);
      setResultOpen(!event.matches);
    };
    media.addEventListener('change', syncResultLayout);
    return () => media.removeEventListener('change', syncResultLayout);
  }, []);

  // WorkBuddy chrome: task pages always show right rail by default
  useEffect(() => {
    if (compactResult || !conversationId || conversationId === Constants.NEW_CONVO) {
      return;
    }
    setResultOpen(true);
  }, [compactResult, conversationId]);

  // Ensure result panel opens when artifacts arrive or run finishes
  useEffect(() => {
    if (compactResult || !conversationId || conversationId === Constants.NEW_CONVO) {
      return;
    }
    if ((ledger.artifacts?.length ?? 0) > 0 || ledger.statusLabel?.startsWith('已完成')) {
      setResultOpen(true);
    }
  }, [compactResult, conversationId, ledger.artifacts, ledger.statusLabel]);

  if (isLoading && conversationId !== Constants.NEW_CONVO) {
    content = <LoadingSpinner />;
  } else if ((isLoading || isNavigating) && !isLandingPage) {
    content = <LoadingSpinner />;
  } else if (!isLandingPage) {
    content = <MessagesView messagesTree={messagesTree} />;
  } else {
    content = <Landing centerFormOnLanding={centerFormOnLanding} />;
  }

  const chatFormPlaceholder =
    isProjectLandingPage && project
      ? localize('com_ui_new_chat_in_project', { name: project.name })
      : isLandingPage
        ? localize('com_ui_task_input_placeholder')
        : undefined;

  return (
    <ChatFormProvider {...methods}>
      <ChatContext.Provider value={chatHelpers}>
        <AddedChatContext.Provider value={addedChatHelpers}>
          <Presentation>
            <div className="relative flex h-full w-full flex-col">
              {!isLandingPage && (
                <>
                  <Header />
                  <TaskRunBar
                    title={taskTitle || ledger.task?.title}
                    isSubmitting={isSubmitting}
                    model={ledger.run?.model}
                    statusLabel={ledger.statusLabel}
                    completedLabel={
                      !isSubmitting &&
                      ledger.statusLabel &&
                      (ledger.statusLabel.startsWith('已完成') ||
                        ledger.statusLabel.startsWith('失败'))
                        ? ledger.statusLabel
                        : null
                    }
                  />
                  {ledger.error ? (
                    <div className="border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-[12px] text-amber-900">
                      账本：{ledger.error}
                    </div>
                  ) : null}
                  <ChangeConfirmBanner taskId={ledger.task?.id} />
                </>
              )}
              <div className="flex min-h-0 flex-1 flex-row">
                <div
                  className={cn(
                    'flex min-w-0 flex-1 flex-col',
                    isLandingPage
                      ? 'pico-wb-stage items-center justify-center gap-3 overflow-y-auto bg-[#f5f5f5] py-6 dark:bg-presentation'
                      : 'h-full overflow-hidden bg-[#fafafa] dark:bg-presentation',
                  )}
                >
                  <div
                    className={cn(
                      'flex min-h-0 w-full flex-1 flex-col',
                      !isLandingPage && 'overflow-y-auto',
                    )}
                  >
                    {content}
                  </div>
                  <div
                    className={cn(
                      'w-full shrink-0',
                      isLandingPage &&
                        'relative z-10 w-full max-w-[797px] px-4 transition-all duration-200',
                      !isLandingPage &&
                        'border-t border-black/[0.04] bg-white dark:border-border-light dark:bg-surface-primary',
                    )}
                  >
                    {isProjectLandingPage && project && <ProjectLandingChip project={project} />}
                    {/* Single submit path: Landing uses useSubmitMessage; ChatForm only when chatting */}
                    {!isLandingPage ? (
                      <div className="mx-auto w-full max-w-[797px] px-2 sm:px-0">
                        <ChatForm index={index} placeholder={chatFormPlaceholder} />
                      </div>
                    ) : null}
                  </div>
                </div>
                {showResultPanel ? (
                  <ResultPanel
                    messages={flatMessages}
                    taskTitle={taskTitle || ledger.task?.title}
                    runStatusLabel={runStatusLabel}
                    picoArtifacts={ledger.artifacts}
                    onClose={() => setResultOpen(false)}
                  />
                ) : null}
                {!resultOpen && !isLandingPage ? (
                  <button
                    type="button"
                    className="absolute right-3 top-14 z-20 inline-flex h-9 items-center gap-1.5 rounded-lg border border-black/[0.08] bg-white px-3 text-[12px] font-medium shadow-sm dark:bg-surface-secondary"
                    onClick={() => setResultOpen(true)}
                    data-testid="result-panel-toggle"
                  >
                    <PanelRightOpen className="h-3.5 w-3.5" />
                    结果区
                  </button>
                ) : null}
              </div>
            </div>
          </Presentation>
        </AddedChatContext.Provider>
      </ChatContext.Provider>
    </ChatFormProvider>
  );
}

export default memo(ChatView);
