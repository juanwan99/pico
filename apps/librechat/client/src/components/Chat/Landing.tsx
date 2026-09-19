/**
 * Pico home — greeting sits above a two-row composer. Attach lives in +.
 * 学校材料 / 存档 default behind the 材料 chip.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { ExtendedFile } from '~/common';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useOptionalChatContext, useOptionalChatFormContext } from '~/Providers';
import useSubmitMessage from '~/hooks/Messages/useSubmitMessage';
import FileFormChat from '~/components/Chat/Input/Files/FileFormChat';
import {
  ComposerModeSwitch,
  ComposerPlanToggle,
  useComposerAttachInput,
} from '~/components/Chat/Input/ComposerPlusMenu';
import { cn } from '~/utils';
import { captureClipboardFiles, clipboardPlainText } from '~/utils/pasteFiles';
import {
  ComposerMaterialsChip,
  ComposerMaterialsPanel,
} from '~/components/Chat/ComposerMaterials';
import PointsBar from '~/components/Chat/PointsBar';
import { useComposerMaterials } from '~/hooks/Pico/useComposerMaterials';
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
    el.style.height = `${Math.max(44, Math.min(el.scrollHeight || 44, COMPOSER_MAX_PX))}px`;
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

  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement> | ClipboardEvent) => {
      if (e.defaultPrevented) {
        return;
      }
      const pastedFiles = captureClipboardFiles(e.clipboardData, () => {
        e.preventDefault();
        const native = 'nativeEvent' in e ? e.nativeEvent : e;
        native.stopImmediatePropagation?.();
      });
      if (pastedFiles && pastedFiles.length > 0) {
        const timestamped = pastedFiles.map(
          (file) =>
            new File([file], `clipboard_${+new Date()}_${file.name}`, { type: file.type }),
        );
        void attach.handleFiles(timestamped);
        return;
      }
      if (pastedFiles) {
        return;
      }
      const pasted = clipboardPlainText(e.clipboardData);
      if (!pasted) {
        return;
      }
      const el = inputRef.current;
      if (!el) {
        syncForm(text + pasted);
        return;
      }
      const start = el.selectionStart ?? text.length;
      const end = el.selectionEnd ?? start;
      syncForm(text.slice(0, start) + pasted + text.slice(end));
    },
    [attach.handleFiles, syncForm, text],
  );

  useEffect(() => {
    const onPasteCapture = (ev: ClipboardEvent) => {
      const el = inputRef.current;
      if (!el) {
        return;
      }
      const target = ev.target as Node | null;
      if (target !== el && !(target && el.contains(target))) {
        return;
      }
      handlePaste(ev);
    };
    document.addEventListener('paste', onPasteCapture, true);
    return () => document.removeEventListener('paste', onPasteCapture, true);
  }, [handlePaste]);

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

  const materials = useComposerMaterials();

  return (
    <div className="pico-wb-landing pico-shell-bg flex h-full min-h-0 w-full flex-col items-center">
      <div className="flex min-h-0 w-full flex-1 flex-col items-center justify-end overflow-y-auto px-4 pb-6 sm:px-6">
        <h1 className="pico-type-title text-center tracking-tight text-[color:var(--pico-ink)]">
          Pico，我帮你
        </h1>
        <p className="pico-type-body mt-2 text-[color:var(--pico-ink-2)]">直接说就行</p>
      </div>

      <div
        className="relative w-full max-w-[797px] shrink-0 px-4 pb-3 sm:px-6"
        data-testid="pico-wb-home-composer-dock"
      >
        {children}
        <ComposerMaterialsPanel
          conversationId={chatCtx?.conversation?.conversationId}
          open={materials.open}
        />
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
          <div className="flex flex-col" data-testid="composer-one-row">
            <textarea
              id="pico-wb-home-input"
              ref={inputRef}
              data-testid="text-input"
              value={text}
              onChange={(e) => syncForm(e.target.value)}
              onPaste={handlePaste}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendTask();
                }
              }}
              placeholder={PLACEHOLDER}
              rows={1}
              className="pico-type-body min-h-[var(--pico-control-h)] min-w-0 w-full resize-none overflow-y-auto border-0 bg-transparent px-4 pt-3 text-[color:var(--pico-ink)] outline-none placeholder:text-[color:var(--pico-ink-3)]"
            />
            <div
              className="pico-wb-composer-row relative flex items-center gap-1.5 px-2 pb-2 pt-1"
              data-testid="composer-toolbar"
            >
              <div className="relative z-50 shrink-0">
                {attach.input}
                <button
                  type="button"
                  data-testid="composer-plus"
                  className="pico-hit inline-flex items-center justify-center rounded-lg text-[color:var(--pico-ink-2)] hover:bg-[color:var(--pico-surface-2)]"
                  aria-label="上传附件"
                  onClick={attach.openPicker}
                >
                  <PicoIcon name="plus" className="text-[color:var(--pico-ink-2)]" />
                </button>
              </div>
              <div className="min-w-0 flex-1" />
              <ComposerMaterialsChip open={materials.open} onToggle={materials.toggle} />
              <ComposerModeSwitch value={model} onChange={applyModel} />
              <ComposerPlanToggle on={planOn} onChange={applyPlan} />
              <button
                type="button"
                data-testid="send-button"
                className={cn(
                  'pico-hit inline-flex shrink-0 items-center justify-center rounded-lg transition-colors',
                  text.trim()
                    ? 'text-[color:var(--pico-accent)] hover:bg-[color:var(--pico-accent-wash)]'
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
    </div>
  );
}
