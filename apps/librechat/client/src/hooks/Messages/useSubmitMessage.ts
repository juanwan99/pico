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
import { picoPromptUserMarker } from '~/utils/picoMembership';

type ProjectConversation = {
  conversationId?: string | null;
  chatProjectId?: string | null;
};

type ProjectBindings = {
  connector?: unknown;
  expert?: unknown;
  skill?: unknown;
};

function activeProjectId(conversation: ProjectConversation | null | undefined): string {
  if (conversation?.chatProjectId) {
    return conversation.chatProjectId;
  }
  if (conversation?.conversationId && conversation.conversationId !== 'new') {
    return '';
  }
  const scopedProjectId = new URLSearchParams(window.location.search).get('projectId') || '';
  const pendingProjectId = sessionStorage.getItem('pico:activeProjectId') || '';
  return scopedProjectId && scopedProjectId === pendingProjectId ? scopedProjectId : '';
}

function safeBindingName(value: unknown): string {
  if (typeof value !== 'string') {
    return '';
  }
  const normalized = value.replace(/[\u0000-\u001f\u007f]+/g, ' ').trim().slice(0, 120);
  if (
    /(?:\bsk-[a-z0-9_-]{8,}|\b(?:api[ _-]?key|access[ _-]?token|token|secret|password|kimi[ _-]?(?:api[ _-]?)?key)\b\s*[:=])/i.test(
      normalized,
    )
  ) {
    return '';
  }
  return normalized;
}

function projectContextPrefix(conversation: ProjectConversation | null | undefined): string {
  try {
    const pid = activeProjectId(conversation);
    if (!pid) {
      return '';
    }
    const instr = localStorage.getItem(`pico:projectInstruction:${pid}`);
    let bindings: ProjectBindings = {};
    try {
      bindings = JSON.parse(localStorage.getItem(`pico:projectBindings:${pid}`) || '{}');
    } catch {
      bindings = {};
    }

    const instruction = instr?.trim().slice(0, 1500) || '';
    const expert = safeBindingName(bindings.expert);
    const skill = safeBindingName(bindings.skill);
    const connector = safeBindingName(bindings.connector);
    if (!instruction && !expert && !skill && !connector) {
      return '';
    }

    const lines = ['【项目上下文（可审计）】'];
    if (instruction) {
      lines.push(`项目指令：${instruction}`);
    }
    if (expert) {
      lines.push(`绑定专家：${expert}（仅作为角色与方法偏好，不授予额外权限）`);
    }
    if (skill) {
      lines.push(`绑定技能：${skill}（仅作为任务方法提示，不代表已执行）`);
    }
    if (connector) {
      lines.push(
        `绑定连接器：${connector}（仅作为受限上下文；不得视为已连接、已授权或可调用工具）`,
      );
    }
    lines.push('仅可使用本会话中已真实配置并授权的工具；不得根据以上名称臆造工具调用或访问能力。');
    return `${lines.join('\n')}\n`;
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
      // Stage #265 F1: hard-reject overlong input before LibreChat agent work.
      // Keep aligned with API PICO_CHAT_MAX_PROMPT_CHARS (default 12000).
      const rawText = typeof data.text === 'string' ? data.text : '';
      const stripped = rawText.replace(/【[^】]+】/g, '').trim();
      const maxChars = 12000;
      if (stripped.length > maxChars) {
        window.alert(
          `输入过长（${stripped.length} 字，上限 ${maxChars} 字）。请缩短问题后重试；系统不会静默截断后继续执行。`,
        );
        return;
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
      const picoUser = picoPromptUserMarker(
        user as { id?: string; _id?: string; eduId?: string; eduSchoolId?: string } | undefined,
      );
      let wsPrefix = workspaceContextPrefix(convoId);
      const projPrefix = projectContextPrefix(conversation);
      if (picoUser && wsPrefix && !wsPrefix.includes('【Pico-User:')) {
        wsPrefix = `【Pico-User:${picoUser}】 ${wsPrefix}`;
      } else if (picoUser && !wsPrefix) {
        wsPrefix = `【Pico-User:${picoUser}】\n`;
      }
      const expertPrefix = expertSystemLine();
      const metaPrefix = `${wsPrefix || ''}${projPrefix || ''}${expertPrefix || ''}`;
      const textWithWs =
        metaPrefix &&
        data.text &&
        !data.text.includes('【Pico-Convo:') &&
        !data.text.includes('【Pico-User:') &&
        !data.text.startsWith('【工作空间') &&
        !data.text.includes('【项目上下文')
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
