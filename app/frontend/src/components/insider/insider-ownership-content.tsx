import { useEffect, useMemo, useState } from 'react';
import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  insiderService,
  type OwnershipChangeRecord,
  type OwnershipChangesResponse,
} from '@/services/insider-api';
import { SkippedCountBanner } from '@/components/insider/skipped-count-banner';
import { formatNumber } from '@/utils/format';

// ---------------------------------------------------------------------------
// Chart helpers
// ---------------------------------------------------------------------------

const LINE_COLORS = ['#2563eb', '#16a34a', '#dc2626', '#d97706', '#7c3aed'];
const lineColor = (index: number): string => LINE_COLORS[index % LINE_COLORS.length];

function buildChartData(
  records: OwnershipChangeRecord[],
  topInsiders: string[]
): Record<string, string | number>[] {
  const byDate: Map<string, Map<string, number>> = new Map();

  for (const rec of records) {
    if (!topInsiders.includes(rec.insider_name)) continue;
    if (rec.shares_after === null) continue;
    if (!byDate.has(rec.filing_date)) {
      byDate.set(rec.filing_date, new Map());
    }
    byDate.get(rec.filing_date)!.set(rec.insider_name, rec.shares_after);
  }

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

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PositionHistoryChart({ data }: { data: OwnershipChangesResponse }) {
  const insiderCounts: Record<string, number> = {};
  for (const rec of data.records) {
    insiderCounts[rec.insider_name] = (insiderCounts[rec.insider_name] ?? 0) + 1;
  }
  const topInsiders = Object.entries(insiderCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name]) => name);

  const chartData = buildChartData(data.records, topInsiders);

  if (chartData.length === 0 || topInsiders.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2 pt-4 px-4">
        <CardTitle className="text-sm font-medium">Position History (Shares Held)</CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} width={50} tickFormatter={(v: number) => (v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `${(v / 1_000).toFixed(0)}K` : String(v))} />
            <Tooltip formatter={(value: number, name: string) => [value.toLocaleString('en-US'), name]} labelFormatter={(label: string) => `Date: ${label}`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {topInsiders.map((insider, i) => (
              <Line key={insider} type="monotone" dataKey={insider} stroke={lineColor(i)} dot={false} connectNulls strokeWidth={2} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

function ChangeLogTable({ records, insiderFilter }: { records: OwnershipChangeRecord[]; insiderFilter: string }) {
  const filtered = insiderFilter === 'all' ? records : records.filter((r) => r.insider_name === insiderFilter);

  if (filtered.length === 0) {
    return <div className="text-center py-12 text-muted-foreground text-sm">No ownership records match the current filter.</div>;
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
              <TableCell className="text-xs text-muted-foreground max-w-[140px] truncate">{rec.position}</TableCell>
              <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.shares_before)}</TableCell>
              <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.shares_after)}</TableCell>
              <TableCell className={`text-right text-sm tabular-nums font-medium ${rec.net_change > 0 ? 'text-green-600' : rec.net_change < 0 ? 'text-red-600' : ''}`}>
                {rec.net_change > 0 ? '+' : ''}{formatNumber(rec.net_change)}
              </TableCell>
              <TableCell className="text-xs font-mono">{rec.form_type}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function OwnershipSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-52 w-full rounded-xl" />
      <div className="space-y-2">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main content component
// ---------------------------------------------------------------------------

export function InsiderOwnershipContent({ ticker }: { ticker: string }) {
  const [data, setData] = useState<OwnershipChangesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [insiderFilter, setInsiderFilter] = useState<string>('all');

  useEffect(() => {
    if (!ticker) { setData(null); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    setInsiderFilter('all');
    insiderService.getOwnership(ticker).then((result) => {
      if (!cancelled) setData(result);
    }).catch((e) => {
      if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to fetch ownership data');
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [ticker]);

  const insiderOptions = useMemo(() => data?.insiders ?? [], [data]);

  if (!ticker) {
    return <div className="text-center py-12 text-muted-foreground text-sm">Search a ticker above to view ownership changes.</div>;
  }

  if (loading) return <OwnershipSkeleton />;

  if (error) {
    return <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>;
  }

  if (!data) return null;

  return (
    <div className="space-y-4">
      <SkippedCountBanner skippedCount={data.skipped_count} shownCount={data.records.length} totalCount={data.total} itemLabel="records" />
      <PositionHistoryChart data={data} />
      {insiderOptions.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Filter by insider:</span>
          <select className="text-sm border rounded-md px-2 py-1 bg-background" value={insiderFilter} onChange={(e) => setInsiderFilter(e.target.value)}>
            <option value="all">All insiders</option>
            {insiderOptions.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </div>
      )}
      <ChangeLogTable records={data.records} insiderFilter={insiderFilter} />
    </div>
  );
}
