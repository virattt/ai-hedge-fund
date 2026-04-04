import { useState } from 'react';
import { Loader2, Search } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  insiderService,
  type GrantRecord,
  type GrantsResponse,
} from '@/services/insider-api';
import { SubNavLink } from '@/components/insider/insider-sub-nav';
import { SkippedCountBanner } from '@/components/insider/skipped-count-banner';
import { formatNumber, formatPrice } from '@/utils/format';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TransactionFilter = 'all' | 'grant' | 'exercise' | 'conversion';

// ---------------------------------------------------------------------------
// Transaction type badge (color-coded)
// ---------------------------------------------------------------------------

function TransactionTypeBadge({ txType }: { txType: string }) {
  const lower = txType.toLowerCase();
  if (lower === 'grant') {
    return (
      <Badge variant="outline" className="text-blue-600 border-blue-600 whitespace-nowrap">
        Grant
      </Badge>
    );
  }
  if (lower === 'exercise') {
    return (
      <Badge variant="outline" className="text-green-600 border-green-600 whitespace-nowrap">
        Exercise
      </Badge>
    );
  }
  if (lower === 'conversion') {
    return (
      <Badge variant="outline" className="text-purple-600 border-purple-600 whitespace-nowrap">
        Conversion
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="whitespace-nowrap">
      {txType}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Acquired/Disposed badge
// ---------------------------------------------------------------------------

function AcquiredDisposedBadge({ value }: { value: string }) {
  if (value.toUpperCase() === 'A') {
    return (
      <Badge variant="outline" className="text-green-600 border-green-600 whitespace-nowrap">
        A
      </Badge>
    );
  }
  if (value.toUpperCase() === 'D') {
    return (
      <Badge variant="outline" className="text-red-600 border-red-600 whitespace-nowrap">
        D
      </Badge>
    );
  }
  return <span className="text-xs font-mono">{value}</span>;
}

// ---------------------------------------------------------------------------
// Filter options
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
// Grants table
// ---------------------------------------------------------------------------

function GrantsTable({ records }: { records: GrantRecord[] }) {
  if (records.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">
        No records match the current filter.
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
              <TableCell className="text-xs text-muted-foreground max-w-[140px] truncate">
                {rec.position}
              </TableCell>
              <TableCell>
                <TransactionTypeBadge txType={rec.transaction_type} />
              </TableCell>
              <TableCell className="text-xs max-w-[160px] truncate">{rec.security_title}</TableCell>
              <TableCell className="text-right text-xs tabular-nums">
                {formatPrice(rec.exercise_price)}
              </TableCell>
              <TableCell className="text-xs whitespace-nowrap">
                {rec.expiration_date ?? '—'}
              </TableCell>
              <TableCell className="text-right text-xs tabular-nums">
                {formatNumber(rec.shares)}
              </TableCell>
              <TableCell className="text-xs max-w-[160px] truncate">
                {rec.underlying_security ?? '—'}
              </TableCell>
              <TableCell className="text-center">
                <AcquiredDisposedBadge value={rec.acquired_disposed} />
              </TableCell>
              <TableCell className="text-xs font-mono">{rec.code}</TableCell>
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
// InsiderGrantsPage
// ---------------------------------------------------------------------------

export function InsiderGrantsPage() {
  const [ticker, setTicker] = useState('');
  const [data, setData] = useState<GrantsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TransactionFilter>('all');

  const handleSearch = async (overrideTicker?: string) => {
    const tickerToUse = (overrideTicker ?? ticker).trim().toUpperCase();
    if (!tickerToUse) return;
    setLoading(true);
    setError(null);
    setData(null);
    setFilter('all');
    try {
      const result = await insiderService.getGrants(tickerToUse);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch grants data');
    } finally {
      setLoading(false);
    }
  };

  const filteredRecords = data ? applyFilter(data.records, filter) : [];

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold">Grants &amp; Exercises</h1>
          <p className="text-sm text-muted-foreground">
            Derivative trades, option grants and exercises from SEC filings.
          </p>
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

          {/* Grants table */}
          {data.records.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              No grants or exercises found for {data.ticker}.
            </div>
          ) : (
            <GrantsTable records={filteredRecords} />
          )}
        </>
      )}

      {/* Empty state */}
      {!data && !loading && !error && (
        <div className="text-center py-20 text-muted-foreground text-sm">
          Enter a ticker symbol and click Search to view grants and exercises.
        </div>
      )}
    </div>
  );
}
