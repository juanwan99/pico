import { createContext, useContext } from 'react';

/** Step lines of the conversation's latest run, for the box above the reply (#1169). */
export type PicoRunSteps = {
  /** The run is still going (queued / preparing / running). */
  active: boolean;
  lines: string[];
};

export const PicoRunStepsContext = createContext<PicoRunSteps>({ active: false, lines: [] });

export const usePicoRunSteps = () => useContext(PicoRunStepsContext);
