/**
 * Pico home — one title, one composer row. Attach lives in +; 快速/深度 is a switch.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { ExtendedFile } from '~/common';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useOptionalChatContext, useOptionalChatFormContext } from '~/Providers';
import { useAuthContext } from '~/hooks';
import useSubmitMessage from '~/hooks/Messages/useSubmitMessage';
import FileFormChat from '~/components/Chat/Input/Files/FileFormChat';
import {
  ComposerModeSwitch,
  ComposerPlanToggle,
  useComposerAttachInput,
} from '~/components/Chat/Input/ComposerPlusMenu';
import { cn } from '~/utils';
import ArchiveFolderBar from '~/components/Chat/ArchiveFolderBar';
import SchoolMaterialsBar from '~/components/Chat/SchoolMaterialsBar';
import PointsBar from '~/components/Chat/PointsBar';
import { usePointsMeter } from '~/hooks/Pico/usePointsMeter';
import {
  consumePendingModel,
  getPicoModelMode,
  normalizePicoModelMode,
  patchConversationModel,
  patchConversationPlan,
  setPicoModelMode,
  setPicoPlanOn,
} from '~/utils/picoModelPref';

const PLACEHOLDER = '发消息';
/** ~6 body lines (16px × 1.55). Then the textarea scrolls. */
const COMPOSER_MAX_PX = 149;

export default function Landing({
  centerFormOnLanding: _c,
  children,
}: {
  centerFormOnLanding: boolean;
  children?: ReactNode;
}) {
  const { user } = useAuthContext();
  const form = useOptionalChatFormContext();
  const { submitMessage } = useSubmitMessage();
  const { quoteFromChars } = usePointsMeter();
  const [text, setText] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [model, setModel] = useState(() => {
    try {
      return normalizePicoModelMode(getPicoModelMode());
    } catch {
      return 'pico-fast';
    }
  });
  const [planOn, setPlanOn] = useState(false);
  const chatCtx = useOptionalChatContext();
  const setConversationRef = useRef(chatCtx?.setConversation);
  setConversationRef.current = chatCtx?.setConversation;
  const [localFiles, setLocalFiles] = useState(() => new Map<string, ExtendedFile>());
  const [localFilesLoading, setLocalFilesLoading] = useState(false);
  const files = chatCtx?.files ?? localFiles;
  const setFiles = chatCtx?.setFiles ?? setLocalFiles;
  const setFilesLoading = chatCtx?.setFilesLoading ?? setLocalFilesLoading;
  const attach = useComposerAttachInput({
    conversation: chatCtx?.conversation ?? null,
    files,
    setFiles,
    setFilesLoading,
    onPicked: undefined,
  });
  const applyModel = useCallback((raw: string) => {
    const id = normalizePicoModelMode(raw);
    setModel((prev) => (prev === id ? prev : id));
    setPicoModelMode(id);
    setConversationRef.current?.((prev) => patchConversationModel(prev, id) ?? prev);
  }, []);
  const applyPlan = useCallback((on: boolean) => {
    setPlanOn((prev) => (prev === on ? prev : on));
    setPicoPlanOn(on);
    setConversationRef.current?.((prev) => patchConversationPlan(prev, on) ?? prev);
  }, []);

  useEffect(() => {
    quoteFromChars(text.length);
  }, [text, quoteFromChars]);

  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) {
      return;
    }
    el.style.height = 'auto';
    el.style.height = `${Math.max(32, Math.min(el.scrollHeight || 32, COMPOSER_MAX_PX))}px`;
  }, [text]);

  const syncForm = useCallback(
    (value: string) => {
      setText(value);
      form?.setValue('text', value, { shouldDirty: true, shouldTouch: true });
    },
    [form],
  );
  const syncFormRef = useRef(syncForm);
  syncFormRef.current = syncForm;
  const applyModelRef = useRef(applyModel);
  applyModelRef.current = applyModel;
  const applyPlanRef = useRef(applyPlan);
  applyPlanRef.current = applyPlan;

  const sendTask = useCallback(() => {
    const value = text.trim();
    if (!value) {
      return;
    }
    quoteFromChars(value.length);
    // Single submit path — no DOM bridge to hidden ChatForm
    submitMessage({ text: value });
    syncForm('');
  }, [text, submitMessage, syncForm, quoteFromChars]);

  // Expert / skill "summon" prefill from capability hub. Mount-only: applyModel
  // used to write PENDING and depend on chatCtx, which retriggered consume → #185.
  useEffect(() => {
    try {
      const pendingModel = consumePendingModel();
      if (pendingModel) {
        applyModelRef.current(pendingModel);
      }
      // New home: 先计划 off. Do not restore pico:planOn from storage (#809 T3).
      applyPlanRef.current(false);
      const pre = sessionStorage.getItem('pico:pendingPrompt');
      if (pre) {
        sessionStorage.removeItem('pico:pendingPrompt');
        syncFormRef.current(pre);
        requestAnimationFrame(() => {
          document.getElementById('pico-wb-home-input')?.focus();
        });
      }
    } catch {
      /* ignore */
    }
  }, []);

  const name = user?.name?.split(/\s+/)[0] || '';

  return (
    <div className="pico-wb-landing pico-shell-bg flex h-full min-h-0 w-full flex-col items-center">
      <div className="flex min-h-0 w-full flex-1 flex-col items-center overflow-y-auto px-4 pt-10 sm:px-6 sm:pt-12">
        <h1 className="pico-type-title text-center tracking-normal text-[color:var(--pico-ink)] dark:text-text-primary">
          Pico，我帮你
        </h1>
        {name ? (
          <p className="pico-type-aux mt-2.5 text-[color:var(--pico-ink-3)]">
            {name}，直接说就行
          </p>
        ) : null}
      </div>

      <div
        className="w-full max-w-[797px] shrink-0 px-4 pb-3 sm:px-6"
        data-testid="pico-wb-home-composer-dock"
      >
        {children}
        <SchoolMaterialsBar conversationId={chatCtx?.conversation?.conversationId} />
        <ArchiveFolderBar conversationId={chatCtx?.conversation?.conversationId} />
        <PointsBar />
        <div
          className="pico-wb-composer overflow-visible rounded-[var(--pico-radius)] border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] shadow-[var(--pico-shadow)]"
          data-testid="pico-wb-home-composer"
        >
          <FileFormChat
            conversation={chatCtx?.conversation ?? null}
            files={files}
            setFiles={setFiles}
            setFilesLoading={setFilesLoading}
          />
          <div
            className="pico-wb-composer-row relative flex items-end gap-2 px-2 py-2"
            data-testid="composer-one-row"
          >
            <div className="relative z-50 shrink-0">
              {attach.input}
              <button
                type="button"
                data-testid="composer-plus"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[color:var(--pico-ink-2)] hover:bg-black/[0.04]"
                aria-label="上传附件"
                onClick={attach.openPicker}
              >
                <PicoIcon name="plus" className="text-[color:var(--pico-ink-2)]" />
              </button>
            </div>
            <textarea
              id="pico-wb-home-input"
              ref={inputRef}
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
              className="pico-type-body min-h-8 min-w-0 flex-1 resize-none overflow-y-auto border-0 bg-transparent py-1 text-[color:var(--pico-ink)] outline-none placeholder:text-[color:var(--pico-ink-3)]"
            />
            <ComposerModeSwitch value={model} onChange={applyModel} />
            <ComposerPlanToggle on={planOn} onChange={applyPlan} />
            <button
              type="button"
              data-testid="send-button"
              className={cn(
                'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors',
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
  );
}
