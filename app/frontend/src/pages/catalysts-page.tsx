import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, ChevronRight, ExternalLink, Loader2, RefreshCw, Zap } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { catalystService, type InsiderPurchase, type SpinoffFiling, type SpinoffInsiderSummary } from '@/services/catalyst-api';

type SortKey = keyof SpinoffFiling;
type SortDir = 'asc' | 'desc';

interface SortableHeadProps {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  dir: SortDir;
  onSort: (key: SortKey) => void;
  className?: string;
}

function SortableHead({ label, sortKey, activeKey, dir, onSort, className = '' }: SortableHeadProps) {
  const active = activeKey === sortKey;
  return (
    <TableHead
      className={`cursor-pointer select-none hover:bg-muted/50 uppercase text-xs tracking-wider ${className}`}
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

function compare(a: SpinoffFiling, b: SpinoffFiling, key: SortKey, dir: SortDir): number {
  const av = a[key];
  const bv = b[key];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const cmp =
    typeof av === 'number' && typeof bv === 'number'
      ? av - bv
      : String(av).localeCompare(String(bv));
  return dir === 'asc' ? cmp : -cmp;
}

const formatMoney = (n: number | null | undefined): string => {
  if (n == null) return '—';
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
};

const formatShares = (n: number | null | undefined): string => {
  if (n == null) return '—';
  return n.toLocaleString();
};

const formatPrice = (n: number | null | undefined): string => {
  if (n == null) return '—';
  return `$${n.toFixed(2)}`;
};

interface InsiderState {
  loading: boolean;
  data: SpinoffInsiderSummary | null;
  error: string | null;
}

/** Throttled concurrent runner: at most `maxConcurrent` async tasks at once. */
async function runThrottled<T>(items: T[], maxConcurrent: number, fn: (item: T) => Promise<void>) {
  const queue = [...items];
  const workers = Array.from({ length: Math.min(maxConcurrent, queue.length) }, async () => {
    while (queue.length) {
      const next = queue.shift();
      if (next === undefined) return;
      try {
        await fn(next);
      } catch {
        // already captured per-row
      }
    }
  });
  await Promise.all(workers);
}

function InsiderBadge({ state }: { state: InsiderState | undefined }) {
  if (!state || state.loading) {
    return <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />;
  }
  if (state.error) {
    return <span className="text-xs text-destructive">err</span>;
  }
  if (!state.data || state.data.purchase_count === 0) {
    return <span className="text-muted-foreground text-sm">—</span>;
  }
  const { purchase_count, total_value } = state.data;
  return (
    <span
      className="font-data text-xs px-2 py-0.5 rounded border border-primary/50 bg-primary/15 text-primary inline-flex items-center gap-1.5 hud-glow"
      title={`${purchase_count} insider purchase${purchase_count === 1 ? '' : 's'}, total ${formatMoney(total_value)}`}
    >
      <span className="font-semibold">{purchase_count}</span>
      <span className="opacity-70">buys</span>
      <span className="opacity-50">·</span>
      <span>{formatMoney(total_value)}</span>
    </span>
  );
}

function InsiderDetailPanel({ purchases }: { purchases: InsiderPurchase[] }) {
  if (purchases.length === 0) {
    return (
      <div className="px-4 py-6 text-center text-sm text-muted-foreground italic">
        No insider purchases on file.
      </div>
    );
  }
  return (
    <div className="border-l-2 border-primary/40 bg-primary/5 px-4 py-3">
      <div className="text-[10px] font-data uppercase tracking-widest text-primary/70 mb-2">
        // insider buys ({purchases.length})
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="uppercase text-[10px] tracking-wider">Filing Date</TableHead>
            <TableHead className="uppercase text-[10px] tracking-wider">Insider</TableHead>
            <TableHead className="uppercase text-[10px] tracking-wider">Title</TableHead>
            <TableHead className="uppercase text-[10px] tracking-wider text-right">Shares</TableHead>
            <TableHead className="uppercase text-[10px] tracking-wider text-right">Price</TableHead>
            <TableHead className="uppercase text-[10px] tracking-wider text-right">Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {purchases.map((p, i) => (
            <TableRow key={`${p.accession_no}-${i}`}>
              <TableCell className="font-data text-xs">{p.filing_date}</TableCell>
              <TableCell className="text-xs font-medium">{p.insider_name}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{p.insider_title || '—'}</TableCell>
              <TableCell className="font-data text-xs text-right">{formatShares(p.shares)}</TableCell>
              <TableCell className="font-data text-xs text-right">{formatPrice(p.price_per_share)}</TableCell>
              <TableCell className="font-data text-xs text-right text-primary font-semibold">{formatMoney(p.value)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function CatalystsPage() {
  const [filings, setFilings] = useState<SpinoffFiling[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('filing_date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [insiders, setInsiders] = useState<Record<number, InsiderState>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Track in-flight fetches to avoid duplicate calls on re-mount
  const fetchedCiksRef = useRef<Set<number>>(new Set());

  const load = async () => {
    setLoading(true);
    setError(null);
    setInsiders({});
    fetchedCiksRef.current = new Set();
    try {
      const res = await catalystService.getSpinoffs(undefined, undefined, 100, 0);
      setFilings(res.filings);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load spin-off filings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // Lazy-load insider data for each unique CIK after filings arrive
  useEffect(() => {
    if (filings.length === 0) return;
    const uniqueCiks = Array.from(new Set(filings.map((f) => f.cik))).filter(
      (c) => !fetchedCiksRef.current.has(c),
    );
    if (uniqueCiks.length === 0) return;

    // Mark loading state for all unfetched CIKs
    setInsiders((prev) => {
      const next = { ...prev };
      for (const c of uniqueCiks) {
        if (!next[c]) next[c] = { loading: true, data: null, error: null };
        fetchedCiksRef.current.add(c);
      }
      return next;
    });

    // Throttle to 3 concurrent EDGAR queries
    runThrottled(uniqueCiks, 3, async (cik) => {
      try {
        const data = await catalystService.getSpinoffInsiders(cik);
        setInsiders((prev) => ({ ...prev, [cik]: { loading: false, data, error: null } }));
      } catch (e) {
        setInsiders((prev) => ({
          ...prev,
          [cik]: { loading: false, data: null, error: e instanceof Error ? e.message : 'error' },
        }));
      }
    });
  }, [filings]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'filing_date' ? 'desc' : 'asc');
    }
  };

  const sorted = useMemo(
    () => [...filings].sort((a, b) => compare(a, b, sortKey, sortDir)),
    [filings, sortKey, sortDir],
  );

  const toggleExpand = (accession_no: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(accession_no)) next.delete(accession_no);
      else next.add(accession_no);
      return next;
    });
  };

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Zap size={22} className="text-primary" />
            <h1 className="text-2xl font-bold text-foreground tracking-wide uppercase">Catalysts</h1>
            <span className="text-[10px] font-data uppercase tracking-widest text-primary/70">
              // spin-off tracker
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={load}
            disabled={loading}
            className="gap-1.5"
          >
            {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
            Refresh
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          Recent SEC Form 10 / 10-12B filings — companies registering as new public entities
          (often via spin-off). {total > 0 && <span className="font-data text-primary">{total} filings</span>}
          . Click a row to expand insider purchase history.
        </p>
        <div className="hud-divider" />
      </div>

      {/* Error */}
      {error && (
        <div className="border border-destructive/40 bg-destructive/10 text-destructive px-4 py-3 rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="border border-primary/25 bg-card/60 backdrop-blur-md rounded-md overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <SortableHead label="Filing Date" sortKey="filing_date" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
              <SortableHead label="Company" sortKey="company" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
              <SortableHead label="CIK" sortKey="cik" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
              <SortableHead label="Form" sortKey="form" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
              <TableHead className="uppercase text-xs tracking-wider">Insider Buys</TableHead>
              <TableHead className="uppercase text-xs tracking-wider">Document</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && filings.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin inline-block mr-2" />
                  Querying SEC EDGAR for recent spin-off filings...
                </TableCell>
              </TableRow>
            ) : sorted.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                  No spin-off filings found in the last 90 days.
                </TableCell>
              </TableRow>
            ) : (
              sorted.map((f) => {
                const isExpanded = expanded.has(f.accession_no);
                const insiderState = insiders[f.cik];
                return (
                  <Fragment key={f.accession_no}>
                    <TableRow
                      className="cursor-pointer"
                      onClick={() => toggleExpand(f.accession_no)}
                    >
                      <TableCell className="w-8 text-muted-foreground">
                        {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </TableCell>
                      <TableCell className="font-data text-sm">{f.filing_date}</TableCell>
                      <TableCell className="text-sm font-medium">{f.company}</TableCell>
                      <TableCell className="font-data text-sm text-right text-muted-foreground">
                        {f.cik}
                      </TableCell>
                      <TableCell>
                        <span className="font-data text-xs px-2 py-0.5 rounded border border-primary/40 bg-primary/10 text-primary">
                          {f.form}
                        </span>
                      </TableCell>
                      <TableCell>
                        <InsiderBadge state={insiderState} />
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        {f.primary_doc_url ? (
                          <a
                            href={f.primary_doc_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-primary hover:underline text-sm"
                          >
                            View <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : (
                          <span className="text-muted-foreground text-sm">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                    {isExpanded && (
                      <TableRow>
                        <TableCell colSpan={7} className="p-0">
                          {insiderState?.loading ? (
                            <div className="px-4 py-6 text-center text-sm text-muted-foreground">
                              <Loader2 className="h-4 w-4 animate-spin inline-block mr-2" />
                              Loading insider history...
                            </div>
                          ) : insiderState?.error ? (
                            <div className="px-4 py-3 text-sm text-destructive bg-destructive/5">
                              Error loading insider data: {insiderState.error}
                            </div>
                          ) : insiderState?.data ? (
                            <InsiderDetailPanel purchases={insiderState.data.purchases} />
                          ) : (
                            <div className="px-4 py-6 text-center text-sm text-muted-foreground italic">
                              Insider data not yet loaded.
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
