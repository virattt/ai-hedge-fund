import { CheckCircle, Loader2, AlertCircle, Clock } from "lucide-react";
import { cn } from "../lib/utils";
import type { RunPhase } from "../store/runStore";
import type { Decision } from "../api/client";

interface AgentTimelineProps {
  phase: RunPhase;
  runId: string | null;
  decisions: Record<string, Decision> | null;
  errorMessage: string | null;
}

function StatusIcon({ phase }: { phase: RunPhase }) {
  switch (phase) {
    case "idle":
      return <Clock className="h-5 w-5 text-muted-foreground" />;
    case "running":
      return <Loader2 className="h-5 w-5 animate-spin text-blue-400" />;
    case "done":
      return <CheckCircle className="h-5 w-5 text-green-400" />;
    case "error":
      return <AlertCircle className="h-5 w-5 text-red-400" />;
  }
}

function StatusBadge({ phase }: { phase: RunPhase }) {
  return (
    <span
      data-testid="run-status"
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        phase === "idle" && "bg-secondary text-secondary-foreground",
        phase === "running" && "bg-blue-500/10 text-blue-400",
        phase === "done" && "bg-green-500/10 text-green-400",
        phase === "error" && "bg-red-500/10 text-red-400",
      )}
    >
      <StatusIcon phase={phase} />
      {phase}
    </span>
  );
}

export function AgentTimeline({ phase, runId, decisions, errorMessage }: AgentTimelineProps) {
  if (phase === "idle") {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
        Configure your analysis and click Run to begin.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Status header */}
      <div className="flex items-center justify-between rounded-lg border border-border bg-card px-4 py-3">
        <div className="text-sm text-muted-foreground">
          Run {runId ? <code className="text-xs">{runId.slice(0, 8)}</code> : "..."}
        </div>
        <StatusBadge phase={phase} />
      </div>

      {/* Running state */}
      {phase === "running" && (
        <div
          data-testid="agent-running"
          className="flex items-center gap-3 rounded-lg border border-blue-500/20 bg-blue-500/5 p-4"
        >
          <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
          <span className="text-sm text-blue-300">Agents are analyzing...</span>
        </div>
      )}

      {/* Error state */}
      {phase === "error" && errorMessage && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4">
          <p className="text-sm text-red-400">{errorMessage}</p>
        </div>
      )}

      {/* Decisions table */}
      {phase === "done" && decisions && Object.keys(decisions).length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border" data-testid="decisions-table">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Ticker</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Action</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Qty</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(decisions).map(([ticker, dec]) => (
                <tr key={ticker} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 font-medium">{ticker}</td>
                  <td className="px-4 py-2">
                    <span
                      className={cn(
                        "inline-block rounded px-2 py-0.5 text-xs font-medium",
                        dec.action === "buy" && "bg-green-500/10 text-green-400",
                        dec.action === "sell" && "bg-red-500/10 text-red-400",
                        dec.action === "hold" && "bg-secondary text-secondary-foreground",
                        dec.action === "short" && "bg-orange-500/10 text-orange-400",
                        dec.action === "cover" && "bg-blue-500/10 text-blue-400",
                      )}
                    >
                      {dec.action}
                    </span>
                  </td>
                  <td className="px-4 py-2">{dec.quantity}</td>
                  <td className="px-4 py-2">{dec.confidence.toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
