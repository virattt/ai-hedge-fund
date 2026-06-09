import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Anchor, ArrowLeft, ChartBar, ExternalLink, FileText, Flame, Loader2, RefreshCw, Search, Star, TrendingDown, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useWatchlist } from '@/contexts/watchlist-context';
import { discoveryService, type DiscoveryIdea, type IdeaSignal } from '@/services/discovery-api';
import { insiderService, type InsiderSummaryResponse, type ShortInterestResponse } from '@/services/insider-api';
import { watchlistService, type WatchlistItem } from '@/services/watchlist-api';
import { whaleService, type TickerWhaleSummary } from '@/services/whale-api';
import { cn } from '@/lib/utils';

const HIGH_CONFLUENCE_MIN_SOURCES = 4;
const HIGH_CONFLUENCE_MIN_SCORE = 80;

interface ConfluenceTier {
  label: string;
  className: string;
}

function distinctSourceCount(signals: IdeaSignal[]): number {
  return new Set(signals.map((s) => s.source)).size;
}

function confluenceTier(signals: IdeaSignal[], score: number): ConfluenceTier {
  const sources = distinctSourceCount(signals);
  if (sources >= HIGH_CONFLUENCE_MIN_SOURCES && score >= HIGH_CONFLUENCE_MIN_SCORE) {
    return { label: '🚨 SUPER-NOVA', className: 'border-destructive bg-destructive/20 text-destructive font-bold animate-pulse' };
  }
  if (sources >= 3) {
    return { label: 'TRIPLE', className: 'border-primary/60 bg-primary/15 text-primary font-semibold' };
  }
  if (sources >= 2) {
    return { label: 'DOUBLE', className: 'border-primary/30 bg-primary/5 text-primary/80' };
  }
  return { label: 'SINGLE', className: 'border-muted-foreground/20 bg-muted/30 text-muted-foreground' };
}

function signalBadge(s: IdeaSignal) {
  const cls =
    s.source === 'spinoff' ? 'border-primary/40 bg-primary/10 text-primary'
    : s.source === 'csuite_buy' ? 'border-amber-500/40 bg-amber-500/10 text-amber-400'
    : s.source === 'squeeze' ? 'border-destructive/40 bg-destructive/10 text-destructive'
    : s.source === 'cluster_buy' ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
    : s.source === 'analyst' ? 'border-purple-500/40 bg-purple-500/10 text-purple-400'
    : s.source === 'commodity_tailwind' ? 'border-orange-500/40 bg-orange-500/10 text-orange-400'
    : s.source === 'insider_doubling_down' ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-400'
    : s.source === 'first_time_buyer' ? 'border-pink-500/40 bg-pink-500/10 text-pink-400'
    : s.source === 'mega_dollar_buy' ? 'border-yellow-500/40 bg-yellow-500/10 text-yellow-400'
    : s.source === 'repeat_buyer' ? 'border-teal-500/40 bg-teal-500/10 text-teal-400'
    : s.source === 'relative_strength' ? 'border-indigo-500/40 bg-indigo-500/10 text-indigo-400'
    : s.source === 'contrarian_setup' ? 'border-rose-500/40 bg-rose-500/10 text-rose-400 font-semibold'
    : s.source === 'activist_13d' ? 'border-fuchsia-500/40 bg-fuchsia-500/10 text-fuchsia-400 font-semibold'
    : s.source === 'revenue_acceleration' ? 'border-lime-500/40 bg-lime-500/10 text-lime-400 font-semibold'
    : s.source === 'quality_score' ? 'border-sky-500/40 bg-sky-500/10 text-sky-400'
    : s.source === 'valuation_score' ? 'border-green-500/40 bg-green-500/10 text-green-400'
    : s.source === 'dividend_grower' ? 'border-violet-500/40 bg-violet-500/10 text-violet-400'
    : s.source === 'fcf_yield' ? 'border-blue-500/40 bg-blue-500/10 text-blue-400 font-semibold'
    : s.source === 'high_roic' ? 'border-stone-400/40 bg-stone-400/10 text-stone-300 font-semibold'
    : 'border-border bg-muted text-muted-foreground';
  return (
    <span
      key={`${s.source}-${s.label}`}
      className={cn('inline-flex items-center font-data text-[10px] uppercase tracking-wider px-2 py-0.5 rounded border', cls)}
      title={`${s.source}: +${s.score}`}
    >
      {s.label} <span className="opacity-60 ml-1">+{s.score}</span>
    </span>
  );
}

function sentimentColor(sentiment: string | null | undefined): string {
  if (!sentiment) return 'text-muted-foreground';
  const s = sentiment.toLowerCase();
  if (s === 'bullish') return 'text-primary';
  if (s === 'bearish') return 'text-destructive';
  return 'text-muted-foreground';
}

function deltaIcon(direction: string | null | undefined) {
  if (direction === 'improving') return <TrendingUp className="h-4 w-4 text-primary" />;
  if (direction === 'deteriorating') return <TrendingDown className="h-4 w-4 text-destructive" />;
  return null;
}

function formatMoney(n: number | null | undefined): string {
  if (n == null) return '—';
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function formatPercent(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${n.toFixed(1)}%`;
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  const seconds = Math.floor((Date.now() - then) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

const SECTION_CLASS =
  'rounded-lg border border-primary/25 bg-card/60 backdrop-blur-md p-4 space-y-3 shadow-[0_4px_24px_hsl(210_55%_3%/0.35)]';

export function TickerDetailPage() {
  const params = useParams<{ ticker: string }>();
  const navigate = useNavigate();
  const ticker = (params.ticker ?? '').toUpperCase().replace(/[^A-Z0-9.\-]/g, '');

  const { isWatched, toggle } = useWatchlist();

  const [discoveryIdea, setDiscoveryIdea] = useState<DiscoveryIdea | null>(null);
  const [discoveryLoading, setDiscoveryLoading] = useState(true);

  const [shortInterest, setShortInterest] = useState<ShortInterestResponse | null>(null);
  const [shortInterestLoading, setShortInterestLoading] = useState(true);
  const [shortInterestError, setShortInterestError] = useState<string | null>(null);

  const [insiderSummary, setInsiderSummary] = useState<InsiderSummaryResponse | null>(null);
  const [insiderLoading, setInsiderLoading] = useState(true);
  const [insiderError, setInsiderError] = useState<string | null>(null);

  const [watchlistItem, setWatchlistItem] = useState<WatchlistItem | null>(null);
  const [watchlistLoading, setWatchlistLoading] = useState(true);

  const [whaleSummary, setWhaleSummary] = useState<TickerWhaleSummary | null>(null);
  const [whaleLoading, setWhaleLoading] = useState(true);

  const watched = isWatched(ticker);

  // Discovery — find this ticker in the ranked list
  useEffect(() => {
    if (!ticker) return;
    setDiscoveryLoading(true);
    discoveryService
      .getIdeas(200)
      .then((res) => {
        const found = res.ideas.find((i) => i.is_ticker && i.ticker.toUpperCase() === ticker);
        setDiscoveryIdea(found ?? null);
      })
      .catch(() => setDiscoveryIdea(null))
      .finally(() => setDiscoveryLoading(false));
  }, [ticker]);

  // Short interest
  useEffect(() => {
    if (!ticker) return;
    setShortInterestLoading(true);
    setShortInterestError(null);
    insiderService
      .getShortInterest(ticker)
      .then((r) => setShortInterest(r))
      .catch((e) => setShortInterestError(e instanceof Error ? e.message : 'Short interest fetch failed'))
      .finally(() => setShortInterestLoading(false));
  }, [ticker]);

  // Insider Form 4 summary
  useEffect(() => {
    if (!ticker) return;
    setInsiderLoading(true);
    setInsiderError(null);
    insiderService
      .getSummary(ticker, '4', 20, 0)
      .then((r) => setInsiderSummary(r))
      .catch((e) => setInsiderError(e instanceof Error ? e.message : 'Insider summary fetch failed'))
      .finally(() => setInsiderLoading(false));
  }, [ticker]);

  // Watchlist item with cached sentiment snapshot
  useEffect(() => {
    if (!ticker) return;
    setWatchlistLoading(true);
    watchlistService
      .list()
      .then((res) => {
        const found = res.items.find((i) => i.ticker.toUpperCase() === ticker);
        setWatchlistItem(found ?? null);
      })
      .catch(() => setWatchlistItem(null))
      .finally(() => setWatchlistLoading(false));
  }, [ticker]);

  // Whale entries for this ticker
  useEffect(() => {
    if (!ticker) return;
    setWhaleLoading(true);
    whaleService
      .getTickerSummary(ticker)
      .then((res) => setWhaleSummary(res))
      .catch(() => setWhaleSummary(null))
      .finally(() => setWhaleLoading(false));
  }, [ticker]);

  const handleToggleWatch = async () => {
    try {
      const nowWatched = await toggle(ticker);
      toast.success(nowWatched ? `Added ${ticker} to watchlist` : `Removed ${ticker} from watchlist`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Watchlist update failed');
    }
  };

  const goAnalyze = () => {
    navigate(`/insider/earnings?ticker=${encodeURIComponent(ticker)}&autoRun=1`);
  };

  const refreshSentiment = async () => {
    if (!watched) {
      toast.info('Add the ticker to your watchlist first');
      return;
    }
    try {
      const updated = await watchlistService.refreshOne(ticker);
      setWatchlistItem(updated);
      toast.success(`Refreshed ${ticker}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Refresh failed');
    }
  };

  const tier = useMemo(() => {
    if (!discoveryIdea) return null;
    return confluenceTier(discoveryIdea.signals, discoveryIdea.score);
  }, [discoveryIdea]);

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="space-y-2">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="gap-1.5 text-muted-foreground">
          <ArrowLeft className="h-3 w-3" /> Back
        </Button>

        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3 flex-wrap">
            <button
              type="button"
              onClick={handleToggleWatch}
              className="inline-flex items-center justify-center p-1.5 rounded-md hover:bg-accent/50 transition-colors"
              title={watched ? `Remove ${ticker} from watchlist` : `Add ${ticker} to watchlist`}
            >
              <Star className={cn('h-5 w-5', watched ? 'fill-primary text-primary' : 'text-muted-foreground/40')} />
            </button>
            <h1 className="text-3xl font-bold text-foreground tracking-wider uppercase font-data">{ticker}</h1>
            {discoveryIdea?.company && (
              <span className="text-sm text-muted-foreground">{discoveryIdea.company}</span>
            )}
            {tier && (
              <span className={cn('inline-flex items-center font-data text-[10px] uppercase tracking-wider px-2 py-0.5 rounded border whitespace-nowrap', tier.className)}>
                {tier.label}
              </span>
            )}
            {discoveryIdea && (
              <span className="font-data text-base text-primary font-bold">
                Score {Math.round(discoveryIdea.score)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={goAnalyze} className="gap-1.5">
              <Search className="h-3 w-3" /> Analyze Earnings
            </Button>
          </div>
        </div>
        <div className="hud-divider" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Section: Discovery Signals */}
        <section className={cn(SECTION_CLASS, 'lg:col-span-2')}>
          <div className="flex items-center gap-2">
            <Flame size={16} className="text-primary" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">Discovery Signals</h2>
          </div>
          {discoveryLoading ? (
            <div className="text-sm text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin inline-block mr-2" />Loading…</div>
          ) : discoveryIdea ? (
            <div className="space-y-2">
              <div className="flex flex-wrap gap-1">
                {discoveryIdea.signals.map(signalBadge)}
              </div>
              <p className="text-xs text-muted-foreground font-data">
                {discoveryIdea.signals.length} signal{discoveryIdea.signals.length === 1 ? '' : 's'} ·
                {' '}{distinctSourceCount(discoveryIdea.signals)} distinct source{distinctSourceCount(discoveryIdea.signals) === 1 ? '' : 's'} ·
                {' '}composite score {Math.round(discoveryIdea.score)}
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              No active Discovery signals for {ticker} right now.
            </p>
          )}
        </section>

        {/* Section: Watchlist sentiment */}
        <section className={SECTION_CLASS}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-primary" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">Earnings Sentiment</h2>
            </div>
            {watched && (
              <Button variant="ghost" size="sm" onClick={refreshSentiment} className="gap-1.5 h-7 text-xs">
                <RefreshCw className="h-3 w-3" /> Refresh
              </Button>
            )}
          </div>
          {watchlistLoading ? (
            <div className="text-sm text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin inline-block mr-2" />Loading…</div>
          ) : watchlistItem && watchlistItem.last_overall_sentiment ? (
            <div className="space-y-2">
              <div className="flex items-center gap-3 flex-wrap">
                <span className={cn('font-semibold uppercase tracking-wider text-sm', sentimentColor(watchlistItem.last_overall_sentiment))}>
                  {watchlistItem.last_overall_sentiment}
                </span>
                {watchlistItem.last_delta_direction && (
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    {deltaIcon(watchlistItem.last_delta_direction)}
                    <span className="capitalize">{watchlistItem.last_delta_direction}</span>
                  </span>
                )}
              </div>
              {watchlistItem.last_management_tone && (
                <p className="text-xs text-muted-foreground italic">"{watchlistItem.last_management_tone}"</p>
              )}
              <p className="text-[10px] font-data text-muted-foreground">
                Last analyzed: {timeAgo(watchlistItem.last_analyzed_at)}
              </p>
            </div>
          ) : watched ? (
            <p className="text-sm text-muted-foreground italic">
              Watched but not yet analyzed. Click Refresh or Analyze Earnings.
            </p>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              ⭐ Add to watchlist to track sentiment shifts via the daily batch, or click "Analyze Earnings" for a one-off run.
            </p>
          )}
        </section>

        {/* Section: Short interest */}
        <section className={SECTION_CLASS}>
          <div className="flex items-center gap-2">
            <ChartBar size={16} className="text-primary" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">Short Interest</h2>
          </div>
          {shortInterestLoading ? (
            <div className="text-sm text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin inline-block mr-2" />Loading…</div>
          ) : shortInterestError ? (
            <p className="text-xs text-destructive">{shortInterestError}</p>
          ) : shortInterest?.data ? (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">% of float</div>
                <div className="font-data font-bold text-lg">{formatPercent(shortInterest.data.short_pct_float)}</div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Days to cover</div>
                <div className="font-data font-bold text-lg">{shortInterest.data.days_to_cover?.toFixed(1) ?? '—'}</div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Shares short</div>
                <div className="font-data text-sm">{shortInterest.data.shares_short?.toLocaleString() ?? '—'}</div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Float</div>
                <div className="font-data text-sm">{shortInterest.data.float_shares?.toLocaleString() ?? '—'}</div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground italic">No short interest data available.</p>
          )}
        </section>

        {/* Section: Insider Form 4 */}
        <section className={cn(SECTION_CLASS, 'lg:col-span-2')}>
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-primary" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">Recent Insider Form 4</h2>
            {insiderSummary && (
              <span className="text-[10px] font-data text-muted-foreground">
                {insiderSummary.total} filings
              </span>
            )}
          </div>
          {insiderLoading ? (
            <div className="text-sm text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin inline-block mr-2" />Loading…</div>
          ) : insiderError ? (
            <p className="text-xs text-destructive">{insiderError}</p>
          ) : insiderSummary && insiderSummary.filings.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="uppercase text-[10px] tracking-wider">Filed</TableHead>
                    <TableHead className="uppercase text-[10px] tracking-wider">Insider</TableHead>
                    <TableHead className="uppercase text-[10px] tracking-wider">Title</TableHead>
                    <TableHead className="uppercase text-[10px] tracking-wider text-right">Net Change</TableHead>
                    <TableHead className="uppercase text-[10px] tracking-wider text-right">Net Value</TableHead>
                    <TableHead className="uppercase text-[10px] tracking-wider w-12">Doc</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {insiderSummary.filings.slice(0, 10).map((f) => (
                    <TableRow key={f.accession_no}>
                      <TableCell className="font-data text-xs">{f.filing_date}</TableCell>
                      <TableCell className="text-xs font-medium">{f.insider_name || '—'}</TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate" title={f.position || ''}>
                        {f.position || '—'}
                      </TableCell>
                      <TableCell className={cn('font-data text-xs text-right', f.net_change > 0 && 'text-primary', f.net_change < 0 && 'text-destructive')}>
                        {f.net_change.toLocaleString()}
                      </TableCell>
                      <TableCell className={cn('font-data text-xs text-right', (f.net_value ?? 0) > 0 && 'text-primary', (f.net_value ?? 0) < 0 && 'text-destructive')}>
                        {formatMoney(f.net_value)}
                      </TableCell>
                      <TableCell>
                        <a
                          href={`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${ticker}&type=4&dateb=&owner=include&count=10`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline inline-flex items-center"
                          title="Open Form 4 filings on SEC EDGAR"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground italic">No recent Form 4 filings for {ticker}.</p>
          )}
        </section>

        {/* Section: Whale entries */}
        <section className={cn(SECTION_CLASS, 'lg:col-span-2')}>
          <div className="flex items-center gap-2">
            <Anchor size={16} className="text-primary" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">Whale Entries</h2>
            {whaleSummary && whaleSummary.whale_count > 0 && (
              <span className="text-[10px] font-data text-muted-foreground">
                {whaleSummary.whale_count} {whaleSummary.whale_count === 1 ? 'whale holds' : 'whales hold'} this
              </span>
            )}
            {whaleSummary && whaleSummary.distance_from_best_entry_pct != null && (
              <span className={cn(
                'inline-flex items-center font-data text-[10px] uppercase tracking-wider px-2 py-0.5 rounded border whitespace-nowrap',
                whaleSummary.distance_from_best_entry_pct <= 0
                  ? 'border-primary/50 bg-primary/15 text-primary font-semibold'
                  : whaleSummary.distance_from_best_entry_pct <= 20
                    ? 'border-primary/30 bg-primary/5 text-primary/80'
                    : 'border-destructive/50 bg-destructive/15 text-destructive font-semibold',
              )}>
                {whaleSummary.distance_from_best_entry_pct > 0 ? '+' : ''}
                {whaleSummary.distance_from_best_entry_pct.toFixed(0)}% vs best entry
              </span>
            )}
          </div>
          {whaleLoading ? (
            <div className="text-sm text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin inline-block mr-2" />Loading…</div>
          ) : whaleSummary && whaleSummary.entries.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="uppercase text-[10px] tracking-wider">Whale</TableHead>
                    <TableHead className="uppercase text-[10px] tracking-wider">Entry Quarter</TableHead>
                    <TableHead className="uppercase text-[10px] tracking-wider text-right">Entry VWAP</TableHead>
                    <TableHead className="uppercase text-[10px] tracking-wider text-right">Q Low → High</TableHead>
                    <TableHead className="uppercase text-[10px] tracking-wider text-right">Shares</TableHead>
                    <TableHead className="uppercase text-[10px] tracking-wider text-right">vs Current</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {whaleSummary.entries.map((e) => {
                    const distance = (whaleSummary.current_price && e.entry_vwap && e.entry_vwap > 0)
                      ? (whaleSummary.current_price / e.entry_vwap - 1) * 100
                      : null;
                    return (
                      <TableRow key={`${e.whale_cik}-${e.entry_period_end ?? ''}`}>
                        <TableCell className="text-xs font-medium">
                          {e.whale_name}
                          {e.is_pre_lookback && (
                            <span className="ml-1 text-[9px] text-muted-foreground" title="Position predates lookback window">≥3y</span>
                          )}
                        </TableCell>
                        <TableCell className="font-data text-xs text-muted-foreground">{e.entry_quarter_label || '—'}</TableCell>
                        <TableCell className="font-data text-xs text-right">
                          {e.entry_vwap != null ? `$${e.entry_vwap.toFixed(2)}` : '—'}
                        </TableCell>
                        <TableCell className="font-data text-[10px] text-right text-muted-foreground">
                          {(e.entry_low != null && e.entry_high != null)
                            ? `$${e.entry_low.toFixed(2)} → $${e.entry_high.toFixed(2)}`
                            : '—'}
                        </TableCell>
                        <TableCell className="font-data text-xs text-right text-muted-foreground">
                          {e.share_count_at_entry != null ? e.share_count_at_entry.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '—'}
                        </TableCell>
                        <TableCell className={cn(
                          'font-data text-xs text-right font-semibold',
                          distance == null ? 'text-muted-foreground'
                            : distance <= 0 ? 'text-primary'
                            : distance <= 20 ? 'text-primary/70'
                            : 'text-destructive',
                        )}>
                          {distance == null ? '—' : `${distance > 0 ? '+' : ''}${distance.toFixed(0)}%`}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
              {whaleSummary.current_price && (
                <p className="text-[10px] font-data text-muted-foreground mt-2">
                  Current price ≈ ${whaleSummary.current_price.toFixed(2)} · entries approximated as volume-weighted typical price over the filing quarter.
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              No tracked whale holds {ticker}. Add more whales on the Settings page, or refresh whale entries.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
