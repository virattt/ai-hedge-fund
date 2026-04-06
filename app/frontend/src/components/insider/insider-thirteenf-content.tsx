import { useEffect, useState } from 'react';
import { Loader2, X } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  insiderService,
  type CompareHoldingsResponse,
  type HoldingHistoryResponse,
  type ThirteenFFilingListItem,
} from '@/services/insider-api';
import { formatNumber } from '@/utils/format';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const upper = status.toUpperCase();
  if (upper === 'NEW') {
    return <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800">NEW</span>;
  }
  if (upper === 'CLOSED') {
    return <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800">CLOSED</span>;
  }
  if (upper === 'INCREASED') {
    return <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800">INCREASED</span>;
  }
  if (upper === 'DECREASED') {
    return <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-orange-100 text-orange-800">DECREASED</span>;
  }
  return <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-800">{status}</span>;
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function ThirteenFSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-8 w-48" />
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filings table
// ---------------------------------------------------------------------------

interface FilingsTableProps {
  filings: ThirteenFFilingListItem[];
  hasMore: boolean;
  loadingMore: boolean;
  onRowClick: (filing: ThirteenFFilingListItem) => void;
  onLoadMore: () => void;
}

function FilingsTable({ filings, hasMore, loadingMore, onRowClick, onLoadMore }: FilingsTableProps) {
  if (filings.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">No 13F-HR filings found.</div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-md border overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[110px]">Filing Date</TableHead>
              <TableHead>Company</TableHead>
              <TableHead className="w-[80px]">CIK</TableHead>
              <TableHead className="w-[60px]">Form</TableHead>
              <TableHead>Accession No.</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filings.map((filing) => (
              <TableRow
                key={filing.accession_no}
                className="cursor-pointer hover:bg-accent/30"
                onClick={() => onRowClick(filing)}
              >
                <TableCell className="text-xs whitespace-nowrap">{filing.filing_date}</TableCell>
                <TableCell className="text-sm font-medium">{filing.company}</TableCell>
                <TableCell className="text-xs tabular-nums text-muted-foreground">{filing.cik}</TableCell>
                <TableCell>
                  <Badge variant="secondary" className="text-xs font-mono">{filing.form}</Badge>
                </TableCell>
                <TableCell className="text-xs font-mono text-muted-foreground">{filing.accession_no}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {hasMore && (
        <div className="flex justify-center">
          <Button
            variant="outline"
            size="sm"
            onClick={onLoadMore}
            disabled={loadingMore}
          >
            {loadingMore ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Loading…
              </>
            ) : (
              'Load More'
            )}
          </Button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compare Holdings section (lazy-loaded)
// ---------------------------------------------------------------------------

function CompareHoldingsSection({ accessionNo }: { accessionNo: string }) {
  const [data, setData] = useState<CompareHoldingsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  // Reset when accessionNo changes
  useEffect(() => {
    setData(null);
    setLoading(false);
    setError(null);
    setLoaded(false);
  }, [accessionNo]);

  const handleLoad = () => {
    setLoading(true);
    setError(null);
    insiderService
      .getCompareHoldings(accessionNo)
      .then((result) => {
        setData(result);
        setLoaded(true);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Failed to load compare holdings');
        // Keep loaded=false on error so user can retry
      })
      .finally(() => {
        setLoading(false);
      });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Compare Holdings</h3>
        {!loaded && (
          <Button variant="outline" size="sm" onClick={handleLoad} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Loading…
              </>
            ) : (
              'Load Compare Holdings'
            )}
          </Button>
        )}
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {data && data.records.length === 0 && (
        <div className="text-center py-6 text-muted-foreground text-sm">No comparison data available for this filing.</div>
      )}

      {data && data.records.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">
            {data.manager_name} &middot; {data.current_period} vs {data.previous_period} &middot; {data.total} holdings
          </p>
          <div className="rounded-md border overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[100px]">Status</TableHead>
                  <TableHead className="w-[70px]">Ticker</TableHead>
                  <TableHead>Issuer</TableHead>
                  <TableHead className="text-right">Shares</TableHead>
                  <TableHead className="text-right">Prev Shares</TableHead>
                  <TableHead className="text-right">Share Chg %</TableHead>
                  <TableHead className="text-right">Value ($000s)</TableHead>
                  <TableHead className="text-right">Prev Value</TableHead>
                  <TableHead className="text-right">Val Chg %</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.records.map((rec, i) => (
                  <TableRow key={`${rec.cusip}-${i}`}>
                    <TableCell><StatusBadge status={rec.status} /></TableCell>
                    <TableCell className="text-xs font-mono font-medium">{rec.ticker ?? '—'}</TableCell>
                    <TableCell className="text-sm">{rec.issuer}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.shares)}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.prev_shares)}</TableCell>
                    <TableCell className={`text-right text-xs tabular-nums ${rec.share_change_pct !== null && rec.share_change_pct > 0 ? 'text-green-600' : rec.share_change_pct !== null && rec.share_change_pct < 0 ? 'text-red-600' : ''}`}>
                      {rec.share_change_pct !== null ? `${rec.share_change_pct > 0 ? '+' : ''}${rec.share_change_pct.toFixed(1)}%` : '—'}
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.value)}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.prev_value)}</TableCell>
                    <TableCell className={`text-right text-xs tabular-nums ${rec.value_change_pct !== null && rec.value_change_pct > 0 ? 'text-green-600' : rec.value_change_pct !== null && rec.value_change_pct < 0 ? 'text-red-600' : ''}`}>
                      {rec.value_change_pct !== null ? `${rec.value_change_pct > 0 ? '+' : ''}${rec.value_change_pct.toFixed(1)}%` : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Holding History section (lazy-loaded)
// ---------------------------------------------------------------------------

function HoldingHistorySection({ accessionNo }: { accessionNo: string }) {
  const [data, setData] = useState<HoldingHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  // Reset when accessionNo changes
  useEffect(() => {
    setData(null);
    setLoading(false);
    setError(null);
    setLoaded(false);
  }, [accessionNo]);

  const handleLoad = () => {
    setLoading(true);
    setError(null);
    insiderService
      .getHoldingHistory(accessionNo, 4)
      .then((result) => {
        setData(result);
        setLoaded(true);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Failed to load holding history');
        // Keep loaded=false on error so user can retry
      })
      .finally(() => {
        setLoading(false);
      });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Holding History</h3>
        {!loaded && (
          <Button variant="outline" size="sm" onClick={handleLoad} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Loading…
              </>
            ) : (
              'Load Holding History'
            )}
          </Button>
        )}
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {data && data.records.length === 0 && (
        <div className="text-center py-6 text-muted-foreground text-sm">No holding history available for this filing.</div>
      )}

      {data && data.records.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">
            {data.manager_name} &middot; {data.periods.length} periods &middot; {data.total} holdings
          </p>
          <div className="rounded-md border overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[70px]">Ticker</TableHead>
                  <TableHead>Issuer</TableHead>
                  {data.periods.map((period) => (
                    <TableHead key={period} className="text-right text-xs whitespace-nowrap">{period}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.records.map((rec, i) => (
                  <TableRow key={`${rec.cusip}-${i}`}>
                    <TableCell className="text-xs font-mono font-medium">{rec.ticker ?? '—'}</TableCell>
                    <TableCell className="text-sm">{rec.issuer}</TableCell>
                    {data.periods.map((period) => (
                      <TableCell key={period} className="text-right text-xs tabular-nums">
                        {formatNumber(rec.periods_data[period] ?? null)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filing detail sheet
// ---------------------------------------------------------------------------

interface FilingDetailSheetProps {
  filing: ThirteenFFilingListItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function FilingDetailSheet({ filing, open, onOpenChange }: FilingDetailSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-full overflow-y-auto">
        {filing && (
          <>
            <SheetHeader className="mb-6">
              <SheetTitle>{filing.company}</SheetTitle>
              <SheetDescription>
                Filed {filing.filing_date} &middot; {filing.form} &middot; Accession: {filing.accession_no}
              </SheetDescription>
            </SheetHeader>

            <div className="space-y-6">
              <CompareHoldingsSection accessionNo={filing.accession_no} />
              <div className="border-t pt-6">
                <HoldingHistorySection accessionNo={filing.accession_no} />
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------
// Main content component
// ---------------------------------------------------------------------------

/**
 * InsiderThirteenFContent renders a paginated list of 13F-HR filings across
 * all companies. Filings are loaded on mount without requiring a ticker search.
 * A company name search input with 400ms debounce enables fuzzy filtering.
 * Clicking a row opens a Sheet side panel with two independently lazy-loaded
 * sections: Compare Holdings and Holding History.
 */
export function InsiderThirteenFContent() {
  const [filings, setFilings] = useState<ThirteenFFilingListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [selectedFiling, setSelectedFiling] = useState<ThirteenFFilingListItem | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [companySearch, setCompanySearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Debounce company search input by 400ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(companySearch);
    }, 400);
    return () => clearTimeout(timer);
  }, [companySearch]);

  // Reload filings when debounced search changes (reset offset)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setOffset(0);
    insiderService
      .getThirteenFFilings(PAGE_SIZE, 0, undefined, undefined, debouncedSearch || undefined)
      .then((result) => {
        if (cancelled) return;
        setFilings(result.filings);
        setTotal(result.total);
        setHasMore(result.has_more);
        setOffset(PAGE_SIZE);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Failed to fetch 13F filings');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [debouncedSearch]);

  const handleLoadMore = () => {
    setLoadingMore(true);
    insiderService
      .getThirteenFFilings(PAGE_SIZE, offset, undefined, undefined, debouncedSearch || undefined)
      .then((result) => {
        setFilings((prev) => [...prev, ...result.filings]);
        setTotal(result.total);
        setHasMore(result.has_more);
        setOffset((prev) => prev + PAGE_SIZE);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Failed to load more filings');
      })
      .finally(() => {
        setLoadingMore(false);
      });
  };

  const handleRowClick = (filing: ThirteenFFilingListItem) => {
    setSelectedFiling(filing);
    setSheetOpen(true);
  };

  const handleClearSearch = () => {
    setCompanySearch('');
  };

  if (loading) return <ThirteenFSkeleton />;

  if (error) {
    return <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>;
  }

  return (
    <div className="space-y-3">
      <div className="relative max-w-sm">
        <Input
          type="text"
          placeholder="Search by company name..."
          value={companySearch}
          onChange={(e) => setCompanySearch(e.target.value)}
          className="pr-8"
        />
        {companySearch && (
          <button
            type="button"
            onClick={handleClearSearch}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {total > 0 && (
        <p className="text-xs text-muted-foreground">
          Showing {filings.length} of {formatNumber(total)} filings. Click a row to view holdings detail.
        </p>
      )}

      <FilingsTable
        filings={filings}
        hasMore={hasMore}
        loadingMore={loadingMore}
        onRowClick={handleRowClick}
        onLoadMore={handleLoadMore}
      />

      <FilingDetailSheet
        filing={selectedFiling}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </div>
  );
}
