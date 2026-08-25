/**
 * Pico home — one title, one composer row. Model + attach live in +.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ExtendedFile } from '~/common';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useOptionalChatContext, useOptionalChatFormContext } from '~/Providers';
import { useAuthContext } from '~/hooks';
import useSubmitMessage from '~/hooks/Messages/useSubmitMessage';
import FileFormChat from '~/components/Chat/Input/Files/FileFormChat';
import {
  ComposerPlusItem,
  ComposerPlusMenu,
  PLUS_MODE_ITEMS,
  useComposerAttachInput,
} from '~/components/Chat/Input/ComposerPlusMenu';
import { cn } from '~/utils';
import SchoolMaterialsBar from '~/components/Chat/SchoolMaterialsBar';
import {
  consumePendingModel,
  getPicoModelMode,
  normalizePicoModelMode,
  patchConversationModel,
  setPicoModelMode,
} from '~/utils/picoModelPref';

const PLACEHOLDER = '发消息';

export default function Landing({ centerFormOnLanding: _c }: { centerFormOnLanding: boolean }) {
  const { user } = useAuthContext();
  const form = useOptionalChatFormContext();
  const { submitMessage } = useSubmitMessage();
  const [text, setText] = useState('');
  const [plusOpen, setPlusOpen] = useState(false);
  const [model, setModel] = useState(() => {
    try {
      return normalizePicoModelMode(getPicoModelMode());
    } catch {
      return 'pico-fast';
    }
  });
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
    onPicked: () => setPlusOpen(false),
  });
  const applyModel = useCallback((raw: string) => {
    const id = normalizePicoModelMode(raw);
    setModel((prev) => (prev === id ? prev : id));
    setPicoModelMode(id);
    setPlusOpen(false);
    setConversationRef.current?.((prev) => patchConversationModel(prev, id) ?? prev);
  }, []);

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

  const sendTask = useCallback(() => {
    const value = text.trim();
    if (!value) {
      return;
    }
    // Single submit path — no DOM bridge to hidden ChatForm
    submitMessage({ text: value });
    syncForm('');
  }, [text, submitMessage, syncForm]);

  // Expert / skill "summon" prefill from capability hub. Mount-only: applyModel
  // used to write PENDING and depend on chatCtx, which retriggered consume → #185.
  useEffect(() => {
    try {
      const pendingModel = consumePendingModel();
      if (pendingModel) {
        applyModelRef.current(pendingModel);
      }
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
    <div className="pico-wb-landing pico-shell-bg flex min-h-full w-full flex-col items-center px-4 pb-8 pt-10 sm:px-6 sm:pt-[132px]">
      <div className="flex w-full max-w-[797px] flex-col items-center">
        <h1 className="pico-type-title text-center tracking-normal text-[color:var(--pico-ink)] dark:text-text-primary">
          Pico，我帮你
        </h1>
        {name ? (
          <p className="pico-type-aux mt-2.5 text-[color:var(--pico-ink-3)]">
            {name}，直接说就行
          </p>
        ) : null}

        {/* One-row composer: + · input · send arrow */}
        <div className="mt-8 w-full max-w-[797px]">
          <SchoolMaterialsBar conversationId={chatCtx?.conversation?.conversationId} />
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
              className="pico-wb-composer-row relative flex items-end gap-0.5 px-1 py-1"
              data-testid="composer-one-row"
            >
              <div className="relative z-50 shrink-0 self-end">
                {attach.input}
                <button
                  type="button"
                  data-testid="composer-plus"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[color:var(--pico-ink-2)] hover:bg-black/[0.04]"
                  aria-label="更多输入选项"
                  aria-expanded={plusOpen}
                  onClick={() => {
                    setPlusOpen((v) => !v);
                  }}
                >
                  <PicoIcon name="plus" className="text-[color:var(--pico-ink-2)]" />
                </button>
                {plusOpen ? (
                  <ComposerPlusMenu>
                    {PLUS_MODE_ITEMS.map((item) => (
                      <ComposerPlusItem
                        key={item.id}
                        testId={`composer-plus-mode-${item.id}`}
                        active={model === item.id}
                        onClick={() => applyModel(item.id)}
                      >
                        {item.label}
                      </ComposerPlusItem>
                    ))}
                    <ComposerPlusItem testId="composer-plus-attach" onClick={attach.openPicker}>
                      上传附件
                    </ComposerPlusItem>
                  </ComposerPlusMenu>
                ) : null}
              </div>
              <textarea
                id="pico-wb-home-input"
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
                className="pico-type-body min-h-8 min-w-0 flex-1 resize-none border-0 bg-transparent py-2 leading-[1.55] text-[color:var(--pico-ink)] outline-none placeholder:text-[color:var(--pico-ink-3)]"
              />
              <button
                type="button"
                data-testid="send-button"
                className={cn(
                  'inline-flex h-8 w-8 shrink-0 items-center justify-center self-end rounded-md transition-colors',
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
    </div>
  );
}
