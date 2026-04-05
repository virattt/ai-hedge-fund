import { useState, useMemo } from 'react';
import { Loader2, Search } from 'lucide-react';
import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  insiderService,
  type OwnershipChangeRecord,
  type OwnershipChangesResponse,
} from '@/services/insider-api';
import { SubNavLink } from '@/components/insider/insider-sub-nav';
import { SkippedCountBanner } from '@/components/insider/skipped-count-banner';
import { formatNumber } from '@/utils/format';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Generate a stable color for a given index. */
const LINE_COLORS = ['#2563eb', '#16a34a', '#dc2626', '#d97706', '#7c3aed'];
const lineColor = (index: number): string => LINE_COLORS[index % LINE_COLORS.length];

// ---------------------------------------------------------------------------
// Position History Line Chart
// ---------------------------------------------------------------------------

/**
 * Build chart data from ownership records. Each data point is indexed by
 * filing_date. Columns are the top-N insiders by record count.
 */
function buildChartData(
  records: OwnershipChangeRecord[],
  topInsiders: string[]
): Record<string, string | number>[] {
  // Group by filing_date, then by insider name
  const byDate: Map<string, Map<string, number>> = new Map();

  for (const rec of records) {
    if (!topInsiders.includes(rec.insider_name)) continue;
    if (rec.shares_after === null) continue;

    if (!byDate.has(rec.filing_date)) {
      byDate.set(rec.filing_date, new Map());
    }
    // If multiple records for same insider on same date, keep last (most recent)
    byDate.get(rec.filing_date)!.set(rec.insider_name, rec.shares_after);
  }

  // Sort dates ascending
  const sortedDates = Array.from(byDate.keys()).sort();

  return sortedDates.map((date) => {
    const point: Record<string, string | number> = { date };
    const insiderMap = byDate.get(date)!;
    for (const insider of topInsiders) {
      if (insiderMap.has(insider)) {
        point[insider] = insiderMap.get(insider)!;
      }
    }
    return point;
  });
}

function PositionHistoryChart({ data }: { data: OwnershipChangesResponse }) {
  // Pick top 5 insiders by number of records
  const insiderCounts: Record<string, number> = {};
  for (const rec of data.records) {
    insiderCounts[rec.insider_name] = (insiderCounts[rec.insider_name] ?? 0) + 1;
  }
  const topInsiders = Object.entries(insiderCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name]) => name);

  const chartData = buildChartData(data.records, topInsiders);

  if (chartData.length === 0 || topInsiders.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-4">
        <CardTitle className="text-sm font-medium">Position History (Shares Held)</CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={50}
              tickFormatter={(v: number) => (v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `${(v / 1_000).toFixed(0)}K` : String(v))}
            />
            <Tooltip
              formatter={(value: number, name: string) => [value.toLocaleString('en-US'), name]}
              labelFormatter={(label: string) => `Date: ${label}`}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {topInsiders.map((insider, i) => (
              <Line
                key={insider}
                type="monotone"
                dataKey={insider}
                stroke={lineColor(i)}
                dot={false}
                connectNulls
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Change Log Table
// ---------------------------------------------------------------------------

function ChangeLogTable({
  records,
  insiderFilter,
}: {
  records: OwnershipChangeRecord[];
  insiderFilter: string;
}) {
  const filtered = insiderFilter === 'all' ? records : records.filter((r) => r.insider_name === insiderFilter);

  if (filtered.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">
        No ownership records match the current filter.
      </div>
    );
  }

  return (
    <div className="rounded-md border overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[110px]">Filing Date</TableHead>
            <TableHead>Insider Name</TableHead>
            <TableHead>Position</TableHead>
            <TableHead className="text-right">Shares Before</TableHead>
            <TableHead className="text-right">Shares After</TableHead>
            <TableHead className="text-right">Net Change</TableHead>
            <TableHead className="w-[90px]">Form Type</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((rec, i) => (
            <TableRow key={`${rec.accession_no}-${i}`}>
              <TableCell className="text-xs whitespace-nowrap">{rec.filing_date}</TableCell>
              <TableCell className="font-medium text-sm">{rec.insider_name}</TableCell>
              <TableCell className="text-xs text-muted-foreground max-w-[140px] truncate">
                {rec.position}
              </TableCell>
              <TableCell className="text-right text-xs tabular-nums">
                {formatNumber(rec.shares_before)}
              </TableCell>
              <TableCell className="text-right text-xs tabular-nums">
                {formatNumber(rec.shares_after)}
              </TableCell>
              <TableCell
                className={`text-right text-sm tabular-nums font-medium ${
                  rec.net_change > 0
                    ? 'text-green-600'
                    : rec.net_change < 0
                    ? 'text-red-600'
                    : ''
                }`}
              >
                {rec.net_change > 0 ? '+' : ''}
                {formatNumber(rec.net_change)}
              </TableCell>
              <TableCell className="text-xs font-mono">{rec.form_type}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-52 w-full rounded-xl" />
      <div className="space-y-2">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// InsiderOwnershipPage
// ---------------------------------------------------------------------------

export function InsiderOwnershipPage() {
  const [ticker, setTicker] = useState('');
  const [data, setData] = useState<OwnershipChangesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [insiderFilter, setInsiderFilter] = useState<string>('all');

  const handleSearch = async (overrideTicker?: string) => {
    const tickerToUse = (overrideTicker ?? ticker).trim().toUpperCase();
    if (!tickerToUse) return;
    setLoading(true);
    setError(null);
    setData(null);
    setInsiderFilter('all');
    try {
      const result = await insiderService.getOwnership(tickerToUse);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch ownership data');
    } finally {
      setLoading(false);
    }
  };

  // Build dropdown options from insiders in the response
  const insiderOptions = useMemo(() => {
    if (!data) return [];
    return data.insiders;
  }, [data]);

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold">Ownership Changes</h1>
          <p className="text-sm text-muted-foreground">
            Position history and ownership change log from Form 3/4/5 filings.
          </p>
        </div>
        <div className="flex items-center gap-1">
          <SubNavLink to="/insider" label="Dashboard" />
          <SubNavLink to="/insider/ownership" label="Ownership" />
          <SubNavLink to="/insider/grants" label="Grants" />
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

      {/* Error */}
      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {/* Loading skeleton */}
      {loading && <LoadingSkeleton />}

      {/* Results */}
      {data && !loading && (
        <>
          {/* Skipped count notice */}
          <SkippedCountBanner
            skippedCount={data.skipped_count}
            shownCount={data.records.length}
            totalCount={data.total}
            itemLabel="records"
          />

          {/* Position history chart */}
          <PositionHistoryChart data={data} />

          {/* Insider filter dropdown */}
          {insiderOptions.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Filter by insider:</span>
              <select
                className="text-sm border rounded-md px-2 py-1 bg-background"
                value={insiderFilter}
                onChange={(e) => setInsiderFilter(e.target.value)}
              >
                <option value="all">All insiders</option>
                {insiderOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Change log table */}
          <ChangeLogTable records={data.records} insiderFilter={insiderFilter} />
        </>
      )}

      {/* Empty state */}
      {!data && !loading && !error && (
        <div className="text-center py-20 text-muted-foreground text-sm">
          Enter a ticker symbol and click Search to view ownership changes.
        </div>
      )}
    </div>
  );
}
