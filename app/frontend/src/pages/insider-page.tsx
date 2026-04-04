import { Fragment, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronDown, ChevronUp, Loader2, Search } from 'lucide-react';
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
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  insiderService,
  type InsiderDetailResponse,
  type InsiderFilingSummary,
  type InsiderSummaryResponse,
} from '@/services/insider-api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type FormType = '4' | '3' | '5';
type ActivityFilter = 'all' | 'purchases' | 'sales' | 'option_exercises' | 'discretionary';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const formatNumber = (n: number | null | undefined): string => {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
};

const formatValue = (n: number | null | undefined): string => {
  if (n === null || n === undefined) return '—';
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

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
// Sub-page stubs
// ---------------------------------------------------------------------------

export function InsiderGrantsPage() {
  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Grants &amp; Exercises</h1>
        <p className="text-sm text-muted-foreground">
          Derivative trades, option grants and exercises from SEC filings.
        </p>
      </div>
      <div className="text-center py-20 text-muted-foreground text-sm">
        This sub-page is coming soon.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-nav link helper
// ---------------------------------------------------------------------------

function SubNavLink({ to, label }: { to: string; label: string }) {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link
      to={to}
      className={`text-sm px-3 py-1 rounded-md transition-colors ${
        isActive
          ? 'bg-accent text-accent-foreground font-medium'
          : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
      }`}
    >
      {label}
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Main InsiderPage
// ---------------------------------------------------------------------------

export function InsiderPage() {
  const [ticker, setTicker] = useState('');
  const [submittedTicker, setSubmittedTicker] = useState('');
  const [formType, setFormType] = useState<FormType>('4');
  const [data, setData] = useState<InsiderSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ActivityFilter>('all');

  // Per-row detail state: key = accession_no, value = detail response or loading sentinel
  const [detailMap, setDetailMap] = useState<Record<string, InsiderDetailResponse | 'loading' | 'error'>>({});
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const handleSearch = async (overrideTicker?: string, overrideFormType?: FormType) => {
    const tickerToUse = (overrideTicker ?? ticker).trim().toUpperCase();
    if (!tickerToUse) return;
    const formTypeToUse = overrideFormType ?? formType;
    setLoading(true);
    setError(null);
    setData(null);
    setExpandedRow(null);
    setDetailMap({});
    setSubmittedTicker(tickerToUse);
    try {
      const result = await insiderService.getSummary(tickerToUse, formTypeToUse);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch insider data');
    } finally {
      setLoading(false);
    }
  };

  const handleFormTypeChange = (newFormType: string) => {
    const ft = newFormType as FormType;
    setFormType(ft);
    if (submittedTicker) {
      handleSearch(submittedTicker, ft);
    }
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
      const detail = await insiderService.getDetail(submittedTicker, formType, key);
      setDetailMap((prev) => ({ ...prev, [key]: detail }));
    } catch {
      setDetailMap((prev) => ({ ...prev, [key]: 'error' }));
    }
  };

  const filteredFilings = data ? applyFilter(data.filings, filter) : [];

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold">Insiders</h1>
          <p className="text-sm text-muted-foreground">SEC insider trading filings (Form 3/4/5)</p>
        </div>
        <div className="flex items-center gap-1">
          <SubNavLink to="/insider" label="Dashboard" />
          <SubNavLink to="/insider/ownership" label="Ownership" />
          <SubNavLink to="/insider/grants" label="Grants" />
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

      {/* Form type tabs */}
      <Tabs value={formType} onValueChange={handleFormTypeChange}>
        <TabsList>
          <TabsTrigger value="4">Form 4</TabsTrigger>
          <TabsTrigger value="3">Form 3</TabsTrigger>
          <TabsTrigger value="5">Form 5</TabsTrigger>
        </TabsList>
      </Tabs>

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
          {data.skipped_count > 0 && (
            <div className="rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-400">
              Showing {data.filings.length} of {data.total} filings ({data.skipped_count} could not be parsed)
            </div>
          )}

          {/* Filter buttons */}
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
                    <TableHead className="w-[100px]">Filing Date</TableHead>
                    <TableHead>Insider Name</TableHead>
                    <TableHead>Position</TableHead>
                    <TableHead>Primary Activity</TableHead>
                    <TableHead className="text-right">Net Change</TableHead>
                    <TableHead className="text-right">Net Value</TableHead>
                    <TableHead className="text-right">Remaining Shares</TableHead>
                    <TableHead className="w-[70px]">10b5-1</TableHead>
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
                            <TableCell colSpan={10} className="p-3 bg-muted/10">
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

      {/* Empty state */}
      {!data && !loading && !error && (
        <div className="text-center py-20 text-muted-foreground text-sm">
          Enter a ticker symbol and click Search to view insider trading activity.
        </div>
      )}
    </div>
  );
}
