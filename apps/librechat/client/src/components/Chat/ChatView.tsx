import { memo, useCallback, useMemo, useState } from 'react';
import { useRecoilValue } from 'recoil';
import { useForm } from 'react-hook-form';
import { Spinner } from '@librechat/client';
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
import Header from './Header';
import Footer from './Footer';
import { cn } from '~/utils';
import store from '~/store';

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
  const [resultOpen, setResultOpen] = useState(true);
  const flatMessages = useMemo(() => chatHelpers.getMessages?.() ?? null, [chatHelpers, messagesTree, isSubmitting]);
  const taskTitle = chatHelpers.conversation?.title && chatHelpers.conversation.title !== 'New Chat'
    ? chatHelpers.conversation.title
    : undefined;
  const runStatusLabel = isSubmitting ? '等待模型响应' : undefined;
  const showResultPanel = !isLandingPage && resultOpen && conversationId && conversationId !== Constants.NEW_CONVO;

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
              {!isLandingPage && <Header />}
              <div className={cn('flex min-h-0 flex-1', isLandingPage ? 'flex-col' : 'flex-row')}>
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
                      'flex min-h-0 flex-1 flex-col',
                      !isLandingPage && 'overflow-y-auto',
                    )}
                  >
                    {content}
                  </div>
                  <div
                    className={cn(
                      'w-full shrink-0',
                      isLandingPage && 'relative z-10 w-full max-w-[720px] px-4 transition-all duration-200',
                      !isLandingPage && 'border-t border-black/[0.04] bg-white dark:border-border-light dark:bg-surface-primary',
                    )}
                  >
                    {isProjectLandingPage && project && <ProjectLandingChip project={project} />}
                    <div
                      className={
                        isLandingPage
                          ? 'pointer-events-none fixed left-[-9999px] top-0 h-0 w-0 overflow-hidden opacity-0'
                          : 'mx-auto w-full max-w-3xl px-2'
                      }
                    >
                      <ChatForm index={index} placeholder={chatFormPlaceholder} />
                    </div>
                  </div>
                </div>
                {showResultPanel ? (
                  <ResultPanel
                    messages={flatMessages}
                    taskTitle={taskTitle}
                    runStatusLabel={runStatusLabel}
                    onClose={() => setResultOpen(false)}
                  />
                ) : null}
                {!isLandingPage && !resultOpen ? (
                  <button
                    type="button"
                    className="absolute right-3 top-14 z-20 rounded-lg border border-black/[0.08] bg-white px-2.5 py-1.5 text-[12px] shadow-sm dark:bg-surface-secondary"
                    onClick={() => setResultOpen(true)}
                  >
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
