import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ArrowDown, ArrowUp, ArrowUpDown, Check, ChevronDown, ChevronRight, ChevronsUpDown, Loader2, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  insiderService,
  type AggregateHoldingRecord,
  type AggregateHoldingsResponse,
  type CompareHoldingsRecord,
  type CompareHoldingsResponse,
  type HoldingHistoryRecord,
  type HoldingHistoryResponse,
  type ThirteenFCompanyItem,
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
// Shared sortable header
// ---------------------------------------------------------------------------

type SortDir = 'asc' | 'desc';

function SortableHead<K extends string>({
  label,
  sortKey,
  currentKey,
  currentDir,
  onSort,
  className,
}: {
  label: string;
  sortKey: K;
  currentKey: K | null;
  currentDir: SortDir;
  onSort: (key: K) => void;
  className?: string;
}) {
  const active = currentKey === sortKey;
  return (
    <TableHead
      className={`cursor-pointer select-none hover:bg-accent/30 ${className ?? ''}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active ? (
          currentDir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-30" />
        )}
      </span>
    </TableHead>
  );
}

function useSort<K extends string>(defaultDir: SortDir = 'desc') {
  const [sortKey, setSortKey] = useState<K | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(defaultDir);

  const handleSort = (key: K) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(defaultDir);
    }
  };

  const reset = () => {
    setSortKey(null);
    setSortDir(defaultDir);
  };

  return { sortKey, sortDir, handleSort, reset };
}

// ---------------------------------------------------------------------------
// Multi-select company dropdown
// ---------------------------------------------------------------------------

function CompanyMultiSelect({
  companies,
  selected,
  onSave,
  onClear,
  loading,
}: {
  companies: ThirteenFCompanyItem[];
  selected: Set<string>;
  onSave: (selected: Set<string>) => void;
  onClear: () => void;
  loading?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [pending, setPending] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);

  // Sync pending state from parent when popover opens
  useEffect(() => {
    if (open) {
      setPending(new Set(selected));
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = useCallback(
    (company: string) => {
      setPending((prev) => {
        const next = new Set(prev);
        if (next.has(company)) {
          next.delete(company);
        } else {
          next.add(company);
        }
        return next;
      });
    },
    [],
  );

  const handleSave = () => {
    onSave(pending);
    setOpen(false);
  };

  const handleClear = () => {
    onClear();
    setPending(new Set());
    setOpen(false);
  };

  // Filter + sort: selected items first, then alphabetical matches
  const filteredCompanies = useMemo(() => {
    const q = search.trim().toLowerCase();
    const selectedItems: ThirteenFCompanyItem[] = [];
    const rest: ThirteenFCompanyItem[] = [];
    for (const item of companies) {
      if (!q || item.company.toLowerCase().includes(q)) {
        if (pending.has(item.company)) {
          selectedItems.push(item);
        } else {
          rest.push(item);
        }
      }
    }
    return [...selectedItems, ...rest];
  }, [companies, pending, search]);

  const virtualizer = useVirtualizer({
    count: filteredCompanies.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 32,
    overscan: 20,
  });

  // Re-measure when popover opens (scroll container becomes available)
  useEffect(() => {
    if (open) {
      const id = requestAnimationFrame(() => virtualizer.measure());
      return () => cancelAnimationFrame(id);
    }
  }, [open, virtualizer]);

  const label =
    selected.size === 0
      ? 'Filter by companies...'
      : selected.size === 1
        ? [...selected][0]
        : `${selected.size} companies selected`;

  const pendingChanged = pending.size !== selected.size || [...pending].some((c) => !selected.has(c));

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-[320px] justify-between text-xs font-normal"
          disabled={loading}
        >
          <span className="truncate">{loading ? 'Loading companies...' : label}</span>
          <ChevronsUpDown className="ml-2 h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[320px] p-0" align="start">
        <div className="flex flex-col">
          <div className="p-2 border-b">
            <Input
              placeholder="Search companies..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 text-xs"
              autoFocus
            />
          </div>
          <div ref={scrollRef} className="h-[300px] overflow-auto">
            {filteredCompanies.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">No companies found.</p>
            ) : (
              <div style={{ height: `${virtualizer.getTotalSize()}px`, width: '100%', position: 'relative' }}>
                {virtualizer.getVirtualItems().map((virtualRow) => {
                  const item = filteredCompanies[virtualRow.index];
                  const isSelected = pending.has(item.company);
                  return (
                    <div
                      key={item.cik}
                      className="absolute left-0 w-full flex items-center px-2 py-1 cursor-pointer hover:bg-accent text-xs"
                      style={{ top: `${virtualRow.start}px`, height: `${virtualRow.size}px` }}
                      onClick={() => toggle(item.company)}
                    >
                      <Check className={`mr-2 h-4 w-4 shrink-0 ${isSelected ? 'opacity-100' : 'opacity-0'}`} />
                      <span className="truncate">{item.company}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <div className="border-t p-2 flex gap-2">
            <Button
              variant="default"
              size="sm"
              className="flex-1 text-xs"
              onClick={handleSave}
              disabled={pending.size === 0 && selected.size === 0}
            >
              {pendingChanged ? `Save (${pending.size})` : `Save`}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="flex-1 text-xs"
              onClick={handleClear}
              disabled={selected.size === 0 && pending.size === 0}
            >
              Clear
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
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

type FilingSortKey = 'filing_date' | 'company' | 'cik' | 'signer_name' | 'total_value' | 'total_holdings';

function compareFilings(a: ThirteenFFilingListItem, b: ThirteenFFilingListItem, key: FilingSortKey): number {
  if (key === 'filing_date') return a.filing_date.localeCompare(b.filing_date);
  if (key === 'company') return a.company.localeCompare(b.company);
  if (key === 'cik') return a.cik - b.cik;
  if (key === 'signer_name') return (a.signer_name ?? '').localeCompare(b.signer_name ?? '');
  if (key === 'total_value') return (a.total_value ?? 0) - (b.total_value ?? 0);
  if (key === 'total_holdings') return (a.total_holdings ?? 0) - (b.total_holdings ?? 0);
  return 0;
}

function FilingsTable({ filings, hasMore, loadingMore, onRowClick, onLoadMore }: FilingsTableProps) {
  const { sortKey, sortDir, handleSort } = useSort<FilingSortKey>('asc');

  const sortedFilings = useMemo(() => {
    if (!sortKey) return filings;
    const sorted = [...filings].sort((a, b) => compareFilings(a, b, sortKey));
    return sortDir === 'desc' ? sorted.reverse() : sorted;
  }, [filings, sortKey, sortDir]);

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
              <SortableHead label="Filing Date" sortKey="filing_date" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-[110px]" />
              <SortableHead label="Company" sortKey="company" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
              <SortableHead label="Signed By" sortKey="signer_name" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
              <SortableHead label="Value ($000s)" sortKey="total_value" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Holdings" sortKey="total_holdings" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right w-[80px]" />
              <TableHead className="w-[180px]">Accession No.</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedFilings.map((filing) => (
              <TableRow
                key={filing.accession_no}
                className="cursor-pointer hover:bg-accent/30"
                onClick={() => onRowClick(filing)}
              >
                <TableCell className="text-xs whitespace-nowrap">{filing.filing_date}</TableCell>
                <TableCell className="text-sm font-medium">{filing.company}</TableCell>
                <TableCell className="text-xs">{filing.signer_name ? `${filing.signer_name}${filing.signer_title ? ` (${filing.signer_title})` : ''}` : '—'}</TableCell>
                <TableCell className="text-right text-xs tabular-nums">{formatNumber(filing.total_value)}</TableCell>
                <TableCell className="text-right text-xs tabular-nums">{formatNumber(filing.total_holdings)}</TableCell>
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

type CompareSortKey = 'status' | 'ticker' | 'issuer' | 'shares' | 'prev_shares' | 'share_change_pct' | 'value' | 'prev_value' | 'value_change_pct';

function compareCompareRecords(a: CompareHoldingsRecord, b: CompareHoldingsRecord, key: CompareSortKey): number {
  if (key === 'status') return a.status.localeCompare(b.status);
  if (key === 'ticker') return (a.ticker ?? '').localeCompare(b.ticker ?? '');
  if (key === 'issuer') return a.issuer.localeCompare(b.issuer);
  if (key === 'shares') return (a.shares ?? 0) - (b.shares ?? 0);
  if (key === 'prev_shares') return (a.prev_shares ?? 0) - (b.prev_shares ?? 0);
  if (key === 'share_change_pct') return (a.share_change_pct ?? 0) - (b.share_change_pct ?? 0);
  if (key === 'value') return (a.value ?? 0) - (b.value ?? 0);
  if (key === 'prev_value') return (a.prev_value ?? 0) - (b.prev_value ?? 0);
  if (key === 'value_change_pct') return (a.value_change_pct ?? 0) - (b.value_change_pct ?? 0);
  return 0;
}

function CompareHoldingsSection({ accessionNo }: { accessionNo: string }) {
  const [data, setData] = useState<CompareHoldingsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const { sortKey, sortDir, handleSort, reset: resetSort } = useSort<CompareSortKey>('desc');

  // Reset when accessionNo changes
  useEffect(() => {
    setData(null);
    setLoading(false);
    setError(null);
    setLoaded(false);
    resetSort();
  }, [accessionNo]);

  const sortedRecords = useMemo(() => {
    if (!data || !sortKey) return data?.records ?? [];
    const sorted = [...data.records].sort((a, b) => compareCompareRecords(a, b, sortKey));
    return sortDir === 'desc' ? sorted.reverse() : sorted;
  }, [data, sortKey, sortDir]);

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
                  <SortableHead label="Status" sortKey="status" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-[100px]" />
                  <SortableHead label="Ticker" sortKey="ticker" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-[70px]" />
                  <SortableHead label="Issuer" sortKey="issuer" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
                  <SortableHead label="Shares" sortKey="shares" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortableHead label="Prev Shares" sortKey="prev_shares" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortableHead label="Share Chg %" sortKey="share_change_pct" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortableHead label="Value ($000s)" sortKey="value" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortableHead label="Prev Value" sortKey="prev_value" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
                  <SortableHead label="Val Chg %" sortKey="value_change_pct" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedRecords.map((rec, i) => (
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

/** Compute a simple trend string from period values (e.g. "▁▃▅▇" sparkline). */
function getTrendSparkline(periods: string[], periodsData: Record<string, number | null>): string {
  const vals = periods.map((p) => periodsData[p]).filter((v): v is number => v !== null);
  if (vals.length === 0) return '';
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const bars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'];
  const range = max - min;
  return vals
    .map((v) => (range === 0 ? bars[3] : bars[Math.round(((v - min) / range) * 7)]))
    .join('');
}

type HistorySortKey = 'ticker' | 'issuer' | 'change_pct' | string;

function compareHistoryValues(a: HoldingHistoryRecord, b: HoldingHistoryRecord, key: HistorySortKey, periods: string[]): number {
  if (key === 'ticker') return (a.ticker ?? '').localeCompare(b.ticker ?? '');
  if (key === 'issuer') return a.issuer.localeCompare(b.issuer);
  if (key === 'change_pct') return (a.change_pct ?? 0) - (b.change_pct ?? 0);
  if (periods.includes(key)) return (a.periods_data[key] ?? 0) - (b.periods_data[key] ?? 0);
  return 0;
}

function HoldingHistorySection({ accessionNo }: { accessionNo: string }) {
  const [data, setData] = useState<HoldingHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const { sortKey, sortDir, handleSort, reset: resetSort } = useSort<HistorySortKey>('desc');

  // Reset when accessionNo changes
  useEffect(() => {
    setData(null);
    setLoading(false);
    setError(null);
    setLoaded(false);
    resetSort();
  }, [accessionNo]);

  const sortedRecords = useMemo(() => {
    if (!data || !sortKey) return data?.records ?? [];
    const sorted = [...data.records].sort((a, b) => compareHistoryValues(a, b, sortKey, data.periods));
    return sortDir === 'desc' ? sorted.reverse() : sorted;
  }, [data, sortKey, sortDir]);

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
                  <SortableHead label="Ticker" sortKey="ticker" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-[70px]" />
                  <SortableHead label="Issuer" sortKey="issuer" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
                  {data.periods.map((period) => (
                    <SortableHead key={period} label={period} sortKey={period} currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right text-xs whitespace-nowrap" />
                  ))}
                  <TableHead className="w-[80px] text-center text-xs">Trend</TableHead>
                  <SortableHead label="Chg%" sortKey="change_pct" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right w-[70px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedRecords.map((rec, i) => (
                  <TableRow key={`${rec.cusip}-${i}`}>
                    <TableCell className="text-xs font-mono font-medium">{rec.ticker ?? '—'}</TableCell>
                    <TableCell className="text-sm">{rec.issuer}</TableCell>
                    {data.periods.map((period) => (
                      <TableCell key={period} className="text-right text-xs tabular-nums">
                        {formatNumber(rec.periods_data[period] ?? null)}
                      </TableCell>
                    ))}
                    <TableCell className="text-center text-xs tracking-tight font-mono">
                      {getTrendSparkline(data.periods, rec.periods_data)}
                    </TableCell>
                    <TableCell className={`text-right text-xs tabular-nums font-medium ${rec.change_pct !== null && rec.change_pct > 0 ? 'text-green-600' : rec.change_pct !== null && rec.change_pct < 0 ? 'text-red-600' : ''}`}>
                      {rec.change_pct !== null ? `${rec.change_pct > 0 ? '+' : ''}${rec.change_pct.toFixed(1)}%` : '—'}
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
// Aggregate Holdings table (grouped by ticker across companies)
// ---------------------------------------------------------------------------

type AggregateSortKey = 'ticker' | 'issuer' | 'companies' | 'total_shares' | 'total_prev_shares' | 'avg_share_change_pct' | 'total_value' | 'total_prev_value' | 'avg_value_change_pct';

function compareAggregateRecords(a: AggregateHoldingRecord, b: AggregateHoldingRecord, key: AggregateSortKey): number {
  if (key === 'ticker') return a.ticker.localeCompare(b.ticker);
  if (key === 'issuer') return a.issuer.localeCompare(b.issuer);
  if (key === 'companies') return a.companies - b.companies;
  if (key === 'total_shares') return a.total_shares - b.total_shares;
  if (key === 'total_prev_shares') return a.total_prev_shares - b.total_prev_shares;
  if (key === 'avg_share_change_pct') return (a.avg_share_change_pct ?? 0) - (b.avg_share_change_pct ?? 0);
  if (key === 'total_value') return a.total_value - b.total_value;
  if (key === 'total_prev_value') return a.total_prev_value - b.total_prev_value;
  if (key === 'avg_value_change_pct') return (a.avg_value_change_pct ?? 0) - (b.avg_value_change_pct ?? 0);
  return 0;
}

function AggregateHoldingsTable({ data }: { data: AggregateHoldingsResponse }) {
  const { sortKey, sortDir, handleSort } = useSort<AggregateSortKey>('desc');
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  const sortedRecords = useMemo(() => {
    if (!sortKey) return data.records;
    const sorted = [...data.records].sort((a, b) => compareAggregateRecords(a, b, sortKey));
    return sortDir === 'desc' ? sorted.reverse() : sorted;
  }, [data.records, sortKey, sortDir]);

  const toggleExpand = (ticker: string) => {
    setExpandedTicker((prev) => (prev === ticker ? null : ticker));
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Aggregate Holdings</h3>
        <span className="text-xs text-muted-foreground">
          {data.total} tickers across {data.companies_processed} companies
          {data.errors.length > 0 && ` (${data.errors.length} failed)`}
        </span>
      </div>

      {data.errors.length > 0 && (
        <div className="rounded-md bg-yellow-50 dark:bg-yellow-900/20 p-2 text-xs text-yellow-800 dark:text-yellow-200">
          Could not load data for: {data.errors.join(', ')}
        </div>
      )}

      <div className="rounded-md border overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[30px]" />
              <SortableHead label="Ticker" sortKey="ticker" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-[80px]" />
              <SortableHead label="Issuer" sortKey="issuer" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
              <SortableHead label="# Companies" sortKey="companies" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right w-[100px]" />
              <SortableHead label="Total Shares" sortKey="total_shares" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Prev Shares" sortKey="total_prev_shares" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Avg Share Chg %" sortKey="avg_share_change_pct" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Total Value ($000s)" sortKey="total_value" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Prev Value" sortKey="total_prev_value" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Avg Val Chg %" sortKey="avg_value_change_pct" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedRecords.map((rec) => {
              const isExpanded = expandedTicker === rec.ticker;
              return (
                <>
                  <TableRow
                    key={rec.ticker}
                    className="cursor-pointer hover:bg-accent/30"
                    onClick={() => toggleExpand(rec.ticker)}
                  >
                    <TableCell className="px-2">
                      {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </TableCell>
                    <TableCell className="text-xs font-mono font-medium">{rec.ticker}</TableCell>
                    <TableCell className="text-sm">{rec.issuer}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums font-medium">{rec.companies}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.total_shares)}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.total_prev_shares)}</TableCell>
                    <TableCell className={`text-right text-xs tabular-nums ${rec.avg_share_change_pct !== null && rec.avg_share_change_pct > 0 ? 'text-green-600' : rec.avg_share_change_pct !== null && rec.avg_share_change_pct < 0 ? 'text-red-600' : ''}`}>
                      {rec.avg_share_change_pct !== null ? `${rec.avg_share_change_pct > 0 ? '+' : ''}${rec.avg_share_change_pct.toFixed(1)}%` : '—'}
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.total_value)}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatNumber(rec.total_prev_value)}</TableCell>
                    <TableCell className={`text-right text-xs tabular-nums ${rec.avg_value_change_pct !== null && rec.avg_value_change_pct > 0 ? 'text-green-600' : rec.avg_value_change_pct !== null && rec.avg_value_change_pct < 0 ? 'text-red-600' : ''}`}>
                      {rec.avg_value_change_pct !== null ? `${rec.avg_value_change_pct > 0 ? '+' : ''}${rec.avg_value_change_pct.toFixed(1)}%` : '—'}
                    </TableCell>
                  </TableRow>
                  {isExpanded && rec.company_details.map((detail) => (
                    <TableRow key={`${rec.ticker}-${detail.cik}`} className="bg-muted/30">
                      <TableCell />
                      <TableCell className="text-xs pl-6">
                        <StatusBadge status={detail.status} />
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground" colSpan={2}>{detail.company}</TableCell>
                      <TableCell className="text-right text-xs tabular-nums">{formatNumber(detail.shares)}</TableCell>
                      <TableCell className="text-right text-xs tabular-nums">{formatNumber(detail.prev_shares)}</TableCell>
                      <TableCell className={`text-right text-xs tabular-nums ${detail.share_change_pct !== null && detail.share_change_pct > 0 ? 'text-green-600' : detail.share_change_pct !== null && detail.share_change_pct < 0 ? 'text-red-600' : ''}`}>
                        {detail.share_change_pct !== null ? `${detail.share_change_pct > 0 ? '+' : ''}${detail.share_change_pct.toFixed(1)}%` : '—'}
                      </TableCell>
                      <TableCell className="text-right text-xs tabular-nums">{formatNumber(detail.value)}</TableCell>
                      <TableCell className="text-right text-xs tabular-nums">{formatNumber(detail.prev_value)}</TableCell>
                      <TableCell className={`text-right text-xs tabular-nums ${detail.value_change_pct !== null && detail.value_change_pct > 0 ? 'text-green-600' : detail.value_change_pct !== null && detail.value_change_pct < 0 ? 'text-red-600' : ''}`}>
                        {detail.value_change_pct !== null ? `${detail.value_change_pct > 0 ? '+' : ''}${detail.value_change_pct.toFixed(1)}%` : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Flows: types, derivation, and comparator
// ---------------------------------------------------------------------------

interface FlowRow {
  status: string;
  company: string;
  cik: number;
  ticker: string;
  issuer: string;
  shares: number | null;
  prev_shares: number | null;
  share_change_pct: number | null;
  value: number | null;
  prev_value: number | null;
  value_change_pct: number | null;
}

function deriveFlowRows(data: AggregateHoldingsResponse): FlowRow[] {
  return data.records
    .flatMap((rec) =>
      rec.company_details
        .filter((d) => d.status.toUpperCase() !== 'UNCHANGED')
        .map((d) => ({
          status: d.status,
          company: d.company,
          cik: d.cik,
          ticker: rec.ticker,
          issuer: rec.issuer,
          shares: d.shares,
          prev_shares: d.prev_shares,
          share_change_pct: d.share_change_pct,
          value: d.value,
          prev_value: d.prev_value,
          value_change_pct: d.value_change_pct,
        }))
    )
    .sort((a, b) => Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0));
}

type FlowSortKey = 'status' | 'company' | 'ticker' | 'issuer' | 'shares' | 'prev_shares' | 'share_change_pct' | 'value' | 'prev_value' | 'value_change_pct';

function compareFlowRecords(a: FlowRow, b: FlowRow, key: FlowSortKey): number {
  if (key === 'status') return a.status.localeCompare(b.status);
  if (key === 'company') return a.company.localeCompare(b.company);
  if (key === 'ticker') return a.ticker.localeCompare(b.ticker);
  if (key === 'issuer') return a.issuer.localeCompare(b.issuer);
  if (key === 'shares') return (a.shares ?? 0) - (b.shares ?? 0);
  if (key === 'prev_shares') return (a.prev_shares ?? 0) - (b.prev_shares ?? 0);
  if (key === 'share_change_pct') return (a.share_change_pct ?? 0) - (b.share_change_pct ?? 0);
  if (key === 'value') return (a.value ?? 0) - (b.value ?? 0);
  if (key === 'prev_value') return (a.prev_value ?? 0) - (b.prev_value ?? 0);
  if (key === 'value_change_pct') return (a.value_change_pct ?? 0) - (b.value_change_pct ?? 0);
  return 0;
}

// ---------------------------------------------------------------------------
// Flows panel component
// ---------------------------------------------------------------------------

const ALL_FLOW_STATUSES = ['NEW', 'CLOSED', 'INCREASED', 'DECREASED'] as const;

const STATUS_COLORS: Record<string, { bg: string; text: string; activeBg: string }> = {
  NEW: { bg: 'bg-green-100', text: 'text-green-800', activeBg: 'bg-green-600 text-white hover:bg-green-700' },
  CLOSED: { bg: 'bg-red-100', text: 'text-red-800', activeBg: 'bg-red-600 text-white hover:bg-red-700' },
  INCREASED: { bg: 'bg-blue-100', text: 'text-blue-800', activeBg: 'bg-blue-600 text-white hover:bg-blue-700' },
  DECREASED: { bg: 'bg-orange-100', text: 'text-orange-800', activeBg: 'bg-orange-500 text-white hover:bg-orange-600' },
};

function FlowsPanel({ data }: { data: AggregateHoldingsResponse }) {
  const [statusFilter, setStatusFilter] = useState<Set<string>>(new Set(ALL_FLOW_STATUSES));
  const [tickerSearch, setTickerSearch] = useState('');
  const [minValueStr, setMinValueStr] = useState('');
  const { sortKey, sortDir, handleSort } = useSort<FlowSortKey>('desc');

  const allRows = useMemo(() => deriveFlowRows(data), [data]);

  const summary = useMemo(() => {
    const counts = { NEW: 0, CLOSED: 0, INCREASED: 0, DECREASED: 0 };
    for (const row of allRows) {
      const key = row.status.toUpperCase();
      if (key in counts) counts[key as keyof typeof counts]++;
    }
    return counts;
  }, [allRows]);

  const filteredRows = useMemo(() => {
    const minVal = minValueStr ? parseFloat(minValueStr) : null;
    return allRows.filter((row) => {
      if (!statusFilter.has(row.status.toUpperCase())) return false;
      if (tickerSearch && !row.ticker.toLowerCase().includes(tickerSearch.toLowerCase())) return false;
      if (minVal !== null && Math.abs(row.value ?? 0) < minVal) return false;
      return true;
    });
  }, [allRows, statusFilter, tickerSearch, minValueStr]);

  const sortedRows = useMemo(() => {
    if (!sortKey) return filteredRows;
    const sorted = [...filteredRows].sort((a, b) => compareFlowRecords(a, b, sortKey));
    return sortDir === 'desc' ? sorted.reverse() : sorted;
  }, [filteredRows, sortKey, sortDir]);

  const toggleStatus = (status: string) => {
    setStatusFilter((prev) => {
      const next = new Set(prev);
      if (next.has(status)) {
        next.delete(status);
      } else {
        next.add(status);
      }
      return next;
    });
  };

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {ALL_FLOW_STATUSES.map((status) => {
          const colors = STATUS_COLORS[status];
          return (
            <div key={status} className={`rounded-lg border p-3 ${colors.bg}`}>
              <div className={`text-xs font-medium ${colors.text}`}>{status}</div>
              <div className={`text-2xl font-bold ${colors.text}`}>{summary[status]}</div>
              <div className={`text-xs ${colors.text} opacity-70`}>positions</div>
            </div>
          );
        })}
      </div>

      {/* Filter bar */}
      <div className="flex gap-2 flex-wrap items-center">
        {ALL_FLOW_STATUSES.map((status) => {
          const active = statusFilter.has(status);
          const colors = STATUS_COLORS[status];
          return (
            <Button
              key={status}
              variant={active ? 'default' : 'outline'}
              size="sm"
              className={`text-xs ${active ? colors.activeBg : ''}`}
              onClick={() => toggleStatus(status)}
            >
              {status} ({summary[status]})
            </Button>
          );
        })}
        <div className="relative max-w-[160px]">
          <Input
            type="text"
            placeholder="Filter by ticker…"
            value={tickerSearch}
            onChange={(e) => setTickerSearch(e.target.value)}
            className="text-xs pr-7"
          />
          {tickerSearch && (
            <button
              type="button"
              onClick={() => setTickerSearch('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label="Clear ticker search"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
        <div className="relative max-w-[140px]">
          <Input
            type="text"
            placeholder="Min value ($)…"
            value={minValueStr}
            onChange={(e) => setMinValueStr(e.target.value.replace(/[^0-9.]/g, ''))}
            className="text-xs pr-7"
          />
          {minValueStr && (
            <button
              type="button"
              onClick={() => setMinValueStr('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label="Clear min value"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Showing {sortedRows.length} of {allRows.length} flows
      </p>

      {/* Flow table */}
      <div className="rounded-md border overflow-auto max-h-[600px]">
        <Table>
          <TableHeader>
            <TableRow>
              <SortableHead label="Status" sortKey="status" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-[90px]" />
              <SortableHead label="Company" sortKey="company" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
              <SortableHead label="Ticker" sortKey="ticker" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="w-[80px]" />
              <SortableHead label="Issuer" sortKey="issuer" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
              <SortableHead label="Shares" sortKey="shares" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Prev Shares" sortKey="prev_shares" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Chg %" sortKey="share_change_pct" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right w-[80px]" />
              <SortableHead label="Value ($000s)" sortKey="value" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Prev Value" sortKey="prev_value" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Val Chg %" sortKey="value_change_pct" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right w-[80px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedRows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={10} className="text-center text-sm text-muted-foreground py-8">
                  No flows match the current filters.
                </TableCell>
              </TableRow>
            ) : (
              sortedRows.map((row, i) => (
                <TableRow key={`${row.cik}-${row.ticker}-${i}`}>
                  <TableCell><StatusBadge status={row.status} /></TableCell>
                  <TableCell className="text-xs">{row.company}</TableCell>
                  <TableCell className="text-xs font-mono font-medium">{row.ticker}</TableCell>
                  <TableCell className="text-xs">{row.issuer}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums">{formatNumber(row.shares)}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums">{formatNumber(row.prev_shares)}</TableCell>
                  <TableCell className={`text-right text-xs tabular-nums ${row.share_change_pct !== null && row.share_change_pct > 0 ? 'text-green-600' : row.share_change_pct !== null && row.share_change_pct < 0 ? 'text-red-600' : ''}`}>
                    {row.share_change_pct !== null ? `${row.share_change_pct > 0 ? '+' : ''}${row.share_change_pct.toFixed(1)}%` : '—'}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums">{formatNumber(row.value)}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums">{formatNumber(row.prev_value)}</TableCell>
                  <TableCell className={`text-right text-xs tabular-nums ${row.value_change_pct !== null && row.value_change_pct > 0 ? 'text-green-600' : row.value_change_pct !== null && row.value_change_pct < 0 ? 'text-red-600' : ''}`}>
                    {row.value_change_pct !== null ? `${row.value_change_pct > 0 ? '+' : ''}${row.value_change_pct.toFixed(1)}%` : '—'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
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
  const [signerSearch, setSignerSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedCompanies, setSelectedCompanies] = useState<Set<string>>(new Set());
  const [allCompanies, setAllCompanies] = useState<ThirteenFCompanyItem[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(false);
  // Track the CIKs currently applied as a filter (only changes on Save/Clear, not on checkbox toggle)
  const [activeCiks, setActiveCiks] = useState<number[] | undefined>(undefined);
  // Date range filter
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  // Aggregate holdings state
  const [aggregateData, setAggregateData] = useState<AggregateHoldingsResponse | null>(null);
  const [aggregateLoading, setAggregateLoading] = useState(false);
  const [aggregateError, setAggregateError] = useState<string | null>(null);
  // View toggle: aggregate table vs flows panel
  const [activeView, setActiveView] = useState<'aggregate' | 'flows'>('aggregate');

  // Helper: fetch filings with given CIKs
  const fetchFilings = useCallback(
    (searchTerm: string, ciks: number[] | undefined, fromDate?: string, toDate?: string) => {
      setLoading(true);
      setError(null);
      setOffset(0);
      insiderService
        .getThirteenFFilings(PAGE_SIZE, 0, undefined, undefined, searchTerm || undefined, ciks, fromDate || undefined, toDate || undefined)
        .then((result) => {
          setFilings(result.filings);
          setTotal(result.total);
          setHasMore(result.has_more);
          setOffset(PAGE_SIZE);
        })
        .catch((e) => {
          setError(e instanceof Error ? e.message : 'Failed to fetch 13F filings');
        })
        .finally(() => {
          setLoading(false);
        });
    },
    [],
  );

  // Load all company names + saved selections on mount
  useEffect(() => {
    let cancelled = false;
    setCompaniesLoading(true);

    Promise.all([
      insiderService.getThirteenFCompanies(),
      insiderService.getThirteenFSelections(),
    ])
      .then(([companiesRes, selectionsRes]) => {
        if (cancelled) return;
        setAllCompanies(companiesRes.companies);

        if (selectionsRes.selections.length > 0) {
          const names = new Set(selectionsRes.selections.map((s) => s.company));
          const ciks = selectionsRes.selections.map((s) => s.cik);
          setSelectedCompanies(names);
          setActiveCiks(ciks);
          fetchFilings('', ciks);
        } else {
          fetchFilings('', undefined);
        }
      })
      .catch(() => {
        // Fallback: load filings without selections
        fetchFilings('', undefined);
      })
      .finally(() => {
        if (!cancelled) setCompaniesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounce company search input by 400ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(companySearch);
    }, 400);
    return () => clearTimeout(timer);
  }, [companySearch]);

  // Reload filings when debounced search changes (NOT when selections change — that's manual via Save)
  const isFirstRender = useRef(true);
  useEffect(() => {
    // Skip the first render — initial fetch is handled by the mount effect
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    fetchFilings(debouncedSearch, activeCiks, dateFrom || undefined, dateTo || undefined);
  }, [debouncedSearch, dateFrom, dateTo]); // eslint-disable-line react-hooks/exhaustive-deps

  // Save handler: persist selections to DB and apply filter
  const handleSaveCompanies = useCallback(
    (selected: Set<string>) => {
      setSelectedCompanies(selected);
      const cikMap = new Map(allCompanies.map((c) => [c.company, c.cik]));
      const ciks: number[] = [];
      for (const name of selected) {
        const cik = cikMap.get(name);
        if (cik !== undefined) ciks.push(cik);
      }
      const newCiks = ciks.length > 0 ? ciks : undefined;
      setActiveCiks(newCiks);
      setAggregateData(null);
      setAggregateError(null);
      setActiveView('aggregate');
      // Persist to DB (fire-and-forget)
      insiderService.saveThirteenFSelections(ciks).catch(() => {});
      // Apply filter
      fetchFilings(debouncedSearch, newCiks, dateFrom || undefined, dateTo || undefined);
    },
    [allCompanies, debouncedSearch, dateFrom, dateTo, fetchFilings],
  );

  // Clear handler: remove saved selections from DB and reset filter
  const handleClearCompanies = useCallback(() => {
    setSelectedCompanies(new Set());
    setActiveCiks(undefined);
    setAggregateData(null);
    setAggregateError(null);
    setActiveView('aggregate');
    // Clear DB (fire-and-forget)
    insiderService.saveThirteenFSelections([]).catch(() => {});
    // Reload unfiltered
    fetchFilings(debouncedSearch, undefined, dateFrom || undefined, dateTo || undefined);
  }, [debouncedSearch, dateFrom, dateTo, fetchFilings]);

  // Aggregate handler: fetch aggregated holdings for active CIKs
  const handleAggregate = useCallback(() => {
    if (!activeCiks || activeCiks.length === 0) return;
    setAggregateLoading(true);
    setAggregateError(null);
    insiderService
      .getAggregateHoldings(activeCiks)
      .then((result) => {
        setAggregateData(result);
      })
      .catch((e) => {
        setAggregateError(e instanceof Error ? e.message : 'Failed to fetch aggregate holdings');
      })
      .finally(() => {
        setAggregateLoading(false);
      });
  }, [activeCiks]);

  const handleLoadMore = () => {
    setLoadingMore(true);
    insiderService
      .getThirteenFFilings(PAGE_SIZE, offset, undefined, undefined, debouncedSearch || undefined, activeCiks, dateFrom || undefined, dateTo || undefined)
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

  const handleClearSignerSearch = () => {
    setSignerSearch('');
  };

  // Client-side filter: signer name (company filter is server-side via CIKs)
  const filteredFilings = useMemo(() => {
    if (!signerSearch.trim()) return filings;
    const q = signerSearch.trim().toLowerCase();
    return filings.filter((f) => f.signer_name?.toLowerCase().includes(q));
  }, [filings, signerSearch]);

  if (loading) return <ThirteenFSkeleton />;

  if (error) {
    return <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>;
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-3 flex-wrap items-center">
        <div className="relative max-w-sm flex-1 min-w-[200px]">
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
              aria-label="Clear company search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <CompanyMultiSelect
          companies={allCompanies}
          selected={selectedCompanies}
          onSave={handleSaveCompanies}
          onClear={handleClearCompanies}
          loading={companiesLoading}
        />
        <Input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="w-[150px] text-xs"
          placeholder="From date"
        />
        <Input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="w-[150px] text-xs"
          placeholder="To date"
        />
        {(dateFrom || dateTo) && (
          <button
            type="button"
            onClick={() => { setDateFrom(''); setDateTo(''); }}
            className="text-xs text-muted-foreground hover:text-foreground"
            aria-label="Clear date filter"
          >
            <X className="h-4 w-4" />
          </button>
        )}
        {activeCiks && activeCiks.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleAggregate}
            disabled={aggregateLoading}
            className="text-xs"
          >
            {aggregateLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Aggregating…
              </>
            ) : (
              'Aggregate Holdings'
            )}
          </Button>
        )}
        <div className="relative max-w-sm flex-1 min-w-[200px]">
          <Input
            type="text"
            placeholder="Filter by signer name..."
            value={signerSearch}
            onChange={(e) => setSignerSearch(e.target.value)}
            className="pr-8"
          />
          {signerSearch && (
            <button
              type="button"
              onClick={handleClearSignerSearch}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label="Clear signer search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {total > 0 && (
        <p className="text-xs text-muted-foreground">
          Showing {filteredFilings.length} of {formatNumber(total)} filings{selectedCompanies.size > 0 || signerSearch ? ' (filtered)' : ''}. Click a row to view holdings detail.
        </p>
      )}

      <FilingsTable
        filings={filteredFilings}
        hasMore={hasMore}
        loadingMore={loadingMore}
        onRowClick={handleRowClick}
        onLoadMore={handleLoadMore}
      />

      {aggregateError && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{aggregateError}</div>
      )}

      {aggregateData && (
        <div className="border-t pt-4 space-y-4">
          <Tabs value={activeView} onValueChange={(v) => setActiveView(v as 'aggregate' | 'flows')}>
            <TabsList>
              <TabsTrigger value="aggregate">Aggregate</TabsTrigger>
              <TabsTrigger value="flows">Flows</TabsTrigger>
            </TabsList>
          </Tabs>
          {activeView === 'aggregate' && <AggregateHoldingsTable data={aggregateData} />}
          {activeView === 'flows' && <FlowsPanel data={aggregateData} />}
        </div>
      )}

      <FilingDetailSheet
        filing={selectedFiling}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </div>
  );
}
