import { useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  insiderService,
  type GrantRecord,
  type GrantsResponse,
} from '@/services/insider-api';
import { SkippedCountBanner } from '@/components/insider/skipped-count-banner';
import { formatNumber, formatPrice } from '@/utils/format';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TransactionFilter = 'all' | 'grant' | 'exercise' | 'conversion';

// ---------------------------------------------------------------------------
// Badges
// ---------------------------------------------------------------------------

function TransactionTypeBadge({ txType }: { txType: string }) {
  const lower = txType.toLowerCase();
  if (lower === 'grant') return <Badge variant="outline" className="text-blue-600 border-blue-600 whitespace-nowrap">Grant</Badge>;
  if (lower === 'exercise') return <Badge variant="outline" className="text-green-600 border-green-600 whitespace-nowrap">Exercise</Badge>;
  if (lower === 'conversion') return <Badge variant="outline" className="text-purple-600 border-purple-600 whitespace-nowrap">Conversion</Badge>;
  return <Badge variant="outline" className="whitespace-nowrap">{txType}</Badge>;
}

function AcquiredDisposedBadge({ value }: { value: string }) {
  if (value.toUpperCase() === 'A') return <Badge variant="outline" className="text-green-600 border-green-600 whitespace-nowrap">A</Badge>;
  if (value.toUpperCase() === 'D') return <Badge variant="outline" className="text-red-600 border-red-600 whitespace-nowrap">D</Badge>;
  return <span className="text-xs font-mono">{value}</span>;
}

// ---------------------------------------------------------------------------
// Filter
// ---------------------------------------------------------------------------

const FILTER_OPTIONS: { value: TransactionFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'grant', label: 'Grants' },
  { value: 'exercise', label: 'Exercises' },
  { value: 'conversion', label: 'Conversions' },
];

function applyFilter(records: GrantRecord[], filter: TransactionFilter): GrantRecord[] {
  if (filter === 'all') return records;
  return records.filter((r) => r.transaction_type.toLowerCase() === filter);
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

function GrantsTable({ records }: { records: GrantRecord[] }) {
  if (records.length === 0) {
    return <div className="text-center py-12 text-muted-foreground text-sm">No records match the current filter.</div>;
  }

  return (
    <div className="rounded-md border overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[110px]">Filing Date</TableHead>
            <TableHead>Insider Name</TableHead>
            <TableHead>Position</TableHead>
            <TableHead>Transaction Type</TableHead>
            <TableHead>Security Title</TableHead>
            <TableHead className="text-right">Exercise Price</TableHead>
            <TableHead className="w-[110px]">Expiration Date</TableHead>
            <TableHead className="text-right">Shares</TableHead>
            <TableHead>Underlying Security</TableHead>
            <TableHead className="text-center">Acq/Disp</TableHead>
            <TableHead className="w-[60px]">Code</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {records.map((rec, i) => (
            <TableRow key={`${rec.accession_no}-${i}`}>
              <TableCell className="text-xs whitespace-nowrap">{rec.filing_date}</TableCell>
              <TableCell className="font-medium text-sm">{rec.insider_name}</TableCell>
              <TableCell className="text-xs text-muted-foreground max-w-[140px] truncate">{rec.position}</TableCell>
              <TableCell><TransactionTypeBadge txType={rec.transaction_type} /></TableCell>
              <TableCell className="text-xs max-w-[160px] truncate">{rec.security_title}</TableCell>
              <TableCell className="text-right text-xs tabular-nums">{formatPrice(rec.exercise_price)}</TableCell>
              <TableCell className="text-xs whitespace-nowrap">{rec.expiration_date ?? '—'}</TableCell>
              <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.shares)}</TableCell>
              <TableCell className="text-xs max-w-[160px] truncate">{rec.underlying_security ?? '—'}</TableCell>
              <TableCell className="text-center"><AcquiredDisposedBadge value={rec.acquired_disposed} /></TableCell>
              <TableCell className="text-xs font-mono">{rec.code}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function GrantsSkeleton() {
  return (
    <div className="space-y-4">
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

export function InsiderGrantsContent({ ticker }: { ticker: string }) {
  const [data, setData] = useState<GrantsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TransactionFilter>('all');

  useEffect(() => {
    if (!ticker) { setData(null); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    setFilter('all');
    insiderService.getGrants(ticker).then((result) => {
      if (!cancelled) setData(result);
    }).catch((e) => {
      if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to fetch grants data');
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [ticker]);

  if (!ticker) {
    return <div className="text-center py-12 text-muted-foreground text-sm">Search a ticker above to view grants and exercises.</div>;
  }

  if (loading) return <GrantsSkeleton />;

  if (error) {
    return <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>;
  }

  if (!data) return null;

  const filteredRecords = applyFilter(data.records, filter);

  return (
    <div className="space-y-4">
      <SkippedCountBanner skippedCount={data.skipped_count} shownCount={data.records.length} totalCount={data.total} itemLabel="records" />
      <div className="flex flex-wrap gap-1">
        {FILTER_OPTIONS.map(({ value, label }) => (
          <Button key={value} variant={filter === value ? 'default' : 'outline'} size="sm" onClick={() => setFilter(value)}>
            {label}
          </Button>
        ))}
      </div>
      {data.records.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground text-sm">No grants or exercises found for {data.ticker}.</div>
      ) : (
        <GrantsTable records={filteredRecords} />
      )}
    </div>
  );
}
