import React, { createContext, useContext } from 'react';
import {
  usePicoConversationStatusMap,
  type ConversationStatusMap,
} from './usePicoConversationStatusMap';

const Ctx = createContext<ConversationStatusMap>({});

export function PicoConversationStatusProvider({ children }: { children: React.ReactNode }) {
  const { statusByConversationId } = usePicoConversationStatusMap(true);
  return <Ctx.Provider value={statusByConversationId}>{children}</Ctx.Provider>;
}

export function useConversationLedgerStatus(conversationId?: string | null): string | null {
  const map = useContext(Ctx);
  if (!conversationId) {
    return null;
  }
  return map[conversationId] ?? null;
}
