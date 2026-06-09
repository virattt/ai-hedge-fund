import { useState } from 'react';
import { History, Loader2, Play, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TickerLink } from '@/components/ui/ticker-link';
import { cn } from '@/lib/utils';
import {
  discoveryBacktestService,
  type BacktestMode,
  type BacktestResult,
} from '@/services/discovery-backtest-api';

const SOURCE_OPTIONS = [
  'spinoff', 'csuite_buy', 'squeeze', 'cluster_buy', 'analyst',
  'commodity_tailwind', 'insider_doubling_down', 'first_time_buyer',
  'mega_dollar_buy', 'repeat_buyer', 'relative_strength', 'contrarian_setup',
];

const PANEL_CLASS =
  'rounded-lg border border-primary/25 bg-card/60 backdrop-blur-md p-4 space-y-3 shadow-[0_4px_24px_hsl(210_55%_3%/0.35)]';

function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n == null) return '—';
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}%`;
}

function colourFor(n: number | null | undefined): string {
  if (n == null) return 'text-muted-foreground';
  if (n > 0) return 'text-primary';
  if (n < 0) return 'text-destructive';
  return 'text-muted-foreground';
}

export function BacktestPage() {
  const [mode, setMode] = useState<BacktestMode>('high_confluence');
  const [scoreThreshold, setScoreThreshold] = useState(60);
  const [minSources, setMinSources] = useState(3);
  const [sourceFilter, setSourceFilter] = useState<string>(SOURCE_OPTIONS[0]);
  const [sourceScoreThreshold, setSourceScoreThreshold] = useState(20);
  const [lookbackDays, setLookbackDays] = useState(90);
  const [holdDays, setHoldDays] = useState(30);

  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleRun = async () => {
    setLoading(true);
    try {
      const r = await discoveryBacktestService.run({
        mode,
        score_threshold: scoreThreshold,
        min_sources: minSources,
        source_filter: mode === 'source_threshold' ? sourceFilter : undefined,
        source_score_threshold: sourceScoreThreshold,
        lookback_days: lookbackDays,
        hold_days: holdDays,
      });
      setResult(r);
      if (r.total_triggers === 0) {
        toast.info('No triggers in this window — try widening lookback or loosening thresholds');
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Backtest failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      <div className="flex items-center gap-3">
        <History size={24} className="text-primary" />
        <h1 className="text-2xl font-bold text-foreground tracking-wide uppercase">Backtest Replay</h1>
      </div>
      <p className="text-sm text-muted-foreground max-w-3xl">
        Replays the current alert thresholds against the historical{' '}
        <code className="text-primary/90 font-data">discovery_snapshots</code> table — answers
        "had this rule been live X days ago, what tickers would it have flagged, and how did they perform?"
        Each ticker triggers at most once per run (earliest qualifying day).
        Returns approximate "held to today"; will be exact-to-hold-period once the trigger is older than hold_days.
      </p>
      <div className="hud-divider" />

      {/* Controls */}
      <section className={PANEL_CLASS}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wider text-muted-foreground">Mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as BacktestMode)}
              className="w-full bg-background border border-primary/30 rounded px-2 py-1.5 text-sm font-data"
            >
              <option value="score_threshold">Score ≥ N</option>
              <option value="high_confluence">High confluence (sources ≥ N AND score ≥ M)</option>
              <option value="source_threshold">Source X contributed ≥ Y</option>
            </select>
          </div>

          {(mode === 'score_threshold' || mode === 'high_confluence') && (
            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wider text-muted-foreground">Score threshold</label>
              <Input
                type="number"
                value={scoreThreshold}
                onChange={(e) => setScoreThreshold(parseFloat(e.target.value) || 0)}
                className="font-data"
              />
            </div>
          )}

          {mode === 'high_confluence' && (
            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wider text-muted-foreground">Min distinct sources</label>
              <Input
                type="number"
                value={minSources}
                min={1}
                onChange={(e) => setMinSources(parseInt(e.target.value) || 1)}
                className="font-data"
              />
            </div>
          )}

          {mode === 'source_threshold' && (
            <>
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Source</label>
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="w-full bg-background border border-primary/30 rounded px-2 py-1.5 text-sm font-data"
                >
                  {SOURCE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Source score ≥</label>
                <Input
                  type="number"
                  value={sourceScoreThreshold}
                  onChange={(e) => setSourceScoreThreshold(parseFloat(e.target.value) || 0)}
                  className="font-data"
                />
              </div>
            </>
          )}

          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wider text-muted-foreground">Lookback (days)</label>
            <Input
              type="number"
              min={1}
              max={365}
              value={lookbackDays}
              onChange={(e) => setLookbackDays(parseInt(e.target.value) || 1)}
              className="font-data"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wider text-muted-foreground">Hold (days)</label>
            <Input
              type="number"
              min={1}
              max={365}
              value={holdDays}
              onChange={(e) => setHoldDays(parseInt(e.target.value) || 1)}
              className="font-data"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <Button onClick={handleRun} disabled={loading} className="gap-1.5">
            {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            Run backtest
          </Button>
        </div>
      </section>

      {/* Results */}
      {result && (
        <>
          <section className={PANEL_CLASS}>
            <div className="flex items-center gap-2">
              <TrendingUp size={18} className="text-primary" />
              <h2 className="text-lg font-semibold text-foreground tracking-wide">Summary</h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-sm">
              <Stat label="Total triggers" value={result.total_triggers.toLocaleString()} />
              <Stat label="With returns" value={result.triggers_with_returns.toLocaleString()} hint="elapsed hold period" />
              <Stat label="Win rate" value={result.win_rate_pct == null ? '—' : `${result.win_rate_pct.toFixed(0)}%`} />
              <Stat label="Avg return" value={fmtPct(result.avg_return_pct)} colorByValue={result.avg_return_pct} />
              <Stat label="Median return" value={fmtPct(result.median_return_pct)} colorByValue={result.median_return_pct} />
              <Stat label="Avg alpha vs SPY" value={fmtPct(result.avg_alpha_pct)} colorByValue={result.avg_alpha_pct} />
              <Stat label="Best return" value={fmtPct(result.best_return_pct)} colorByValue={result.best_return_pct} />
              <Stat label="Worst return" value={fmtPct(result.worst_return_pct)} colorByValue={result.worst_return_pct} />
              <Stat label="Snapshots in window" value={result.snapshot_count_in_window.toLocaleString()} />
              <Stat label="Distinct tickers" value={result.distinct_tickers_in_window.toLocaleString()} />
            </div>
            {result.total_triggers === 0 && (
              <p className="text-sm text-muted-foreground italic">
                No qualifying triggers in {result.lookback_days}d window. Try widening lookback or loosening thresholds.
              </p>
            )}
            {result.total_triggers > 0 && result.triggers_with_returns === 0 && (
              <p className="text-xs text-amber-400 italic">
                Triggers found, but hold period hasn't elapsed yet — return stats will populate as time passes.
              </p>
            )}
          </section>

          {result.triggers.length > 0 && (
            <section className={PANEL_CLASS}>
              <div className="flex items-center gap-2">
                <TrendingUp size={18} className="text-primary" />
                <h2 className="text-lg font-semibold text-foreground tracking-wide">Triggers ({result.triggers.length})</h2>
              </div>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="uppercase text-[10px] tracking-wider">Ticker</TableHead>
                      <TableHead className="uppercase text-[10px] tracking-wider">Triggered</TableHead>
                      <TableHead className="uppercase text-[10px] tracking-wider text-right">Score</TableHead>
                      <TableHead className="uppercase text-[10px] tracking-wider text-right">Sources</TableHead>
                      <TableHead className="uppercase text-[10px] tracking-wider">Sources at trigger</TableHead>
                      <TableHead className="uppercase text-[10px] tracking-wider text-right">Entry</TableHead>
                      <TableHead className="uppercase text-[10px] tracking-wider text-right">Now</TableHead>
                      <TableHead className="uppercase text-[10px] tracking-wider text-right">Return</TableHead>
                      <TableHead className="uppercase text-[10px] tracking-wider text-right">Alpha</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.triggers.map((t) => (
                      <TableRow key={`${t.ticker}-${t.trigger_date}`}>
                        <TableCell><TickerLink ticker={t.ticker} /></TableCell>
                        <TableCell className="font-data text-xs text-muted-foreground">{t.trigger_date}</TableCell>
                        <TableCell className="font-data text-xs text-right font-semibold">{t.snapshot_score.toFixed(0)}</TableCell>
                        <TableCell className="font-data text-xs text-right">{t.distinct_sources_at_trigger}</TableCell>
                        <TableCell className="text-[10px] text-muted-foreground max-w-[260px] truncate" title={[...new Set(t.signal_sources)].join(', ')}>
                          {[...new Set(t.signal_sources)].join(', ') || '—'}
                        </TableCell>
                        <TableCell className="font-data text-xs text-right">
                          {t.entry_price != null ? `$${t.entry_price.toFixed(2)}` : '—'}
                        </TableCell>
                        <TableCell className="font-data text-xs text-right">
                          {t.exit_price != null ? `$${t.exit_price.toFixed(2)}` : '—'}
                        </TableCell>
                        <TableCell className={cn('font-data text-xs text-right font-semibold', colourFor(t.return_pct))}>
                          {fmtPct(t.return_pct)}
                        </TableCell>
                        <TableCell className={cn('font-data text-xs text-right', colourFor(t.alpha_pct))}>
                          {fmtPct(t.alpha_pct)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value, hint, colorByValue }: { label: string; value: string; hint?: string; colorByValue?: number | null }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn('font-data font-bold text-lg', colorByValue != null ? colourFor(colorByValue) : '')}>
        {value}
      </div>
      {hint && <div className="text-[9px] text-muted-foreground/60 italic">{hint}</div>}
    </div>
  );
}
