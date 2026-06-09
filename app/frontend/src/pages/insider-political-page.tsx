import { useState, useMemo } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, ExternalLink, Loader2, Search } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TickerLink } from '@/components/ui/ticker-link';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { SubNavLink } from '@/components/insider/insider-sub-nav';
import {
  insiderService,
  type GovContract,
  type GovContractsResponse,
  type CongressTrade,
  type CongressTradesResponse,
} from '@/services/insider-api';
import { formatValue } from '@/utils/format';

type PoliticalTab = 'contracts' | 'congress';
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
// Gov Contracts Tab
// ---------------------------------------------------------------------------

type ContractSortKey = 'recipient_name' | 'award_amount' | 'awarding_agency' | 'start_date' | 'end_date';

function compareContracts(a: GovContract, b: GovContract, key: ContractSortKey, dir: SortDir): number {
  const av = a[key];
  const bv = b[key];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
  return dir === 'asc' ? cmp : -cmp;
}

function GovContractsTab() {
  const [data, setData] = useState<GovContractsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [sortKey, setSortKey] = useState<ContractSortKey | null>('award_amount');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    try {
      const selectionsResp = await insiderService.getThirteenFSelections();
      if (!selectionsResp.selections.length) {
        setError('No saved 13F company selections found. Go to the 13-F tab and save some companies first.');
        return;
      }
      const companyNames = selectionsResp.selections.map((s) => s.company);
      const result = await insiderService.getGovContracts(companyNames);
      setData(result);
      setHasLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch government contracts');
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (key: ContractSortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    if (!data) return [];
    if (!sortKey) return data.contracts;
    return [...data.contracts].sort((a, b) => compareContracts(a, b, sortKey, sortDir));
  }, [data, sortKey, sortDir]);

  return (
    <div className="space-y-4">
      {!hasLoaded && !loading && (
        <div className="text-center py-12 space-y-3">
          <p className="text-muted-foreground text-sm">
            View government contract awards for your saved 13F company selections.
            <br />
            <span className="text-xs">Data from the USA Spending API — free, no API key needed.</span>
          </p>
          <Button onClick={handleLoad}>
            <Search className="h-4 w-4 mr-1" />
            Load Contracts
          </Button>
        </div>
      )}

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {loading && (
        <div className="flex items-center gap-2 py-8 justify-center text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Fetching government contract data...
        </div>
      )}

      {data && !loading && (
        <>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>{data.total} contracts</span>
            {data.cached && <Badge variant="secondary" className="text-xs">Cached</Badge>}
            <Button variant="outline" size="sm" onClick={handleLoad}>Refresh</Button>
          </div>

          {sorted.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              No government contracts found for the selected companies.
            </div>
          ) : (
            <div className="rounded-md border overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <SortableHead label="Recipient" sortKey="recipient_name" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortableHead label="Award Amount" sortKey="award_amount" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortableHead label="Agency" sortKey="awarding_agency" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortableHead label="Start Date" sortKey="start_date" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortableHead label="End Date" sortKey="end_date" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                    <TableHead>Description</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sorted.map((c, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium text-sm max-w-[200px] truncate">{c.recipient_name ?? '—'}</TableCell>
                      <TableCell className="text-right text-sm tabular-nums font-medium">{formatValue(c.award_amount)}</TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[180px] truncate">{c.awarding_agency ?? '—'}</TableCell>
                      <TableCell className="text-xs whitespace-nowrap">{c.start_date ?? '—'}</TableCell>
                      <TableCell className="text-xs whitespace-nowrap">{c.end_date ?? '—'}</TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[250px] truncate">{c.description ?? '—'}</TableCell>
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
// Congressional Trades Tab
// ---------------------------------------------------------------------------

type CongressSortKey = 'representative' | 'ticker' | 'transaction_type' | 'amount' | 'transaction_date' | 'disclosure_date';

function compareCongress(a: CongressTrade, b: CongressTrade, key: CongressSortKey, dir: SortDir): number {
  const av = a[key];
  const bv = b[key];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const cmp = String(av).localeCompare(String(bv));
  return dir === 'asc' ? cmp : -cmp;
}

function CongressTradesTab() {
  const [ticker, setTicker] = useState('');
  const [data, setData] = useState<CongressTradesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<CongressSortKey | null>('transaction_date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await insiderService.getCongressTrades(ticker.trim().toUpperCase() || undefined);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch congressional trades');
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (key: CongressSortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    if (!data) return [];
    if (!sortKey) return data.trades;
    return [...data.trades].sort((a, b) => compareCongress(a, b, sortKey, sortDir));
  }, [data, sortKey, sortDir]);

  const txBadge = (type: string | null) => {
    if (!type) return <span className="text-muted-foreground">—</span>;
    const lower = type.toLowerCase();
    if (lower.includes('purchase')) return <Badge className="bg-primary/20 text-primary border-primary/30 text-xs">{type}</Badge>;
    if (lower.includes('sale')) return <Badge className="bg-destructive/20 text-destructive border-destructive/30 text-xs">{type}</Badge>;
    return <Badge variant="secondary" className="text-xs">{type}</Badge>;
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2 max-w-lg">
        <Input
          placeholder="Optional ticker filter (e.g. AAPL)"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleLoad()}
        />
        <Button onClick={handleLoad} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Load Trades
        </Button>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {loading && (
        <div className="flex items-center gap-2 py-8 justify-center text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Fetching congressional trading data...
        </div>
      )}

      {data && !loading && (
        <>
          {!data.source_available ? (
            <Card className="border-primary/30 bg-primary/5">
              <CardContent className="py-8 text-center space-y-3">
                <p className="text-sm font-medium">House Stock Watcher data is currently unavailable</p>
                <p className="text-xs text-muted-foreground">
                  The S3 data source may be temporarily blocked. You can view disclosures directly:
                </p>
                <a
                  href="https://disclosures-clerk.house.gov/PublicDisclosure/FinancialDisclosure"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
                >
                  House Financial Disclosures <ExternalLink className="h-3 w-3" />
                </a>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>{data.total} trades{data.total > 500 ? ' (showing top 500)' : ''}</span>
                {data.cached && <Badge variant="secondary" className="text-xs">Cached</Badge>}
                <Button variant="outline" size="sm" onClick={handleLoad}>Refresh</Button>
              </div>

              {sorted.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground text-sm">
                  No congressional trades found{ticker ? ` for ${ticker}` : ''}.
                </div>
              ) : (
                <div className="rounded-md border overflow-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <SortableHead label="Representative" sortKey="representative" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableHead label="Ticker" sortKey="ticker" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableHead label="Type" sortKey="transaction_type" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableHead label="Amount" sortKey="amount" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableHead label="Transaction Date" sortKey="transaction_date" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableHead label="Disclosure Date" sortKey="disclosure_date" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                        <TableHead>District</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sorted.map((t, i) => (
                        <TableRow key={i}>
                          <TableCell className="font-medium text-sm">{t.representative ?? '—'}</TableCell>
                          <TableCell><TickerLink ticker={t.ticker} /></TableCell>
                          <TableCell>{txBadge(t.transaction_type)}</TableCell>
                          <TableCell className="text-xs whitespace-nowrap">{t.amount ?? '—'}</TableCell>
                          <TableCell className="text-xs whitespace-nowrap">{t.transaction_date ?? '—'}</TableCell>
                          <TableCell className="text-xs whitespace-nowrap">{t.disclosure_date ?? '—'}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">{t.district ?? '—'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </>
          )}
        </>
      )}

      {!data && !loading && !error && (
        <div className="text-center py-16 text-muted-foreground text-sm">
          Search for congressional stock trades. Leave ticker empty to load all recent trades.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main InsiderPoliticalPage
// ---------------------------------------------------------------------------

export function InsiderPoliticalPage() {
  const [activeTab, setActiveTab] = useState<PoliticalTab>('contracts');

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-wide uppercase">Political &amp; Policy</h1>
          <p className="text-sm text-muted-foreground">
            Government contracts and congressional stock trades for policy-driven alpha
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

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as PoliticalTab)}>
        <TabsList>
          <TabsTrigger value="contracts">Gov Contracts</TabsTrigger>
          <TabsTrigger value="congress">Congressional Trades</TabsTrigger>
        </TabsList>
      </Tabs>

      {activeTab === 'contracts' && <GovContractsTab />}
      {activeTab === 'congress' && <CongressTradesTab />}
    </div>
  );
}
