import { useEffect, useMemo, useState } from 'react';
import { Loader2, Minus, RefreshCw, Star, TrendingDown, TrendingUp, X } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TickerLink } from '@/components/ui/ticker-link';
import { useWatchlist } from '@/contexts/watchlist-context';
import { watchlistService, type WatchlistItem } from '@/services/watchlist-api';
import { cn } from '@/lib/utils';

function timeAgo(iso: string | null): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  const seconds = Math.floor((Date.now() - then) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function sentimentBadge(sentiment: string | null) {
  if (!sentiment) return <span className="text-muted-foreground">—</span>;
  const s = sentiment.toLowerCase();
  const cls =
    s === 'bullish' ? 'text-primary border-primary/30 bg-primary/10'
    : s === 'bearish' ? 'text-destructive border-destructive/30 bg-destructive/10'
    : 'text-muted-foreground border-border bg-muted';
  return (
    <span className={cn('inline-flex items-center font-data text-[10px] uppercase tracking-wider px-2 py-0.5 rounded border', cls)}>
      {s}
    </span>
  );
}

function deltaIcon(direction: string | null) {
  if (!direction) return <span className="text-muted-foreground">—</span>;
  if (direction === 'improving') return (
    <span className="inline-flex items-center gap-1 text-primary text-xs">
      <TrendingUp className="h-3 w-3" /> improving
    </span>
  );
  if (direction === 'deteriorating') return (
    <span className="inline-flex items-center gap-1 text-destructive text-xs">
      <TrendingDown className="h-3 w-3" /> deteriorating
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground text-xs">
      <Minus className="h-3 w-3" /> stable
    </span>
  );
}

export function WatchlistPage() {
  const { refresh: refreshContext } = useWatchlist();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshingTicker, setRefreshingTicker] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await watchlistService.list();
      setItems(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load watchlist');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleRunBatch = async () => {
    setScanning(true);
    try {
      const r = await watchlistService.runBatch();
      toast.success(`Batch done: ${r.succeeded}/${r.analyzed} succeeded${r.failed ? ` · ${r.failed} failed` : ''}`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Batch failed');
    } finally {
      setScanning(false);
    }
  };

  const handleRefresh = async (ticker: string) => {
    setRefreshingTicker(ticker);
    try {
      const updated = await watchlistService.refreshOne(ticker);
      setItems((prev) => prev.map((i) => (i.ticker === ticker ? updated : i)));
      toast.success(`Refreshed ${ticker}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : `Refresh failed for ${ticker}`);
    } finally {
      setRefreshingTicker(null);
    }
  };

  const handleRemove = async (ticker: string) => {
    try {
      await watchlistService.remove(ticker);
      setItems((prev) => prev.filter((i) => i.ticker !== ticker));
      await refreshContext();
      toast.success(`Removed ${ticker}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : `Remove failed`);
    }
  };

  const sortedItems = useMemo(
    () => [...items].sort((a, b) => a.ticker.localeCompare(b.ticker)),
    [items],
  );

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Star size={22} className="text-primary fill-primary" />
            <h1 className="text-2xl font-bold text-foreground tracking-wide uppercase">Watchlist</h1>
            <span className="text-[10px] font-data uppercase tracking-widest text-primary/70">
              // {items.length} ticker{items.length === 1 ? '' : 's'}
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRunBatch}
            disabled={scanning || items.length === 0}
            className="gap-1.5"
          >
            {scanning ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
            Refresh all
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          Saved tickers with automatic daily sentiment refresh. Direction shifts (improving / deteriorating) trigger
          alerts via the <span className="text-primary">earnings_sentiment_shift</span> rule.
        </p>
        <div className="hud-divider" />
      </div>

      {/* Error */}
      {error && (
        <div className="border border-destructive/40 bg-destructive/10 text-destructive px-4 py-3 rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="border border-primary/25 bg-card/60 backdrop-blur-md rounded-md overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="uppercase text-xs tracking-wider">Ticker</TableHead>
              <TableHead className="uppercase text-xs tracking-wider">Sentiment</TableHead>
              <TableHead className="uppercase text-xs tracking-wider">Trend</TableHead>
              <TableHead className="uppercase text-xs tracking-wider text-right">Return / Alpha</TableHead>
              <TableHead className="uppercase text-xs tracking-wider text-right">vs Whale</TableHead>
              <TableHead className="uppercase text-xs tracking-wider">Mgmt Tone</TableHead>
              <TableHead className="uppercase text-xs tracking-wider">Last Analyzed</TableHead>
              <TableHead className="uppercase text-xs tracking-wider w-24">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-12 text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin inline-block mr-2" />
                  Loading watchlist...
                </TableCell>
              </TableRow>
            ) : sortedItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-12 text-muted-foreground">
                  <p>No tickers in your watchlist yet.</p>
                  <p className="text-xs mt-2">Click the <Star className="inline h-3 w-3 text-primary" /> next to any ticker on Screener / News / OpenInsider / etc. to add it.</p>
                </TableCell>
              </TableRow>
            ) : (
              sortedItems.map((item) => (
                <TableRow key={item.ticker}>
                  <TableCell>
                    <TickerLink ticker={item.ticker} hideStar />
                  </TableCell>
                  <TableCell>{sentimentBadge(item.last_overall_sentiment)}</TableCell>
                  <TableCell>{deltaIcon(item.last_delta_direction)}</TableCell>
                  <TableCell className="text-right font-data text-xs">
                    {item.return_pct_since_added == null ? (
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      <div className="flex flex-col items-end">
                        <span className={cn(
                          'font-semibold',
                          item.return_pct_since_added > 0 ? 'text-primary' : item.return_pct_since_added < 0 ? 'text-destructive' : 'text-muted-foreground',
                        )}>
                          {item.return_pct_since_added > 0 ? '+' : ''}{item.return_pct_since_added.toFixed(1)}%
                        </span>
                        {item.alpha_pct_vs_spy != null && (
                          <span className={cn(
                            'text-[10px]',
                            item.alpha_pct_vs_spy > 0 ? 'text-primary/80' : item.alpha_pct_vs_spy < 0 ? 'text-destructive/80' : 'text-muted-foreground',
                          )}>
                            {item.alpha_pct_vs_spy > 0 ? '+' : ''}{item.alpha_pct_vs_spy.toFixed(1)} vs SPY
                          </span>
                        )}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-right font-data text-xs">
                    {item.distance_from_whale_entry_pct == null ? (
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      <span className={cn(
                        'font-semibold',
                        item.distance_from_whale_entry_pct <= 0 ? 'text-primary'
                          : item.distance_from_whale_entry_pct <= 20 ? 'text-primary/70'
                          : 'text-destructive',
                      )} title="Current price vs lowest whale entry">
                        {item.distance_from_whale_entry_pct > 0 ? '+' : ''}{item.distance_from_whale_entry_pct.toFixed(0)}%
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate" title={item.last_management_tone || ''}>
                    {item.last_management_tone || '—'}
                  </TableCell>
                  <TableCell className="text-xs font-data text-muted-foreground">
                    {timeAgo(item.last_analyzed_at)}
                    {item.last_error && (
                      <div className="text-[10px] text-destructive/80 mt-0.5 max-w-[160px] truncate" title={item.last_error}>
                        err: {item.last_error}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={() => handleRefresh(item.ticker)}
                        disabled={refreshingTicker === item.ticker}
                        title="Re-run analysis"
                      >
                        {refreshingTicker === item.ticker ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3 w-3" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 hover:text-destructive"
                        onClick={() => handleRemove(item.ticker)}
                        title="Remove from watchlist"
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
