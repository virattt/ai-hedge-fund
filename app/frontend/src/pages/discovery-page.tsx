import { useEffect, useMemo, useState } from 'react';
import { Compass, ExternalLink, Loader2, RefreshCw, Star } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TickerLink } from '@/components/ui/ticker-link';
import { useWatchlist } from '@/contexts/watchlist-context';
import { discoveryService, type DiscoveryIdea, type IdeaSignal } from '@/services/discovery-api';
import { cn } from '@/lib/utils';

const HIGH_CONFLUENCE_MIN_SOURCES = 4;
const HIGH_CONFLUENCE_MIN_SCORE = 80;

type StrategyKey = 'all' | 'rockets' | 'compounders' | 'deep_value';

// Each preset filters to ideas that include at least one signal from the
// listed sources. "All" passes everything through unfiltered.
const STRATEGY_SOURCES: Record<Exclude<StrategyKey, 'all'>, Set<string>> = {
  rockets: new Set([
    'spinoff', 'squeeze', 'cluster_buy', 'mega_dollar_buy',
    'insider_doubling_down', 'first_time_buyer', 'repeat_buyer',
    'csuite_buy', 'revenue_acceleration', 'commodity_tailwind',
    'relative_strength', 'activist_13d', 'contrarian_setup',
  ]),
  compounders: new Set([
    'quality_score', 'high_roic', 'dividend_grower', 'analyst', 'csuite_buy',
  ]),
  deep_value: new Set([
    'valuation_score', 'fcf_yield', 'contrarian_setup',
  ]),
};

const STRATEGY_TABS: { key: StrategyKey; label: string; title: string }[] = [
  { key: 'all', label: 'All', title: 'No source filter — every idea above SINGLE tier' },
  { key: 'rockets', label: '🚀 Rockets', title: 'Catalyst-driven momentum: insider clusters, spinoffs, squeezes, revenue inflection' },
  { key: 'compounders', label: '🐢 Compounders', title: 'Quality businesses to hold: high ROIC, durable margins, dividend growth, analyst upgrades' },
  { key: 'deep_value', label: '💎 Deep Value', title: 'Cheap businesses with insider validation: low PEG, high FCF yield, contrarian setups' },
];

interface ConfluenceTier {
  label: string;
  className: string;
  rowClassName: string;
}

function distinctSources(idea: DiscoveryIdea): number {
  return new Set(idea.signals.map((s) => s.source)).size;
}

function confluenceTier(idea: DiscoveryIdea): ConfluenceTier {
  const sources = distinctSources(idea);
  if (sources >= HIGH_CONFLUENCE_MIN_SOURCES && idea.score >= HIGH_CONFLUENCE_MIN_SCORE) {
    return {
      label: '🚨 SUPER-NOVA',
      className: 'border-destructive bg-destructive/20 text-destructive font-bold animate-pulse',
      rowClassName: 'bg-destructive/5 border-l-2 border-l-destructive',
    };
  }
  if (sources >= 3) {
    return {
      label: 'TRIPLE',
      className: 'border-primary/60 bg-primary/15 text-primary font-semibold',
      rowClassName: '',
    };
  }
  if (sources >= 2) {
    return {
      label: 'DOUBLE',
      className: 'border-primary/30 bg-primary/5 text-primary/80',
      rowClassName: '',
    };
  }
  return {
    label: 'SINGLE',
    className: 'border-muted-foreground/20 bg-muted/30 text-muted-foreground',
    rowClassName: '',
  };
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

export function DiscoveryPage() {
  const { isWatched, toggle } = useWatchlist();
  const [ideas, setIdeas] = useState<DiscoveryIdea[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [cached, setCached] = useState(false);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [dontChase, setDontChase] = useState(false);
  const [strategy, setStrategy] = useState<StrategyKey>('all');

  const load = async (filterEnabled = dontChase) => {
    setLoading(true);
    setError(null);
    try {
      const r = await discoveryService.getIdeas(50, filterEnabled ? 20 : undefined);
      setIdeas(r.ideas);
      setGeneratedAt(r.generated_at);
      setCached(r.cached);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load ideas');
    } finally {
      setLoading(false);
    }
  };

  const toggleDontChase = async () => {
    const next = !dontChase;
    setDontChase(next);
    await load(next);
  };

  useEffect(() => {
    load();
  }, []);

  const handleStarTopN = async (n: number = 10) => {
    setBulkLoading(true);
    let added = 0;
    let skippedCik = 0;
    let alreadyWatched = 0;

    for (const idea of ideas.slice(0, 30)) {
      if (added >= n) break;
      if (!idea.is_ticker) {
        skippedCik += 1;
        continue;
      }
      const t = idea.ticker.toUpperCase();
      if (isWatched(t)) {
        alreadyWatched += 1;
        continue;
      }
      try {
        await toggle(t);
        added += 1;
      } catch {
        // Continue with next
      }
    }
    setBulkLoading(false);

    const parts: string[] = [`Added ${added} to watchlist`];
    if (alreadyWatched > 0) parts.push(`${alreadyWatched} already watched`);
    if (skippedCik > 0) parts.push(`${skippedCik} CIK-only (no ticker yet)`);
    toast.success(parts.join(' · '));
  };

  const sortedIdeas = useMemo(
    () => [...ideas].sort((a, b) => b.score - a.score),
    [ideas],
  );

  const filteredIdeas = useMemo(() => {
    if (strategy === 'all') return sortedIdeas;
    const required = STRATEGY_SOURCES[strategy];
    return sortedIdeas.filter((idea) =>
      idea.signals.some((s) => required.has(s.source)),
    );
  }, [sortedIdeas, strategy]);

  const tickerCount = useMemo(() => ideas.filter((i) => i.is_ticker).length, [ideas]);

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Compass size={22} className="text-primary" />
            <h1 className="text-2xl font-bold text-foreground tracking-wide uppercase">Discovery</h1>
            <span className="text-[10px] font-data uppercase tracking-widest text-primary/70">
              // {ideas.length} ranked idea{ideas.length === 1 ? '' : 's'}
              {generatedAt && ` · generated ${new Date(generatedAt).toLocaleTimeString()}`}
              {cached && ' · cached'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={dontChase ? 'default' : 'outline'}
              size="sm"
              onClick={toggleDontChase}
              disabled={loading}
              className="gap-1.5"
              title={dontChase
                ? 'Showing only ideas within +20% of best whale entry price'
                : "Don't chase: hide ideas trading >20% above the best whale entry"}
            >
              🐋 Don't chase
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleStarTopN(10)}
              disabled={bulkLoading || tickerCount === 0}
              className="gap-1.5"
              title="Add the top 10 ticker-bearing ideas to your watchlist"
            >
              {bulkLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Star className="h-3 w-3" />}
              Star top 10
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => load()}
              disabled={loading}
              className="gap-1.5"
            >
              {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
              Refresh
            </Button>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          Ranked feed of tickers with active signals across spin-offs, C-suite insider buys, and squeeze setups.
          Click ⭐ to track. Click ticker to analyze.
        </p>
        <div className="hud-divider" />
      </div>

      {error && (
        <div className="border border-destructive/40 bg-destructive/10 text-destructive px-4 py-3 rounded-md text-sm">
          {error}
        </div>
      )}

      {!loading && ideas.length === 0 && !error && (
        <div className="border border-primary/30 bg-primary/5 text-foreground px-4 py-6 rounded-md text-sm space-y-1">
          <p className="font-medium">No ideas in the feed yet.</p>
          <p className="text-muted-foreground">
            Discovery aggregates from Catalysts (spin-offs), insider Form 4 buys, and short-squeeze candidates.
            Make sure <span className="font-data text-primary">FINNHUB_API_KEY</span>, <span className="font-data text-primary">EDGAR_IDENTITY</span>,
            and the spin-off sync are configured.
          </p>
        </div>
      )}

      {/* Strategy tabs */}
      {sortedIdeas.length > 0 && (
        <div className="flex items-center gap-1 border-b border-primary/25 -mb-px">
          {STRATEGY_TABS.map(({ key, label, title }) => {
            const active = strategy === key;
            const count = key === 'all'
              ? sortedIdeas.length
              : sortedIdeas.filter((i) => i.signals.some((s) => STRATEGY_SOURCES[key].has(s.source))).length;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setStrategy(key)}
                title={title}
                className={cn(
                  'px-3 py-1.5 text-sm font-data tracking-wide border-b-2 transition-colors',
                  active
                    ? 'border-primary text-primary font-semibold'
                    : 'border-transparent text-muted-foreground hover:text-foreground',
                )}
              >
                {label}
                <span className="ml-1.5 text-[10px] text-muted-foreground/70">({count})</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Table */}
      {sortedIdeas.length > 0 && (
        <div className="border border-primary/25 bg-card/60 backdrop-blur-md rounded-md overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="uppercase text-xs tracking-wider w-12">Rank</TableHead>
                <TableHead className="uppercase text-xs tracking-wider w-28">Tier</TableHead>
                <TableHead className="uppercase text-xs tracking-wider w-32">Ticker</TableHead>
                <TableHead className="uppercase text-xs tracking-wider">Company</TableHead>
                <TableHead className="uppercase text-xs tracking-wider w-20 text-right">Score</TableHead>
                <TableHead className="uppercase text-xs tracking-wider w-24 text-right">30d / α</TableHead>
                <TableHead className="uppercase text-xs tracking-wider w-24 text-right">vs Whale</TableHead>
                <TableHead className="uppercase text-xs tracking-wider">Signals</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredIdeas.map((idea, idx) => {
                const watched = idea.is_ticker && isWatched(idea.ticker);
                const tier = confluenceTier(idea);
                return (
                  <TableRow
                    key={`${idea.ticker}-${idx}`}
                    className={cn(watched && 'opacity-60', tier.rowClassName)}
                  >
                    <TableCell className="font-data text-sm text-muted-foreground">#{idx + 1}</TableCell>
                    <TableCell>
                      <span className={cn('inline-flex items-center font-data text-[10px] uppercase tracking-wider px-2 py-0.5 rounded border whitespace-nowrap', tier.className)}>
                        {tier.label}
                      </span>
                    </TableCell>
                    <TableCell>
                      {idea.is_ticker ? (
                        <TickerLink ticker={idea.ticker} />
                      ) : (
                        <Link
                          to="/catalysts"
                          className="inline-flex items-center gap-1 text-primary text-xs font-data hover:underline"
                          title={`Spin-off entity (no ticker yet) — view in Catalysts`}
                        >
                          CIK {idea.cik} <ExternalLink className="h-3 w-3" />
                        </Link>
                      )}
                    </TableCell>
                    <TableCell className="text-sm font-medium text-muted-foreground max-w-[300px] truncate" title={idea.company || ''}>
                      {idea.company || '—'}
                    </TableCell>
                    <TableCell className="font-data text-base text-right text-primary font-bold">
                      {Math.round(idea.score)}
                    </TableCell>
                    <TableCell className="text-right font-data text-xs">
                      {idea.return_30d_pct == null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <div className="flex flex-col items-end">
                          <span className={cn(
                            'font-semibold',
                            idea.return_30d_pct > 0 ? 'text-primary' : idea.return_30d_pct < 0 ? 'text-destructive' : 'text-muted-foreground',
                          )}>
                            {idea.return_30d_pct > 0 ? '+' : ''}{idea.return_30d_pct.toFixed(1)}%
                          </span>
                          {idea.alpha_30d_pct != null && (
                            <span className={cn(
                              'text-[10px]',
                              idea.alpha_30d_pct > 0 ? 'text-primary/80' : idea.alpha_30d_pct < 0 ? 'text-destructive/80' : 'text-muted-foreground',
                            )}>
                              {idea.alpha_30d_pct > 0 ? '+' : ''}{idea.alpha_30d_pct.toFixed(1)} α
                            </span>
                          )}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-data text-xs">
                      {idea.distance_from_whale_entry_pct == null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <span className={cn(
                          'font-semibold',
                          idea.distance_from_whale_entry_pct <= 0 ? 'text-primary'
                            : idea.distance_from_whale_entry_pct <= 20 ? 'text-primary/70'
                            : 'text-destructive',
                        )} title={`Current price vs lowest whale entry`}>
                          {idea.distance_from_whale_entry_pct > 0 ? '+' : ''}{idea.distance_from_whale_entry_pct.toFixed(0)}%
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {idea.signals.map(signalBadge)}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
