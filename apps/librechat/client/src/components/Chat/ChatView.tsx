import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRecoilValue } from 'recoil';
import { useForm } from 'react-hook-form';
import { Spinner } from '@librechat/client';
import { PicoIcon } from '~/components/ui/pico-icons';
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
import ArchiveFolderBar from './ArchiveFolderBar';
import SchoolMaterialsBar from './SchoolMaterialsBar';
import Landing from './Landing';
import MainDeliveryStrip from './MainDeliveryStrip';
import ResultPanel from './ResultPanel';
import TaskRunBar from './TaskRunBar';
import ChangeConfirmBanner from './ChangeConfirmBanner';
import Header from './Header';
import Footer from './Footer';
import { cn } from '~/utils';
import store from '~/store';
import { usePicoTaskLedger } from '~/hooks/Pico/usePicoTaskLedger';
import { collectPicoSandboxSession } from '~/utils/picoSandboxSession';
import {
  latestUserOpenOfficeIntent,
  latestUserOpenWebsiteIntent,
} from '~/utils/picoOpenInPane';

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
  const [resultOpen, setResultOpen] = useState(false);
  const flatMessages = useMemo(
    () => chatHelpers.getMessages?.() ?? null,
    [chatHelpers, messagesTree, isSubmitting],
  );
  const websiteIntent = useMemo(
    () => latestUserOpenWebsiteIntent(flatMessages),
    [flatMessages],
  );
  const officeIntent = useMemo(
    () => latestUserOpenOfficeIntent(flatMessages),
    [flatMessages],
  );
  const openPaneIntent = Boolean(websiteIntent || officeIntent);
  const openPaneIntentRef = useRef(openPaneIntent);
  openPaneIntentRef.current = openPaneIntent;
  const taskTitle =
    chatHelpers.conversation?.title && chatHelpers.conversation.title !== 'New Chat'
      ? chatHelpers.conversation.title
      : undefined;
  const ledger = usePicoTaskLedger(conversationId, isSubmitting);
  const cancellableRunId = ['queued', 'running', 'preparing'].includes(ledger.run?.status || '')
    ? ledger.run?.id
    : undefined;
  // Show task-bar「停止任务」whenever stream is live or ledger run is active.
  // Distinct from input-bar「停止生成」(screen-only).
  const canCancelTask = Boolean(cancellableRunId) || isSubmitting;
  const runStatusLabel = ledger.statusLabel ?? (isSubmitting ? '仍在处理…' : undefined);
  const showResultPanel = resultOpen && !isLandingPage && conversationId !== Constants.SEARCH;

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1024px)');
    const syncResultLayout = (event: MediaQueryListEvent) => {
      setCompactResult(event.matches);
      // Keep the rail if the teacher just asked to open a site/browser.
      if (event.matches && !openPaneIntentRef.current) {
        setResultOpen(false);
      }
    };
    media.addEventListener('change', syncResultLayout);
    return () => media.removeEventListener('change', syncResultLayout);
  }, []);

  // Open the right rail when the teacher asked to open a site/browser, or
  // when the ledger already has something to show. Idle chat stays closed.
  useEffect(() => {
    if (openPaneIntent) {
      setResultOpen(true);
      return;
    }
    if (compactResult || !conversationId || conversationId === Constants.NEW_CONVO) {
      return;
    }
    const realArtifacts = (ledger.artifacts ?? []).filter(
      (item) => !(item.kind === 'doc' && (item.title || '').trim() === '回复摘要'),
    );
    if (realArtifacts.length > 0 || collectPicoSandboxSession(ledger.events)) {
      setResultOpen(true);
    }
  }, [compactResult, conversationId, ledger.artifacts, ledger.events, openPaneIntent]);

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
      : localize('com_ui_task_input_placeholder');

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
                      // Terminal ledger labels always surface (even if stream isSubmitting).
                      ledger.statusLabel &&
                      (ledger.statusLabel.startsWith('已完成') ||
                        ledger.statusLabel.startsWith('失败') ||
                        ledger.statusLabel.startsWith('已停止'))
                        ? ledger.statusLabel
                        : null
                    }
                    canCancel={canCancelTask}
                    cancelling={ledger.cancelling}
                    onCancel={() => void ledger.cancelRun(cancellableRunId)}
                    canRerun={['failed', 'succeeded', 'cancelled'].includes(
                      ledger.run?.status || '',
                    )}
                    rerunning={ledger.rerunning}
                    onRerun={() => void ledger.rerunFailedRun(ledger.run?.id)}
                    processHint={ledger.processHint || (isSubmitting ? '正在检索或作答' : null)}
                  />
                  {ledger.error ? (
                    <div className="border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-[12px] text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-100">
                      账本：{ledger.error}
                    </div>
                  ) : null}
                  <ChangeConfirmBanner taskId={ledger.task?.id} onChanged={ledger.refresh} />
                </>
              )}
              <div className="flex min-h-0 flex-1 flex-row">
                <div
                  className={cn(
                    'flex min-w-0 flex-1 flex-col',
                    isLandingPage
                      ? 'pico-wb-stage items-center justify-center gap-3 overflow-y-auto bg-[color:var(--pico-shell)] py-6'
                      : 'h-full overflow-hidden bg-[color:var(--pico-shell)]',
                  )}
                >
                  <div
                    className={cn(
                      'flex min-h-0 w-full flex-1 flex-col',
                      !isLandingPage && 'overflow-y-auto',
                    )}
                  >
                    {content}
                    {!isLandingPage &&
                    conversationId &&
                    conversationId !== Constants.SEARCH ? (
                      <MainDeliveryStrip
                        artifacts={ledger.artifacts}
                        runEvents={ledger.events}
                        messages={flatMessages}
                        conversationId={conversationId}
                        onOpenResultPanel={() => setResultOpen(true)}
                      />
                    ) : null}
                  </div>
                  <div
                    className={cn(
                      'w-full shrink-0',
                      isLandingPage &&
                        'relative z-10 w-full max-w-[797px] px-4 transition-all duration-200',
                      !isLandingPage && 'bg-transparent',
                    )}
                  >
                    {isProjectLandingPage && project && <ProjectLandingChip project={project} />}
                    {/* Single submit path: Landing uses useSubmitMessage; ChatForm only when chatting */}
                    {!isLandingPage ? (
                      <div className="mx-auto w-full max-w-[797px] px-2 sm:px-0">
                        <SchoolMaterialsBar conversationId={conversationId} />
                        <ArchiveFolderBar conversationId={conversationId} />
                        <ChatForm index={index} placeholder={chatFormPlaceholder} />
                      </div>
                    ) : null}
                  </div>
                </div>
                {showResultPanel ? (
                  <ResultPanel
                    messages={flatMessages}
                    conversationId={conversationId}
                    taskTitle={taskTitle || ledger.task?.title}
                    runStatusLabel={runStatusLabel}
                    processHint={ledger.processHint || (isSubmitting ? '正在检索或作答' : null)}
                    picoArtifacts={ledger.artifacts}
                    runEvents={ledger.events}
                    run={ledger.run}
                    canRerun={['failed', 'succeeded', 'cancelled'].includes(
                      ledger.run?.status || '',
                    )}
                    rerunning={ledger.rerunning}
                    onRerun={() => void ledger.rerunFailedRun(ledger.run?.id)}
                    onClose={() => setResultOpen(false)}
                  />
                ) : null}
                {!resultOpen && !isLandingPage ? (
                  <button
                    type="button"
                    className="pico-type-aux pico-type-medium absolute right-3 top-14 z-[220] inline-flex h-9 items-center gap-1.5 rounded-lg border border-black/[0.08] bg-white px-3 shadow-sm dark:bg-surface-secondary"
                    onClick={() => setResultOpen(true)}
                    data-testid="result-panel-toggle"
                  >
                    <PicoIcon name="panel" size="sm" />
                    结果区
                    {(ledger.artifacts ?? []).filter(
                      (a) => !(a.kind === 'doc' && (a.title || '').trim() === '回复摘要'),
                    ).length > 0 ? (
                      <span
                        className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-[#3b6fd9] px-1.5 text-[10px] font-semibold text-white"
                        data-testid="result-artifact-count"
                        title="可下载文件"
                      >
                        {
                          ledger.artifacts.filter(
                            (a) => !(a.kind === 'doc' && (a.title || '').trim() === '回复摘要'),
                          ).length
                        }
                      </span>
                    ) : ledger.processHint ? (
                      <span className="ml-0.5 h-2 w-2 rounded-full bg-[#3b6fd9]" aria-hidden />
                    ) : null}
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
