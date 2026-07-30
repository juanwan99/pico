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
import { expertSystemLine } from '~/utils/picoModelPref';

function projectInstructionPrefix(conversation: { chatProjectId?: string | null } | null | undefined): string {
  try {
    const pid =
      conversation?.chatProjectId ||
      sessionStorage.getItem('pico:activeProjectId') ||
      '';
    if (!pid) {
      return '';
    }
    const instr = localStorage.getItem(`pico:projectInstruction:${pid}`);
    if (!instr || !instr.trim()) {
      return '';
    }
    return `【项目指令：${instr.trim().slice(0, 1500)}】\n`;
  } catch {
    return '';
  }
}


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

      let convoId = conversation?.conversationId;
      // First message: LibreChat still has "new" — mint pending id for ledger binding
      if (!convoId || convoId === 'new') {
        try {
          const existing = sessionStorage.getItem('pico:pendingConvo');
          if (existing && existing.startsWith('pending_')) {
            convoId = existing;
          } else {
            const id =
              typeof crypto !== 'undefined' && crypto.randomUUID
                ? `pending_${crypto.randomUUID()}`
                : `pending_${Date.now()}`;
            sessionStorage.setItem('pico:pendingConvo', id);
            convoId = id;
          }
        } catch {
          convoId = `pending_${Date.now()}`;
        }
      } else if (convoId !== 'new') {
        try {
          const pending = sessionStorage.getItem('pico:pendingConvo');
          if (pending && pending.startsWith('pending_') && pending !== convoId) {
            sessionStorage.setItem('pico:rebindFrom', pending);
            sessionStorage.setItem('pico:rebindTo', convoId);
            sessionStorage.removeItem('pico:pendingConvo');
          }
        } catch {
          /* ignore */
        }
      }
      const userId = user?.id ?? (user as { _id?: string } | undefined)?._id;
      let wsPrefix = workspaceContextPrefix(convoId);
      const projPrefix = projectInstructionPrefix(conversation);
      if (userId && wsPrefix && !wsPrefix.includes('【Pico-User:')) {
        wsPrefix = `【Pico-User:${String(userId)}】 ${wsPrefix}`;
      } else if (userId && !wsPrefix) {
        wsPrefix = `【Pico-User:${String(userId)}】\n`;
      }
      const expertPrefix = expertSystemLine();
      const metaPrefix = `${wsPrefix || ''}${projPrefix || ''}${expertPrefix || ''}`;
      const textWithWs =
        metaPrefix &&
        data.text &&
        !data.text.includes('【Pico-Convo:') &&
        !data.text.includes('【Pico-User:') &&
        !data.text.startsWith('【工作空间') &&
        !data.text.includes('【项目指令')
          ? `${metaPrefix}${data.text}`
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
