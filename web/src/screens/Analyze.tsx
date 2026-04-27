import { useCallback, useRef } from "react";
import { RunConfigForm, type RunConfig } from "../components/RunConfigForm";
import { AgentTimeline } from "../components/AgentTimeline";
import { useRunStore } from "../store/runStore";
import { streamAnalyze } from "../api/sse";
import type { Decision } from "../api/client";

export function Analyze() {
  const { phase, runId, decisions, errorMessage, reset, setRunning, addEvent, setDone, setError } =
    useRunStore();
  const abortRef = useRef<AbortController | null>(null);

  const handleSubmit = useCallback(
    (config: RunConfig) => {
      // Cancel any in-flight stream
      abortRef.current?.abort();
      reset();

      const controller = streamAnalyze(
        {
          tickers: config.tickers,
          selected_analysts: config.selectedAnalysts,
          model_name: config.modelName,
          model_provider: config.modelProvider,
          start_date: config.startDate || undefined,
          end_date: config.endDate || undefined,
        },
        (evt) => {
          addEvent(evt);
          try {
            const data = JSON.parse(evt.data);
            if (evt.event === "run.started") {
              setRunning(data.run_id);
            } else if (evt.event === "run.done") {
              setDone(data.decisions as Record<string, Decision>);
            } else if (evt.event === "error") {
              setError(data.message);
            }
          } catch {
            // Ignore parse errors for non-JSON events
          }
        },
        (err) => {
          setError(err.message);
        },
      );

      abortRef.current = controller;
      // Optimistic: set running immediately (run.started will confirm with real ID)
      setRunning("pending...");
    },
    [reset, setRunning, addEvent, setDone, setError],
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <div className="rounded-lg border border-border bg-card p-5">
        <h2 className="mb-4 text-lg font-semibold">Run Configuration</h2>
        <RunConfigForm onSubmit={handleSubmit} disabled={phase === "running"} />
      </div>
      <div>
        <h2 className="mb-4 text-lg font-semibold">Results</h2>
        <AgentTimeline
          phase={phase}
          runId={runId}
          decisions={decisions}
          errorMessage={errorMessage}
        />
      </div>
    </div>
  );
}
