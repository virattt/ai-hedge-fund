const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

export type BacktestMode = 'score_threshold' | 'high_confluence' | 'source_threshold';

export interface BacktestParams {
  score_threshold: number;
  min_sources: number;
  source_filter: string | null;
  source_score_threshold: number;
}

export interface BacktestTrigger {
  ticker: string;
  trigger_date: string;
  snapshot_score: number;
  distinct_sources_at_trigger: number;
  signal_sources: string[];
  holding_period_days: number;
  entry_price: number | null;
  exit_price: number | null;
  return_pct: number | null;
  spy_return_pct: number | null;
  alpha_pct: number | null;
}

export interface BacktestResult {
  mode: BacktestMode;
  lookback_days: number;
  hold_days: number;
  params: BacktestParams;
  total_triggers: number;
  triggers_with_returns: number;
  win_rate_pct: number | null;
  avg_return_pct: number | null;
  median_return_pct: number | null;
  avg_alpha_pct: number | null;
  best_return_pct: number | null;
  worst_return_pct: number | null;
  snapshot_count_in_window: number;
  distinct_tickers_in_window: number;
  triggers: BacktestTrigger[];
}

export interface BacktestRunArgs {
  mode: BacktestMode;
  score_threshold?: number;
  min_sources?: number;
  source_filter?: string;
  source_score_threshold?: number;
  lookback_days?: number;
  hold_days?: number;
}

function extractDetail(body: unknown): string {
  if (!body || typeof body !== 'object') return '';
  const detail = (body as Record<string, unknown>).detail;
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((e) => (typeof e === 'string' ? e : (e?.msg ?? JSON.stringify(e)))).join('; ');
  }
  return JSON.stringify(detail);
}

class DiscoveryBacktestService {
  private baseUrl = `${API_BASE_URL}/backtest`;

  async run(args: BacktestRunArgs): Promise<BacktestResult> {
    const params = new URLSearchParams({ mode: args.mode });
    if (args.score_threshold != null) params.set('score_threshold', String(args.score_threshold));
    if (args.min_sources != null) params.set('min_sources', String(args.min_sources));
    if (args.source_filter) params.set('source_filter', args.source_filter);
    if (args.source_score_threshold != null) params.set('source_score_threshold', String(args.source_score_threshold));
    if (args.lookback_days != null) params.set('lookback_days', String(args.lookback_days));
    if (args.hold_days != null) params.set('hold_days', String(args.hold_days));

    const r = await fetch(`${this.baseUrl}/run?${params.toString()}`);
    if (!r.ok) {
      const body = await r.json().catch(() => null);
      throw new Error(extractDetail(body) || `Backtest failed: ${r.statusText}`);
    }
    return r.json();
  }
}

export const discoveryBacktestService = new DiscoveryBacktestService();
