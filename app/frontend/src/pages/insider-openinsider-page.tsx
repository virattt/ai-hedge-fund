import { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, Loader2, RefreshCw } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  insiderService,
  type OpenInsiderRecord,
  type OpenInsiderResponse,
} from '@/services/insider-api';
import { SubNavLink } from '@/components/insider/insider-sub-nav';
import { formatNumber, formatPrice, formatValue } from '@/utils/format';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PRESETS: Record<string, { label: string; description: string }> = {
  ceo_cfo_conviction: {
    label: 'CEO/CFO Conviction',
    description: 'Buys & sells ≥ $100K by CEOs and CFOs in the last 30 days.',
  },
  cluster_buy: {
    label: 'Cluster Buy',
    description: 'Tickers with ≥ 3 insiders buying ≥ $25K each in the last 90 days.',
  },
  cluster_sell: {
    label: 'Cluster Sell',
    description: 'Tickers with ≥ 3 insiders selling ≥ $25K each in the last 90 days.',
  },
  significant_increase: {
    label: 'Significant Increase',
    description: 'Insiders increasing holdings by ≥ 20% in the last 90 days.',
  },
  screener: {
    label: 'Screener',
    description: 'All insider trades (buys & sells) in the last 30 days.',
  },
};

type PresetKey = keyof typeof PRESETS;

// ---------------------------------------------------------------------------
// Trade type badge (color-coded green=purchase, red=sale)
// ---------------------------------------------------------------------------

function TradeTypeBadge({ tradeType }: { tradeType: string }) {
  const lower = tradeType.toLowerCase();
  const isPurchase = lower.includes('purchase') || lower.startsWith('p');
  const isSale = lower.includes('sale') || lower.startsWith('s');

  if (isPurchase) {
    return (
      <Badge variant="outline" className="text-green-600 border-green-600 whitespace-nowrap">
        {tradeType}
      </Badge>
    );
  }
  if (isSale) {
    return (
      <Badge variant="outline" className="text-red-600 border-red-600 whitespace-nowrap">
        {tradeType}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="whitespace-nowrap">
      {tradeType}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Sortable results table
// ---------------------------------------------------------------------------

type SortKey = keyof OpenInsiderRecord;
type SortDir = 'asc' | 'desc';

function parseNumericDelta(raw: string | null): number | null {
  if (!raw) return null;
  const n = parseFloat(raw.replace(/[^0-9.\-+]/g, ''));
  return isNaN(n) ? null : n;
}

function compareFn(a: OpenInsiderRecord, b: OpenInsiderRecord, key: SortKey, dir: SortDir): number {
  let av: string | number | null;
  let bv: string | number | null;
  if (key === 'delta_own') {
    av = parseNumericDelta(a.delta_own);
    bv = parseNumericDelta(b.delta_own);
  } else {
    av = a[key];
    bv = b[key];
  }
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
  return dir === 'asc' ? cmp : -cmp;
}

interface SortableHeadProps {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey | null;
  dir: SortDir;
  onSort: (key: SortKey) => void;
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

function OpenInsiderTable({ records }: { records: OpenInsiderRecord[] }) {
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    if (!sortKey) return records;
    return [...records].sort((a, b) => compareFn(a, b, sortKey, sortDir));
  }, [records, sortKey, sortDir]);

  if (records.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">
        No records found for this screener.
      </div>
    );
  }

  const hp = { activeKey: sortKey, dir: sortDir, onSort: handleSort };

  return (
    <div className="rounded-md border overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <SortableHead label="Filing Date" sortKey="filing_date" className="w-[105px]" {...hp} />
            <SortableHead label="Trade Date" sortKey="trade_date" className="w-[105px]" {...hp} />
            <SortableHead label="Ticker" sortKey="ticker" className="w-[70px]" {...hp} />
            <SortableHead label="Company" sortKey="company_name" {...hp} />
            <SortableHead label="Insider" sortKey="insider_name" {...hp} />
            <SortableHead label="Title" sortKey="title" {...hp} />
            <SortableHead label="Type" sortKey="trade_type" {...hp} />
            <SortableHead label="Price" sortKey="price" className="text-right" {...hp} />
            <SortableHead label="Qty" sortKey="qty" className="text-right" {...hp} />
            <SortableHead label="Value" sortKey="value" className="text-right" {...hp} />
            <SortableHead label="Owned" sortKey="owned" className="text-right" {...hp} />
            <SortableHead label="ΔOwn" sortKey="delta_own" className="text-right" {...hp} />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((rec, i) => (
            <TableRow key={`${rec.ticker}-${rec.filing_date}-${i}`}>
              <TableCell className="text-xs whitespace-nowrap">{rec.filing_date}</TableCell>
              <TableCell className="text-xs whitespace-nowrap">{rec.trade_date}</TableCell>
              <TableCell className="font-mono text-xs font-semibold">{rec.ticker}</TableCell>
              <TableCell className="text-xs max-w-[160px] truncate">{rec.company_name}</TableCell>
              <TableCell className="text-xs font-medium max-w-[140px] truncate">
                {rec.insider_name}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground max-w-[120px] truncate">
                {rec.title}
              </TableCell>
              <TableCell>
                <TradeTypeBadge tradeType={rec.trade_type} />
              </TableCell>
              <TableCell className="text-right text-xs tabular-nums">
                {formatPrice(rec.price)}
              </TableCell>
              <TableCell className="text-right text-xs tabular-nums">
                {formatNumber(rec.qty)}
              </TableCell>
              <TableCell className="text-right text-xs tabular-nums">
                {formatValue(rec.value)}
              </TableCell>
              <TableCell className="text-right text-xs tabular-nums">
                {formatNumber(rec.owned)}
              </TableCell>
              <TableCell className="text-right text-xs tabular-nums">
                {rec.delta_own ?? '—'}
              </TableCell>
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
    <div className="space-y-2">
      <Skeleton className="h-8 w-full" />
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom filter form
// ---------------------------------------------------------------------------

interface CustomFilters {
  ticker: string;
  min_value: string;
  filing_days: string;
  min_delta_own: string;
  min_insiders: string;
  officer_filter: string;
  transaction_type: string;
}

const DEFAULT_CUSTOM: CustomFilters = {
  ticker: '',
  min_value: '',
  filing_days: '30',
  min_delta_own: '',
  min_insiders: '',
  officer_filter: 'any',
  transaction_type: 'purchase',
};

interface CustomFilterFormProps {
  filters: CustomFilters;
  onChange: (filters: CustomFilters) => void;
  onSearch: () => void;
  loading: boolean;
}

function CustomFilterForm({ filters, onChange, onSearch, loading }: CustomFilterFormProps) {
  const set = (key: keyof CustomFilters) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange({ ...filters, [key]: e.target.value });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Ticker</label>
          <Input
            placeholder="e.g. AAPL"
            value={filters.ticker}
            onChange={set('ticker')}
            className="h-8 text-sm uppercase"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Min Value ($)</label>
          <Input
            type="number"
            placeholder="e.g. 50000"
            value={filters.min_value}
            onChange={set('min_value')}
            className="h-8 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Filing Days</label>
          <Input
            type="number"
            placeholder="30"
            value={filters.filing_days}
            onChange={set('filing_days')}
            className="h-8 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Min ΔOwn%</label>
          <Input
            type="number"
            placeholder="e.g. 10"
            value={filters.min_delta_own}
            onChange={set('min_delta_own')}
            className="h-8 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Min Insiders</label>
          <Input
            type="number"
            placeholder="e.g. 2"
            value={filters.min_insiders}
            onChange={set('min_insiders')}
            className="h-8 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Officer Filter</label>
          <select
            value={filters.officer_filter}
            onChange={set('officer_filter')}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="any">Any</option>
            <option value="ceo_cfo">CEO / CFO</option>
            <option value="officer">Officer</option>
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Transaction Type</label>
          <select
            value={filters.transaction_type}
            onChange={set('transaction_type')}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="purchase">Purchase</option>
            <option value="sale">Sale</option>
            <option value="all">All</option>
          </select>
        </div>
      </div>
      <Button onClick={onSearch} disabled={loading} size="sm">
        {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
        Search
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// InsiderOpeninsiderPage
// ---------------------------------------------------------------------------

export function InsiderOpeninsiderPage() {
  const [activeTab, setActiveTab] = useState<string>('ceo_cfo_conviction');
  const [records, setRecords] = useState<OpenInsiderRecord[]>([]);
  const [response, setResponse] = useState<OpenInsiderResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customFilters, setCustomFilters] = useState<CustomFilters>(DEFAULT_CUSTOM);

  const isPresetTab = activeTab in PRESETS;

  const fetchData = async (preset: string, customParams?: Record<string, string>) => {
    setLoading(true);
    setError(null);
    setRecords([]);
    setResponse(null);
    try {
      const result = await insiderService.getOpenInsiderScreener(preset, customParams);
      setResponse(result);
      setRecords(result.records);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch OpenInsider data');
    } finally {
      setLoading(false);
    }
  };

  // Auto-fetch when switching to a preset tab
  useEffect(() => {
    if (isPresetTab) {
      fetchData(activeTab);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const handleCustomSearch = () => {
    const params: Record<string, string> = {};
    if (customFilters.ticker.trim()) params.ticker = customFilters.ticker.trim().toUpperCase();
    if (customFilters.min_value) params.min_value = customFilters.min_value;
    if (customFilters.filing_days) params.filing_days = customFilters.filing_days;
    if (customFilters.min_delta_own) params.min_delta_own = customFilters.min_delta_own;
    if (customFilters.min_insiders) params.min_insiders = customFilters.min_insiders;
    if (customFilters.officer_filter) params.officer_filter = customFilters.officer_filter;
    if (customFilters.transaction_type) params.transaction_type = customFilters.transaction_type;
    fetchData('custom', params);
  };

  const handleRetry = () => {
    if (isPresetTab) {
      fetchData(activeTab);
    } else {
      handleCustomSearch();
    }
  };

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header with sub-nav */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold">OpenInsider Screener</h1>
          <p className="text-sm text-muted-foreground">
            Curated insider trading data sourced from openinsider.com.
          </p>
        </div>
        <div className="flex items-center gap-1">
          <SubNavLink to="/insider" label="Edgar Insider" />
          <SubNavLink to="/insider/openinsider" label="OpenInsider" />
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {Object.entries(PRESETS).map(([key, { label }]) => (
            <TabsTrigger key={key} value={key}>
              {label}
            </TabsTrigger>
          ))}
          <TabsTrigger value="custom">Custom</TabsTrigger>
        </TabsList>

        {/* Preset tab content */}
        {(Object.keys(PRESETS) as PresetKey[]).map((key) => (
          <TabsContent key={key} value={key} className="space-y-4 mt-4">
            <p className="text-sm text-muted-foreground">{PRESETS[key].description}</p>
          </TabsContent>
        ))}

        {/* Custom tab content */}
        <TabsContent value="custom" className="space-y-4 mt-4">
          <CustomFilterForm
            filters={customFilters}
            onChange={setCustomFilters}
            onSearch={handleCustomSearch}
            loading={loading}
          />
        </TabsContent>
      </Tabs>

      {/* Cached indicator */}
      {response?.cached && (
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">
            Cached
          </Badge>
          <span className="text-xs text-muted-foreground">Results loaded from cache (up to 1h old)</span>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive flex items-center justify-between gap-3">
          <span>{error}</span>
          <Button
            variant="outline"
            size="sm"
            className="shrink-0 text-destructive border-destructive/50 hover:bg-destructive/10"
            onClick={handleRetry}
          >
            <RefreshCw className="h-3 w-3 mr-1" />
            Retry
          </Button>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && <LoadingSkeleton />}

      {/* Results */}
      {!loading && !error && response && (
        <>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {response.total} record{response.total !== 1 ? 's' : ''} found
            </span>
          </div>
          <OpenInsiderTable records={records} />
        </>
      )}

      {/* Empty state for preset tabs before first load */}
      {!loading && !error && !response && isPresetTab && (
        <div className="text-center py-20 text-muted-foreground text-sm">
          Loading screener data...
        </div>
      )}

      {/* Empty state for custom tab */}
      {!loading && !error && !response && !isPresetTab && (
        <div className="text-center py-20 text-muted-foreground text-sm">
          Set your filters above and click Search to run the custom screener.
        </div>
      )}
    </div>
  );
}
