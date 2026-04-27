import { useState, useCallback } from "react";
import { Play } from "lucide-react";
import { cn } from "../lib/utils";

/** Hardcoded defaults — in production these come from /api/analysts and /api/models */
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
  { model_name: "claude-3-5-sonnet-20241022", provider: "Anthropic", display_name: "Claude 3.5 Sonnet" },
  { model_name: "deepseek-chat", provider: "DeepSeek", display_name: "DeepSeek Chat" },
];

export interface RunConfig {
  tickers: string[];
  selectedAnalysts: string[];
  modelName: string;
  modelProvider: string;
  startDate: string;
  endDate: string;
}

interface RunConfigFormProps {
  onSubmit: (config: RunConfig) => void;
  disabled?: boolean;
}

export function RunConfigForm({ onSubmit, disabled = false }: RunConfigFormProps) {
  const [tickerInput, setTickerInput] = useState("AAPL, MSFT, GOOGL");
  const [selectedAnalysts, setSelectedAnalysts] = useState<string[]>(
    DEFAULT_ANALYSTS.map((a) => a.key),
  );
  const [selectedModel, setSelectedModel] = useState(0);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const toggleAnalyst = useCallback((key: string) => {
    setSelectedAnalysts((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const tickers = tickerInput
        .split(",")
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean);
      if (tickers.length === 0) return;

      const model = DEFAULT_MODELS[selectedModel];
      onSubmit({
        tickers,
        selectedAnalysts,
        modelName: model.model_name,
        modelProvider: model.provider,
        startDate,
        endDate,
      });
    },
    [tickerInput, selectedAnalysts, selectedModel, startDate, endDate, onSubmit],
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Tickers */}
      <div>
        <label htmlFor="tickers" className="mb-1.5 block text-sm font-medium">
          Tickers
        </label>
        <input
          id="tickers"
          type="text"
          value={tickerInput}
          onChange={(e) => setTickerInput(e.target.value)}
          placeholder="AAPL, MSFT, GOOGL"
          disabled={disabled}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
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
                disabled && "pointer-events-none opacity-50",
              )}
            >
              <input
                type="checkbox"
                checked={selectedAnalysts.includes(analyst.key)}
                onChange={() => toggleAnalyst(analyst.key)}
                disabled={disabled}
                className="sr-only"
                data-testid={`analyst-${analyst.key}`}
              />
              {analyst.display_name}
            </label>
          ))}
        </div>
      </div>

      {/* Model */}
      <div>
        <label htmlFor="model" className="mb-1.5 block text-sm font-medium">
          Model
        </label>
        <select
          id="model"
          value={selectedModel}
          onChange={(e) => setSelectedModel(Number(e.target.value))}
          disabled={disabled}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {DEFAULT_MODELS.map((m, i) => (
            <option key={m.model_name} value={i}>
              {m.display_name} ({m.provider})
            </option>
          ))}
        </select>
      </div>

      {/* Date range */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="start-date" className="mb-1.5 block text-sm font-medium">
            Start Date
          </label>
          <input
            id="start-date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            disabled={disabled}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div>
          <label htmlFor="end-date" className="mb-1.5 block text-sm font-medium">
            End Date
          </label>
          <input
            id="end-date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            disabled={disabled}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={disabled}
        className={cn(
          "inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90",
          disabled && "pointer-events-none opacity-50",
        )}
      >
        <Play className="h-4 w-4" />
        Run Analysis
      </button>
    </form>
  );
}
