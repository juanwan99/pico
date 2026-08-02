import React, { createContext, useContext } from 'react';
import type { ConversationStatusMap } from './usePicoConversationStatusMap';

const Ctx = createContext<ConversationStatusMap>({});

export function PicoConversationStatusProvider({
  children,
  statusByConversationId,
}: {
  children: React.ReactNode;
  statusByConversationId: ConversationStatusMap;
}) {
  return <Ctx.Provider value={statusByConversationId}>{children}</Ctx.Provider>;
}

export function useConversationLedgerStatus(conversationId?: string | null): string | null {
  const map = useContext(Ctx);
  if (!conversationId) {
    return null;
  }
  return map[conversationId] ?? null;
}
