import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { Loader2 } from "lucide-react";
import { fetchRuns, type RunListItem } from "../api/client";
import { cn } from "../lib/utils";

function StatusBadge({ status }: { status: RunListItem["status"] }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        status === "done" && "bg-green-500/10 text-green-400",
        status === "running" && "bg-blue-500/10 text-blue-400",
        status === "error" && "bg-red-500/10 text-red-400",
      )}
    >
      {status}
    </span>
  );
}

export function History() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["runs"],
    queryFn: () => fetchRuns(),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">
        Failed to load runs: {(error as Error).message}
      </div>
    );
  }

  const items = data?.items ?? [];

  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold">Past Runs</h2>
      {items.length === 0 ? (
        <div
          className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground"
          data-testid="empty-runs"
        >
          No runs yet. Go to Analyze to start one.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border" data-testid="runs-table">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">ID</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Status</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Tickers</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Model</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Started</th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Duration</th>
              </tr>
            </thead>
            <tbody>
              {items.map((run) => (
                <tr key={run.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 font-mono text-xs">{run.id.slice(0, 8)}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-2">{run.tickers.join(", ")}</td>
                  <td className="px-4 py-2">{run.model_name}</td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {format(new Date(run.started_at), "MMM d, HH:mm")}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
