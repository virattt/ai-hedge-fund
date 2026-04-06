import { Fragment, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, ChevronUp, Loader2, Search } from 'lucide-react';
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  insiderService,
  type InsiderDetailResponse,
  type InsiderFilingSummary,
  type InsiderSummaryResponse,
  type InsiderAggregates,
  type ActivityByDate,
} from '@/services/insider-api';
import { SubNavLink } from '@/components/insider/insider-sub-nav';
import { SkippedCountBanner } from '@/components/insider/skipped-count-banner';
import { InsiderOwnershipContent } from '@/components/insider/insider-ownership-content';
import { InsiderGrantsContent } from '@/components/insider/insider-grants-content';
import { InsiderThirteenFContent } from '@/components/insider/insider-thirteenf-content';
import { formatNumber, formatValue } from '@/utils/format';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type EdgarTab = 'filings' | 'ownership' | 'grants' | 'thirteenf';
type ActivityFilter = 'all' | 'purchases' | 'sales' | 'option_exercises' | 'discretionary';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const formatPercent = (n: number): string => `${(n * 100).toFixed(1)}%`;

const isPurchase = (f: InsiderFilingSummary): boolean =>
  f.primary_activity.toLowerCase() === 'purchase';

const isSale = (f: InsiderFilingSummary): boolean =>
  f.primary_activity.toLowerCase() === 'sale';

const isOptionExercise = (f: InsiderFilingSummary): boolean =>
  f.transaction_types.some((t) => t.toLowerCase().includes('exercise') || t.toLowerCase().includes('option'));

const isDiscretionary = (f: InsiderFilingSummary): boolean =>
  f.has_10b5_1_plan !== true;

const applyFilter = (filings: InsiderFilingSummary[], filter: ActivityFilter): InsiderFilingSummary[] => {
  switch (filter) {
    case 'purchases':
      return filings.filter(isPurchase);
    case 'sales':
      return filings.filter(isSale);
    case 'option_exercises':
      return filings.filter(isOptionExercise);
    case 'discretionary':
      return filings.filter(isDiscretionary);
    default:
      return filings;
  }
};

/**
 * Merge multiple InsiderSummaryResponse objects into a single combined response.
 * Filings are concatenated and sorted by filing_date descending.
 * Aggregates are recomputed from the merged set.
 */
function mergeResponses(responses: InsiderSummaryResponse[]): InsiderSummaryResponse {
  const allFilings: InsiderFilingSummary[] = [];
  let totalCount = 0;
  let totalSkipped = 0;
  let ticker = '';

  for (const resp of responses) {
    allFilings.push(...resp.filings);
    totalCount += resp.total;
    totalSkipped += resp.skipped_count;
    if (!ticker) ticker = resp.ticker;
  }

  // Sort by filing_date descending
  allFilings.sort((a, b) => b.filing_date.localeCompare(a.filing_date));

  // Merge aggregates
  const mergedAggregates = mergeAggregates(responses.map((r) => r.aggregates));

  return {
    ticker,
    form_type: '3,4,5',
    filings: allFilings,
    aggregates: mergedAggregates,
    total: totalCount,
    skipped_count: totalSkipped,
  };
}

function mergeAggregates(aggregates: InsiderAggregates[]): InsiderAggregates {
  let totalFilings = 0;
  let totalPurchases = 0;
  let totalSales = 0;
  let totalOther = 0;
  let plan10b51Count = 0;
  let largestValue: number | null = null;
  let largestInsider: string | null = null;

  const activityMap = new Map<string, ActivityByDate>();

  for (const agg of aggregates) {
    totalFilings += agg.total_filings;
    totalPurchases += agg.total_purchases;
    totalSales += agg.total_sales;
    totalOther += agg.total_other;
    plan10b51Count += agg.plan_10b5_1_count;

    if (agg.largest_transaction_value !== null) {
      if (largestValue === null || agg.largest_transaction_value > largestValue) {
        largestValue = agg.largest_transaction_value;
        largestInsider = agg.largest_transaction_insider;
      }
    }

    for (const entry of agg.activity_by_date) {
      const existing = activityMap.get(entry.date);
      if (existing) {
        existing.purchases += entry.purchases;
        existing.sales += entry.sales;
        existing.purchase_value += entry.purchase_value;
        existing.sale_value += entry.sale_value;
      } else {
        activityMap.set(entry.date, { ...entry });
      }
    }
  }

  const activityByDate = Array.from(activityMap.values()).sort((a, b) => a.date.localeCompare(b.date));

  return {
    total_filings: totalFilings,
    total_purchases: totalPurchases,
    total_sales: totalSales,
    total_other: totalOther,
    net_sentiment: totalPurchases - totalSales,
    largest_transaction_value: largestValue,
    largest_transaction_insider: largestInsider,
    plan_10b5_1_count: plan10b51Count,
    plan_10b5_1_ratio: totalFilings > 0 ? plan10b51Count / totalFilings : 0,
    activity_by_date: activityByDate,
  };
}

// ---------------------------------------------------------------------------
// Sortable table header
// ---------------------------------------------------------------------------

type FilingSortKey = keyof InsiderFilingSummary;
type SortDir = 'asc' | 'desc';

function compareFilings(a: InsiderFilingSummary, b: InsiderFilingSummary, key: FilingSortKey, dir: SortDir): number {
  const av = a[key];
  const bv = b[key];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  let cmp: number;
  if (typeof av === 'number' && typeof bv === 'number') {
    cmp = av - bv;
  } else if (typeof av === 'boolean' && typeof bv === 'boolean') {
    cmp = (av ? 1 : 0) - (bv ? 1 : 0);
  } else if (Array.isArray(av) && Array.isArray(bv)) {
    cmp = av.join(',').localeCompare(bv.join(','));
  } else {
    cmp = String(av).localeCompare(String(bv));
  }
  return dir === 'asc' ? cmp : -cmp;
}

interface SortableHeadProps {
  label: string;
  sortKey: FilingSortKey;
  activeKey: FilingSortKey | null;
  dir: SortDir;
  onSort: (key: FilingSortKey) => void;
  className?: string;
}

function SortableHead({ label, sortKey, activeKey, dir, onSort, className = '' }: SortableHeadProps) {
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
// Sub-components
// ---------------------------------------------------------------------------

function ActivityBadge({ activity }: { activity: string }) {
  const lower = activity.toLowerCase();
  if (lower === 'purchase') {
    return (
      <Badge variant="outline" className="text-green-600 border-green-600 whitespace-nowrap">
        Purchase
      </Badge>
    );
  }
  if (lower === 'sale') {
    return (
      <Badge variant="outline" className="text-red-600 border-red-600 whitespace-nowrap">
        Sale
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="whitespace-nowrap">
      {activity}
    </Badge>
  );
}

function SummaryCards({ data }: { data: InsiderSummaryResponse }) {
  const { aggregates } = data;

  const sentimentPositive = aggregates.net_sentiment >= 0;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {/* Net Insider Sentiment */}
      <Card>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-xs font-medium text-muted-foreground">Net Insider Sentiment</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className={`text-2xl font-bold ${sentimentPositive ? 'text-green-600' : 'text-red-600'}`}>
            {sentimentPositive ? '+' : ''}{aggregates.net_sentiment}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {aggregates.total_purchases} purchases &minus; {aggregates.total_sales} sales
          </p>
        </CardContent>
      </Card>

      {/* Largest Transaction */}
      <Card>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-xs font-medium text-muted-foreground">Largest Transaction</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className="text-2xl font-bold truncate">
            {formatValue(aggregates.largest_transaction_value)}
          </div>
          <p className="text-xs text-muted-foreground mt-1 truncate">
            {aggregates.largest_transaction_insider ?? '—'}
          </p>
        </CardContent>
      </Card>

      {/* 10b5-1 Plan Ratio */}
      <Card>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-xs font-medium text-muted-foreground">10b5-1 Plan Ratio</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className="text-2xl font-bold">{formatPercent(aggregates.plan_10b5_1_ratio)}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {aggregates.plan_10b5_1_count} of {aggregates.total_filings} filings
          </p>
        </CardContent>
      </Card>

      {/* Total Filings */}
      <Card>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-xs font-medium text-muted-foreground">Total Filings</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className="text-2xl font-bold">{aggregates.total_filings}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {data.total} total &middot; {data.skipped_count} skipped
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function ActivityChart({ data }: { data: InsiderSummaryResponse }) {
  const chartData = data.aggregates.activity_by_date;

  if (!chartData || chartData.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-4">
        <CardTitle className="text-sm font-medium">Buy / Sell Activity Over Time</CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
            <Tooltip
              formatter={(value: number, name: string) => [value, name === 'purchases' ? 'Purchases' : 'Sales']}
              labelFormatter={(label: string) => `Date: ${label}`}
            />
            <Bar dataKey="purchases" name="Purchases" fill="#16a34a" radius={[2, 2, 0, 0]} />
            <Bar dataKey="sales" name="Sales" fill="#dc2626" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

function DetailPanel({ detail, onClose }: { detail: InsiderDetailResponse; onClose: () => void }) {
  return (
    <div className="rounded-md border bg-muted/30 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-medium text-sm">{detail.insider_name}</span>
          <span className="text-xs text-muted-foreground ml-2">{detail.position}</span>
          <span className="text-xs text-muted-foreground ml-2">Filed {detail.filing_date}</span>
          <span className="text-xs text-muted-foreground ml-2">Accession: {detail.accession_no}</span>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>
      <div className="text-xs text-muted-foreground">
        {detail.market_trades_count} market trade{detail.market_trades_count !== 1 ? 's' : ''} &middot;&nbsp;
        {detail.derivative_trades_count} derivative trade{detail.derivative_trades_count !== 1 ? 's' : ''}
      </div>
      {detail.transactions.length > 0 && (
        <div className="rounded-md border overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Security</TableHead>
                <TableHead className="text-right">Shares</TableHead>
                <TableHead className="text-right">Price / Share</TableHead>
                <TableHead className="text-right">Value</TableHead>
                <TableHead>10b5-1</TableHead>
                <TableHead>Derivative</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.transactions.map((tx, i) => (
                <TableRow key={i}>
                  <TableCell className="text-xs">{tx.transaction_type}</TableCell>
                  <TableCell className="text-xs font-mono">{tx.code}</TableCell>
                  <TableCell className="text-xs">{tx.security_title ?? tx.security_type ?? '—'}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums">{formatNumber(tx.shares)}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums">
                    {tx.price_per_share !== null && tx.price_per_share !== undefined
                      ? `$${tx.price_per_share.toFixed(2)}`
                      : '—'}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums font-medium">
                    {formatValue(tx.value)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {tx.is_10b5_1_plan === true ? 'Yes' : tx.is_10b5_1_plan === false ? 'No' : '—'}
                  </TableCell>
                  <TableCell className="text-xs">{tx.is_derivative ? 'Yes' : 'No'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

const FILTER_OPTIONS: { value: ActivityFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'purchases', label: 'Purchases' },
  { value: 'sales', label: 'Sales' },
  { value: 'option_exercises', label: 'Option Exercises' },
  { value: 'discretionary', label: 'Discretionary Only' },
];

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-52 w-full rounded-xl" />
      <div className="space-y-2">
        <Skeleton className="h-8 w-72" />
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main InsiderPage
// ---------------------------------------------------------------------------

export function InsiderPage() {
  const [ticker, setTicker] = useState('');
  const [submittedTicker, setSubmittedTicker] = useState('');
  const [activeTab, setActiveTab] = useState<EdgarTab>('filings');
  const [data, setData] = useState<InsiderSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ActivityFilter>('all');

  // Form type visibility checkboxes
  const [showForm3, setShowForm3] = useState(true);
  const [showForm4, setShowForm4] = useState(true);
  const [showForm5, setShowForm5] = useState(true);

  // Column sorting
  const [sortKey, setSortKey] = useState<FilingSortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Per-row detail state: key = accession_no, value = detail response or loading sentinel
  const [detailMap, setDetailMap] = useState<Record<string, InsiderDetailResponse | 'loading' | 'error'>>({});
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const handleSearch = async (overrideTicker?: string) => {
    const tickerToUse = (overrideTicker ?? ticker).trim().toUpperCase();
    if (!tickerToUse) return;
    setLoading(true);
    setError(null);
    setData(null);
    setExpandedRow(null);
    setDetailMap({});
    setSubmittedTicker(tickerToUse);
    try {
      // Fire all 3 form type requests in parallel
      const results = await Promise.allSettled([
        insiderService.getSummary(tickerToUse, '3'),
        insiderService.getSummary(tickerToUse, '4'),
        insiderService.getSummary(tickerToUse, '5'),
      ]);

      const fulfilled: InsiderSummaryResponse[] = [];
      const errors: string[] = [];
      for (const r of results) {
        if (r.status === 'fulfilled') {
          fulfilled.push(r.value);
        } else {
          errors.push(r.reason instanceof Error ? r.reason.message : String(r.reason));
        }
      }

      if (fulfilled.length === 0) {
        setError(errors.join('; ') || 'Failed to fetch insider data');
      } else {
        setData(mergeResponses(fulfilled));
        // If some failed, we still show partial data but could note it
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch insider data');
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (newTab: string) => {
    setActiveTab(newTab as EdgarTab);
  };

  const handleRowClick = async (filing: InsiderFilingSummary) => {
    const key = filing.accession_no;
    if (expandedRow === key) {
      setExpandedRow(null);
      return;
    }
    setExpandedRow(key);
    if (detailMap[key]) return;

    setDetailMap((prev) => ({ ...prev, [key]: 'loading' }));
    try {
      const detail = await insiderService.getDetail(submittedTicker, filing.form_type, key);
      setDetailMap((prev) => ({ ...prev, [key]: detail }));
    } catch {
      setDetailMap((prev) => ({ ...prev, [key]: 'error' }));
    }
  };

  const handleSort = (key: FilingSortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const filteredFilings = useMemo(() => {
    if (!data) return [];
    // Apply form type filter
    const visibleForms = new Set<string>();
    if (showForm3) visibleForms.add('3');
    if (showForm4) visibleForms.add('4');
    if (showForm5) visibleForms.add('5');
    const formFiltered = data.filings.filter((f) => visibleForms.has(f.form_type));
    // Apply activity filter
    const activityFiltered = applyFilter(formFiltered, filter);
    // Apply sorting
    if (!sortKey) return activityFiltered;
    return [...activityFiltered].sort((a, b) => compareFilings(a, b, sortKey, sortDir));
  }, [data, filter, showForm3, showForm4, showForm5, sortKey, sortDir]);

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold">Edgar Insider</h1>
          <p className="text-sm text-muted-foreground">SEC insider trading filings (Form 3/4/5), ownership changes, and grants</p>
        </div>
        <div className="flex items-center gap-1">
          <SubNavLink to="/insider" label="Edgar Insider" />
          <SubNavLink to="/insider/openinsider" label="OpenInsider" />
        </div>
      </div>

      {/* Search bar */}
      <div className="flex gap-2 max-w-md">
        <Input
          placeholder="Enter ticker (e.g. AAPL)"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        />
        <Button onClick={() => handleSearch()} disabled={loading || !ticker.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Search
        </Button>
      </div>

      {/* Tabs: Filings | Ownership | Grants */}
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="filings">Filings</TabsTrigger>
          <TabsTrigger value="ownership">Ownership</TabsTrigger>
          <TabsTrigger value="grants">Grants</TabsTrigger>
          <TabsTrigger value="thirteenf">13-F</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Ownership tab content */}
      {activeTab === 'ownership' && (
        <InsiderOwnershipContent ticker={submittedTicker} />
      )}

      {/* Grants tab content */}
      {activeTab === 'grants' && (
        <InsiderGrantsContent ticker={submittedTicker} />
      )}

      {/* 13-F tab content */}
      {activeTab === 'thirteenf' && (
        <InsiderThirteenFContent />
      )}

      {/* Filings tab content */}
      {activeTab === 'filings' && (
        <>
          {/* Error */}
          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
          )}

          {/* Loading skeleton */}
          {loading && <LoadingSkeleton />}

          {/* Results */}
          {data && !loading && (
            <>
              {/* Summary cards */}
              <SummaryCards data={data} />

              {/* Activity chart */}
              <ActivityChart data={data} />

              {/* Skipped count notice */}
              <SkippedCountBanner
                skippedCount={data.skipped_count}
                shownCount={data.filings.length}
                totalCount={data.total}
                itemLabel="filings"
              />

              {/* Filter buttons + form type checkboxes */}
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex flex-wrap gap-1">
                  {FILTER_OPTIONS.map(({ value, label }) => (
                    <Button
                      key={value}
                      variant={filter === value ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setFilter(value)}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                <div className="flex items-center gap-3 ml-auto">
                  <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                    <Checkbox checked={showForm3} onCheckedChange={(v) => setShowForm3(!!v)} />
                    Form 3
                  </label>
                  <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                    <Checkbox checked={showForm4} onCheckedChange={(v) => setShowForm4(!!v)} />
                    Form 4
                  </label>
                  <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                    <Checkbox checked={showForm5} onCheckedChange={(v) => setShowForm5(!!v)} />
                    Form 5
                  </label>
                </div>
              </div>

              {/* Table */}
              {filteredFilings.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground text-sm">
                  No {filter === 'all' ? '' : filter.replace('_', ' ')} filings found for {data.ticker}.
                </div>
              ) : (
                <div className="rounded-md border overflow-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <SortableHead label="Filing Date" sortKey="filing_date" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="w-[100px]" />
                        <SortableHead label="Form" sortKey="form_type" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="w-[60px]" />
                        <SortableHead label="Insider Name" sortKey="insider_name" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableHead label="Position" sortKey="position" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableHead label="Primary Activity" sortKey="primary_activity" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableHead label="Net Change" sortKey="net_change" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                        <SortableHead label="Net Value" sortKey="net_value" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                        <SortableHead label="Remaining Shares" sortKey="remaining_shares" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                        <SortableHead label="10b5-1" sortKey="has_10b5_1_plan" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="w-[70px]" />
                        <TableHead>Transaction Types</TableHead>
                        <TableHead className="w-[30px]" />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredFilings.map((filing) => {
                        const isExpanded = expandedRow === filing.accession_no;
                        const detail = detailMap[filing.accession_no];
                        return (
                          <Fragment key={filing.accession_no}>
                            <TableRow
                              className="cursor-pointer hover:bg-accent/30"
                              onClick={() => handleRowClick(filing)}
                            >
                              <TableCell className="text-xs whitespace-nowrap">{filing.filing_date}</TableCell>
                              <TableCell>
                                <Badge variant="secondary" className="text-xs font-mono">
                                  {filing.form_type}
                                </Badge>
                              </TableCell>
                              <TableCell className="font-medium text-sm">{filing.insider_name}</TableCell>
                              <TableCell className="text-xs text-muted-foreground max-w-[140px] truncate">
                                {filing.position}
                              </TableCell>
                              <TableCell>
                                <ActivityBadge activity={filing.primary_activity} />
                              </TableCell>
                              <TableCell className={`text-right text-sm tabular-nums font-medium ${filing.net_change > 0 ? 'text-green-600' : filing.net_change < 0 ? 'text-red-600' : ''}`}>
                                {filing.net_change > 0 ? '+' : ''}{formatNumber(filing.net_change)}
                              </TableCell>
                              <TableCell className="text-right text-sm tabular-nums">
                                {formatValue(filing.net_value)}
                              </TableCell>
                              <TableCell className="text-right text-sm tabular-nums">
                                {formatNumber(filing.remaining_shares)}
                              </TableCell>
                              <TableCell className="text-xs text-center">
                                {filing.has_10b5_1_plan === true ? 'Yes' : filing.has_10b5_1_plan === false ? 'No' : '—'}
                              </TableCell>
                              <TableCell className="text-xs text-muted-foreground max-w-[180px] truncate">
                                {filing.transaction_types.join(', ')}
                              </TableCell>
                              <TableCell>
                                {isExpanded
                                  ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
                                  : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                              </TableCell>
                            </TableRow>

                            {/* Expandable detail row */}
                            {isExpanded && (
                              <TableRow>
                                <TableCell colSpan={11} className="p-3 bg-muted/10">
                                  {detail === 'loading' && (
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                                      <Loader2 className="h-4 w-4 animate-spin" />
                                      Loading transaction detail…
                                    </div>
                                  )}
                                  {detail === 'error' && (
                                    <div className="text-sm text-destructive py-2">
                                      Failed to load transaction detail for this filing.
                                    </div>
                                  )}
                                  {detail && detail !== 'loading' && detail !== 'error' && (
                                    <DetailPanel
                                      detail={detail}
                                      onClose={() => setExpandedRow(null)}
                                    />
                                  )}
                                </TableCell>
                              </TableRow>
                            )}
                          </Fragment>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </>
          )}

          {/* Empty state for filings tab */}
          {!data && !loading && !error && (
            <div className="text-center py-20 text-muted-foreground text-sm">
              Enter a ticker symbol and click Search to view insider trading activity.
            </div>
          )}
        </>
      )}
    </div>
  );
}
