import { useState, useCallback, useRef } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Play, Loader2 } from "lucide-react";
import { cn } from "../lib/utils";
import { streamBacktest, type BacktestRequest } from "../api/sse";

const DEFAULT_ANALYSTS = [
  { key: "technical_analyst", display_name: "Technical Analyst" },
  { key: "fundamentals_analyst", display_name: "Fundamentals Analyst" },
  { key: "sentiment_analyst", display_name: "Sentiment Analyst" },
  { key: "valuation_analyst", display_name: "Valuation Analyst" },
  { key: "warren_buffett", display_name: "Warren Buffett" },
  { key: "charlie_munger", display_name: "Charlie Munger" },
  { key: "ben_graham", display_name: "Ben Graham" },
  { key: "bill_ackman", display_name: "Bill Ackman" },
  { key: "cathie_wood", display_name: "Cathie Wood" },
  { key: "stanley_druckenmiller", display_name: "Stanley Druckenmiller" },
  { key: "phil_fisher", display_name: "Phil Fisher" },
];

const DEFAULT_MODELS = [
  { model_name: "gpt-4o", provider: "OpenAI", display_name: "GPT-4o" },
  {
    model_name: "claude-3-5-sonnet-20241022",
    provider: "Anthropic",
    display_name: "Claude 3.5 Sonnet",
  },
  {
    model_name: "deepseek-chat",
    provider: "DeepSeek",
    display_name: "DeepSeek Chat",
  },
];

interface PortfolioPoint {
  date: string;
  value: number;
}

type Phase = "idle" | "running" | "done" | "error";

export function Backtest() {
  const [tickerInput, setTickerInput] = useState("AAPL, MSFT");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [initialCash, setInitialCash] = useState("100000");
  const [marginReq, setMarginReq] = useState("0");
  const [selectedAnalysts, setSelectedAnalysts] = useState<string[]>(
    DEFAULT_ANALYSTS.map((a) => a.key),
  );
  const [selectedModel, setSelectedModel] = useState(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [portfolioData, setPortfolioData] = useState<PortfolioPoint[]>([]);
  const [finalValue, setFinalValue] = useState<number | null>(null);
  const [totalReturn, setTotalReturn] = useState<number | null>(null);
  const [dayEvents, setDayEvents] = useState<number>(0);

  const abortRef = useRef<AbortController | null>(null);

  const toggleAnalyst = useCallback((key: string) => {
    setSelectedAnalysts((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      abortRef.current?.abort();

      const tickers = tickerInput
        .split(",")
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean);
      if (tickers.length === 0 || !startDate || !endDate) return;

      const model = DEFAULT_MODELS[selectedModel];
      const req: BacktestRequest = {
        tickers,
        start_date: startDate,
        end_date: endDate,
        initial_cash: parseFloat(initialCash) || 100000,
        margin_requirement: parseFloat(marginReq) || 0,
        selected_analysts: selectedAnalysts,
        model_name: model.model_name,
        model_provider: model.provider,
      };

      setPhase("running");
      setErrorMessage(null);
      setPortfolioData([]);
      setFinalValue(null);
      setTotalReturn(null);
      setDayEvents(0);

      const controller = streamBacktest(
        req,
        (evt) => {
          try {
            const data = JSON.parse(evt.data);
            if (evt.event === "day.completed") {
              setDayEvents((n) => n + 1);
            } else if (evt.event === "backtest.done") {
              setPhase("done");
              setFinalValue(data.final_value);
              setTotalReturn(data.total_return_pct);
              setPortfolioData(
                (data.portfolio_values ?? []).map(
                  (pv: { date: string; value: number }) => ({
                    date: pv.date,
                    value: pv.value,
                  }),
                ),
              );
            } else if (evt.event === "error") {
              setPhase("error");
              setErrorMessage(data.message);
            }
          } catch {
            // ignore non-JSON
          }
        },
        (err) => {
          setPhase("error");
          setErrorMessage(err.message);
        },
      );

      abortRef.current = controller;
    },
    [
      tickerInput,
      startDate,
      endDate,
      initialCash,
      marginReq,
      selectedAnalysts,
      selectedModel,
    ],
  );

  const isRunning = phase === "running";

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      {/* Config form */}
      <div className="rounded-lg border border-border bg-card p-5">
        <h2 className="mb-4 text-lg font-semibold">Backtest Configuration</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="bt-tickers"
              className="mb-1.5 block text-sm font-medium"
            >
              Tickers
            </label>
            <input
              id="bt-tickers"
              type="text"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value)}
              placeholder="AAPL, MSFT"
              disabled={isRunning}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="bt-start"
                className="mb-1.5 block text-sm font-medium"
              >
                Start Date
              </label>
              <input
                id="bt-start"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                disabled={isRunning}
                required
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label
                htmlFor="bt-end"
                className="mb-1.5 block text-sm font-medium"
              >
                End Date
              </label>
              <input
                id="bt-end"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                disabled={isRunning}
                required
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="bt-cash"
                className="mb-1.5 block text-sm font-medium"
              >
                Initial Cash
              </label>
              <input
                id="bt-cash"
                type="number"
                value={initialCash}
                onChange={(e) => setInitialCash(e.target.value)}
                disabled={isRunning}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div>
              <label
                htmlFor="bt-margin"
                className="mb-1.5 block text-sm font-medium"
              >
                Margin Req.
              </label>
              <input
                id="bt-margin"
                type="number"
                step="0.01"
                value={marginReq}
                onChange={(e) => setMarginReq(e.target.value)}
                disabled={isRunning}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          {/* Analysts */}
          <div>
            <span className="mb-1.5 block text-sm font-medium">Analysts</span>
            <div className="flex flex-wrap gap-2">
              {DEFAULT_ANALYSTS.map((analyst) => (
                <label
                  key={analyst.key}
                  className={cn(
                    "flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
                    selectedAnalysts.includes(analyst.key)
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:border-primary/50",
                    isRunning && "pointer-events-none opacity-50",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selectedAnalysts.includes(analyst.key)}
                    onChange={() => toggleAnalyst(analyst.key)}
                    disabled={isRunning}
                    className="sr-only"
                  />
                  {analyst.display_name}
                </label>
              ))}
            </div>
          </div>

          {/* Model */}
          <div>
            <label
              htmlFor="bt-model"
              className="mb-1.5 block text-sm font-medium"
            >
              Model
            </label>
            <select
              id="bt-model"
              value={selectedModel}
              onChange={(e) => setSelectedModel(Number(e.target.value))}
              disabled={isRunning}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {DEFAULT_MODELS.map((m, i) => (
                <option key={m.model_name} value={i}>
                  {m.display_name} ({m.provider})
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={isRunning}
            className={cn(
              "inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90",
              isRunning && "pointer-events-none opacity-50",
            )}
          >
            {isRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {isRunning ? "Running..." : "Run Backtest"}
          </button>
        </form>
      </div>

      {/* Results */}
      <div>
        <h2 className="mb-4 text-lg font-semibold">Results</h2>

        {phase === "idle" && (
          <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
            Configure and run a backtest to see results.
          </div>
        )}

        {phase === "running" && (
          <div className="rounded-lg border border-border bg-card p-8 text-center">
            <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Running backtest... {dayEvents > 0 && `${dayEvents} trades processed`}
            </p>
          </div>
        )}

        {phase === "error" && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">
            {errorMessage}
          </div>
        )}

        {phase === "done" && (
          <div className="space-y-4">
            {/* Metrics bar */}
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-lg border border-border bg-card p-4">
                <div className="text-xs text-muted-foreground">Final Value</div>
                <div className="text-xl font-semibold">
                  ${finalValue?.toLocaleString() ?? "-"}
                </div>
              </div>
              <div className="rounded-lg border border-border bg-card p-4">
                <div className="text-xs text-muted-foreground">
                  Total Return
                </div>
                <div
                  className={cn(
                    "text-xl font-semibold",
                    (totalReturn ?? 0) >= 0
                      ? "text-green-400"
                      : "text-red-400",
                  )}
                >
                  {totalReturn != null ? `${totalReturn.toFixed(2)}%` : "-"}
                </div>
              </div>
              <div className="rounded-lg border border-border bg-card p-4">
                <div className="text-xs text-muted-foreground">
                  Trading Days
                </div>
                <div className="text-xl font-semibold">
                  {portfolioData.length}
                </div>
              </div>
            </div>

            {/* Chart */}
            {portfolioData.length > 0 && (
              <div className="rounded-lg border border-border bg-card p-4">
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                  Equity Curve
                </h3>
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={portfolioData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11, fill: "#888" }}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#888" }}
                      tickFormatter={(v: number) =>
                        `$${(v / 1000).toFixed(0)}k`
                      }
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#1a1a2e",
                        border: "1px solid #333",
                        borderRadius: 8,
                        color: "#eee",
                      }}
                      formatter={(v) => [
                        `$${Number(v).toLocaleString()}`,
                        "Value",
                      ]}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#6366f1"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
