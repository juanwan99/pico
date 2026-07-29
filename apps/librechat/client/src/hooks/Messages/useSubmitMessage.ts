import { useCallback } from 'react';
import { useRecoilValue, useSetRecoilState } from 'recoil';
import { replaceSpecialVars } from 'librechat-data-provider';
import type { TMessage } from 'librechat-data-provider';
import { useChatContext, useChatFormContext, useAddedChatContext } from '~/Providers';
import { useGetLatestMessage } from '~/hooks/Messages/useLatestMessage';
import { useAuthContext } from '~/hooks/AuthContext';
import { mainTextareaId } from '~/common';
import store from '~/store';
import { workspaceContextPrefix } from '~/components/Chat/Input/WorkspaceSelector';

export default function useSubmitMessage() {
  const { user } = useAuthContext();
  const methods = useChatFormContext();
  const { conversation: addedConvo } = useAddedChatContext();
  const { ask, index, getMessages, setMessages, conversation } = useChatContext();
  const getLatestMessage = useGetLatestMessage(index);

  const autoSendPrompts = useRecoilValue(store.autoSendPrompts);
  const setActivePrompt = useSetRecoilState(store.activePromptByIndex(index));

  const submitMessage = useCallback(
    (data?: {
      text: string;
      overrideFiles?: TMessage['files'];
      overrideQuotes?: string[];
      overrideManualSkills?: string[];
    }) => {
      if (!data) {
        return console.warn('No data provided to submitMessage');
      }
      const latestMessage = getLatestMessage();
      const rootMessages = getMessages();
      const isLatestInRootMessages = rootMessages?.some(
        (message) => message.messageId === latestMessage?.messageId,
      );
      if (!isLatestInRootMessages && latestMessage) {
        setMessages([...(rootMessages || []), latestMessage]);
      }

      const convoId = conversation?.conversationId;
      const userId = user?.id ?? (user as { _id?: string } | undefined)?._id;
      let wsPrefix = workspaceContextPrefix(convoId);
      if (userId && wsPrefix && !wsPrefix.includes('【Pico-User:')) {
        wsPrefix = `【Pico-User:${String(userId)}】 ${wsPrefix}`;
      } else if (userId && !wsPrefix) {
        wsPrefix = `【Pico-User:${String(userId)}】\n`;
      }
      const textWithWs =
        wsPrefix &&
        data.text &&
        !data.text.includes('【Pico-Convo:') &&
        !data.text.includes('【Pico-User:') &&
        !data.text.startsWith('【工作空间')
          ? `${wsPrefix}${data.text}`
          : data.text;
      const submitted = ask(
        {
          text: textWithWs,
        },
        {
          addedConvo: addedConvo ?? undefined,
          overrideFiles: data.overrideFiles,
          overrideQuotes: data.overrideQuotes,
          overrideManualSkills: data.overrideManualSkills,
        },
      );
      if (submitted === false) {
        return false;
      }
      methods.reset();
    },
    [ask, methods, addedConvo, setMessages, getMessages, getLatestMessage, conversation, user],
  );

  const submitPrompt = useCallback(
    (text: string) => {
      const parsedText = replaceSpecialVars({ text, user });
      if (autoSendPrompts) {
        submitMessage({ text: parsedText });
        return;
      }

      const textarea = document.getElementById(mainTextareaId) as HTMLTextAreaElement | null;
      const currentText = textarea?.value ?? methods.getValues('text');
      const newText = currentText.trim().length > 1 ? `\n${parsedText}` : parsedText;
      setActivePrompt(newText);
    },
    [autoSendPrompts, submitMessage, setActivePrompt, methods, user],
  );

  return { submitMessage, submitPrompt };
}
