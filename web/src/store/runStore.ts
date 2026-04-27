import { create } from "zustand";
import type { Decision } from "../api/client";
import type { SSEEvent } from "../api/sse";

export type RunPhase = "idle" | "running" | "done" | "error";

export interface RunState {
  phase: RunPhase;
  runId: string | null;
  events: SSEEvent[];
  decisions: Record<string, Decision> | null;
  errorMessage: string | null;

  // Actions
  reset: () => void;
  setRunning: (runId: string) => void;
  addEvent: (evt: SSEEvent) => void;
  setDone: (decisions: Record<string, Decision>) => void;
  setError: (message: string) => void;
}

export const useRunStore = create<RunState>((set) => ({
  phase: "idle",
  runId: null,
  events: [],
  decisions: null,
  errorMessage: null,

  reset: () =>
    set({
      phase: "idle",
      runId: null,
      events: [],
      decisions: null,
      errorMessage: null,
    }),

  setRunning: (runId: string) =>
    set({ phase: "running", runId, events: [], decisions: null, errorMessage: null }),

  addEvent: (evt: SSEEvent) =>
    set((state) => ({ events: [...state.events, evt] })),

  setDone: (decisions: Record<string, Decision>) =>
    set({ phase: "done", decisions }),

  setError: (message: string) =>
    set({ phase: "error", errorMessage: message }),
}));
