import { useState, useMemo } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, Loader2, Search } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TickerLink } from '@/components/ui/ticker-link';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { SubNavLink } from '@/components/insider/insider-sub-nav';
import {
  insiderService,
  type ShortInterestResponse,
  type SqueezeCandidate,
  type SqueezeScreenerResponse,
} from '@/services/insider-api';
import { formatNumber, formatValue } from '@/utils/format';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type FinnhubTab = 'short_interest' | 'squeeze';
type SqueezeSortKey = keyof SqueezeCandidate;
type SortDir = 'asc' | 'desc';

// ---------------------------------------------------------------------------
// Generic sortable header
// ---------------------------------------------------------------------------

interface SortableHeadProps<K> {
  label: string;
  sortKey: K;
  activeKey: K | null;
  dir: SortDir;
  onSort: (key: K) => void;
  className?: string;
}

function SortableHead<K>({ label, sortKey, activeKey, dir, onSort, className = '' }: SortableHeadProps<K>) {
  const active = activeKey === sortKey;
  return (
    <TableHead
      className={`cursor-pointer select-none hover:bg-muted/50 ${className}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active ? (
          dir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-30" />
        )}
      </span>
    </TableHead>
  );
}

// ---------------------------------------------------------------------------
// Sort comparator
// ---------------------------------------------------------------------------

function compareSqueeze(a: SqueezeCandidate, b: SqueezeCandidate, key: SqueezeSortKey, dir: SortDir): number {
  const av = a[key];
  const bv = b[key];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
  return dir === 'asc' ? cmp : -cmp;
}

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------

const formatPercent = (n: number | null | undefined): string => {
  if (n === null || n === undefined) return '—';
  return `${n.toFixed(2)}%`;
};

const formatRatio = (n: number | null | undefined): string => {
  if (n === null || n === undefined) return '—';
  return n.toFixed(2);
};

// ---------------------------------------------------------------------------
// Short Interest Tab — single ticker lookup with summary cards
// ---------------------------------------------------------------------------

function ShortInterestTab() {
  const [symbol, setSymbol] = useState('');
  const [data, setData] = useState<ShortInterestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await insiderService.getShortInterest(sym);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch short interest data');
    } finally {
      setLoading(false);
    }
  };

  const si = data?.data;

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="flex gap-2 max-w-md">
        <Input
          placeholder="Enter ticker (e.g. AAPL)"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        />
        <Button onClick={handleSearch} disabled={loading || !symbol.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Search
        </Button>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {loading && (
        <div className="flex items-center gap-2 py-8 justify-center text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading short interest data...
        </div>
      )}

      {data && !loading && (
        <>
          {data.cached && (
            <Badge variant="secondary" className="text-xs">Cached</Badge>
          )}

          {si ? (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <Card>
                <CardHeader className="pb-2 pt-4 px-4">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Symbol</CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4">
                  <div className="text-2xl font-bold">{data.symbol}</div>
                  <p className="text-xs text-muted-foreground mt-1">Yahoo Finance</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2 pt-4 px-4">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Short % of Float</CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4">
                  <div className={`text-2xl font-bold ${(si.short_pct_float ?? 0) > 20 ? 'text-destructive' : (si.short_pct_float ?? 0) > 10 ? 'text-foreground' : 'text-foreground'}`}>
                    {formatPercent(si.short_pct_float)}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">The squeeze signal</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2 pt-4 px-4">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Days to Cover</CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4">
                  <div className={`text-2xl font-bold ${(si.days_to_cover ?? 0) > 5 ? 'text-destructive' : 'text-foreground'}`}>
                    {formatRatio(si.days_to_cover)}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">How trapped shorts are</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2 pt-4 px-4">
                  <CardTitle className="text-xs font-medium text-muted-foreground">Shares Short</CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4">
                  <div className="text-2xl font-bold">
                    {formatNumber(si.shares_short)}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Float: {si.float_shares ? formatNumber(Math.round(si.float_shares)) : '—'}
                  </p>
                </CardContent>
              </Card>
            </div>
          ) : (
            <Card className="border-primary/30 bg-primary/5">
              <CardContent className="py-8 text-center space-y-2">
                <p className="text-sm font-medium">No short interest data available for {data.symbol}</p>
                <p className="text-xs text-muted-foreground">
                  The ticker may not be found or Finnhub may not have metrics for this symbol.
                </p>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {!data && !loading && !error && (
        <div className="text-center py-20 text-muted-foreground text-sm">
          Enter a ticker symbol to view short interest metrics from Yahoo Finance.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Squeeze Screener Tab
// ---------------------------------------------------------------------------

function SqueezeScreenerTab() {
  const [data, setData] = useState<SqueezeScreenerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SqueezeSortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [hasLoaded, setHasLoaded] = useState(false);

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await insiderService.getSqueezeScreener();
      setData(result);
      setHasLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch squeeze screener');
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (key: SqueezeSortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sortedCandidates = useMemo(() => {
    if (!data) return [];
    if (!sortKey) return data.candidates;
    return [...data.candidates].sort((a, b) => compareSqueeze(a, b, sortKey, sortDir));
  }, [data, sortKey, sortDir]);

  return (
    <div className="space-y-4">
      {!hasLoaded && !loading && (
        <div className="text-center py-12 space-y-3">
          <p className="text-muted-foreground text-sm">
            Find stocks with high short interest that insiders are buying — potential squeeze candidates.
            <br />
            <span className="text-xs">Cross-references OpenInsider cluster buys with Finnhub short interest data.</span>
          </p>
          <Button onClick={handleLoad}>
            <Search className="h-4 w-4 mr-1" />
            Load Squeeze Screener
          </Button>
        </div>
      )}

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {loading && (
        <div className="flex items-center gap-2 py-8 justify-center text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Fetching insider buys and cross-referencing with short interest data...
        </div>
      )}

      {data && !loading && (
        <>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>{data.total} candidates</span>
            <Button variant="outline" size="sm" onClick={handleLoad}>
              Refresh
            </Button>
          </div>

          {sortedCandidates.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              No squeeze candidates found.
            </div>
          ) : (
            <div className="rounded-md border overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <SortableHead label="Ticker" sortKey="ticker" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortableHead label="Company" sortKey="company_name" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortableHead label="Short Float %" sortKey="short_pct_float" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortableHead label="Days to Cover" sortKey="days_to_cover" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortableHead label="Shares Short" sortKey="shares_short" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortableHead label="Insider Buys" sortKey="insider_buy_count" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortableHead label="Buy Value" sortKey="insider_buy_value" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortableHead label="Latest Buy" sortKey="latest_insider_buy_date" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedCandidates.map((c, i) => (
                    <TableRow key={i} className={c.insider_buy_count > 0 ? 'bg-primary/5' : ''}>
                      <TableCell><TickerLink ticker={c.ticker} /></TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">{c.company_name}</TableCell>
                      <TableCell className={`text-right text-sm tabular-nums font-medium ${(c.short_pct_float ?? 0) > 20 ? 'text-destructive' : (c.short_pct_float ?? 0) > 10 ? 'text-foreground' : ''}`}>
                        {formatPercent(c.short_pct_float)}
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {formatRatio(c.days_to_cover)}
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {formatNumber(c.shares_short)}
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {c.insider_buy_count > 0 ? (
                          <span className="text-primary font-medium">{c.insider_buy_count}</span>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {c.insider_buy_value > 0 ? (
                          <span className="text-primary">{formatValue(c.insider_buy_value)}</span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs whitespace-nowrap">
                        {c.latest_insider_buy_date ?? '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main InsiderFinnhubPage
// ---------------------------------------------------------------------------

export function InsiderFinnhubPage() {
  const [activeTab, setActiveTab] = useState<FinnhubTab>('short_interest');

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-wide uppercase">Short Interest</h1>
          <p className="text-sm text-muted-foreground">
            Short interest metrics and squeeze screener powered by Yahoo Finance
          </p>
        </div>
        <div className="flex items-center gap-1">
          <SubNavLink to="/insider" label="Edgar Insider" />
          <SubNavLink to="/insider/openinsider" label="OpenInsider" />
          <SubNavLink to="/insider/finnhub" label="Finnhub" />
          <SubNavLink to="/insider/political" label="Political" />
          <SubNavLink to="/insider/earnings" label="Earnings" />
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as FinnhubTab)}>
        <TabsList>
          <TabsTrigger value="short_interest">Short Interest</TabsTrigger>
          <TabsTrigger value="squeeze">Squeeze Screener</TabsTrigger>
        </TabsList>
      </Tabs>

      {activeTab === 'short_interest' && <ShortInterestTab />}
      {activeTab === 'squeeze' && <SqueezeScreenerTab />}
    </div>
  );
}
