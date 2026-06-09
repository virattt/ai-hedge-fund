import React, { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, ChevronRight, Loader2, List, BarChart3, RefreshCw } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TickerLink } from '@/components/ui/ticker-link';
import {
  insiderService,
  type OpenInsiderRecord,
  type OpenInsiderResponse,
} from '@/services/insider-api';
import { SubNavLink } from '@/components/insider/insider-sub-nav';
import { formatNumber, formatPrice, formatValue } from '@/utils/format';

// ---------------------------------------------------------------------------
// Category definitions
// ---------------------------------------------------------------------------

interface PresetItem {
  label: string;
}

interface Category {
  label: string;
  items: Record<string, PresetItem>;
}

const CATEGORIES: Record<string, Category> = {
  latest: {
    label: 'Latest',
    items: {
      latest_cluster_buys: { label: 'Cluster Buys' },
      latest_penny_stock_buys: { label: 'Penny Stock Buys' },
      latest_insider_trading: { label: 'All Insider Trading' },
      latest_insider_buys: { label: 'Insider Purchases' },
      latest_insider_buys_25k: { label: 'Insider Purchases $25K+' },
      latest_officer_buys_25k: { label: 'Officer Purchases $25K+' },
      latest_ceo_cfo_buys_25k: { label: 'CEO/CFO Purchases $25K+' },
      latest_insider_sales: { label: 'Insider Sales' },
      latest_insider_sales_100k: { label: 'Insider Sales $100K+' },
      latest_officer_sales_100k: { label: 'Officer Sales $100K+' },
      latest_ceo_cfo_sales_100k: { label: 'CEO/CFO Sales $100K+' },
    },
  },
  top: {
    label: 'Top',
    items: {
      top_officer_buys_today: { label: 'Officer Purchases Today' },
      top_officer_buys_week: { label: 'Officer Purchases This Week' },
      top_officer_buys_month: { label: 'Officer Purchases This Month' },
      top_insider_buys_today: { label: 'Insider Purchases Today' },
      top_insider_buys_week: { label: 'Insider Purchases This Week' },
      top_insider_buys_month: { label: 'Insider Purchases This Month' },
      top_insider_sales_today: { label: 'Insider Sales Today' },
      top_insider_sales_week: { label: 'Insider Sales This Week' },
      top_insider_sales_month: { label: 'Insider Sales This Month' },
    },
  },
};

/** Resolve a preset key to its human-readable label. */
function getPresetLabel(key: string): string {
  if (key === 'screener') return 'Screener';
  for (const cat of Object.values(CATEGORIES)) {
    if (key in cat.items) return cat.items[key].label;
  }
  return key;
}

/** Find which category a preset key belongs to. */
function getCategoryForPreset(key: string): string | null {
  for (const [catKey, cat] of Object.entries(CATEGORIES)) {
    if (key in cat.items) return catKey;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Trade type badge (color-coded green=purchase, red=sale)
// ---------------------------------------------------------------------------

function TradeTypeBadge({ tradeType }: { tradeType: string }) {
  const lower = tradeType.toLowerCase();
  const isPurchase = lower.includes('purchase') || lower.startsWith('p');
  const isSale = lower.includes('sale') || lower.startsWith('s');

  if (isPurchase) {
    return (
      <Badge variant="outline" className="text-primary border-primary whitespace-nowrap">
        {tradeType}
      </Badge>
    );
  }
  if (isSale) {
    return (
      <Badge variant="outline" className="text-destructive border-destructive whitespace-nowrap">
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

// ---------------------------------------------------------------------------
// Ticker aggregation
// ---------------------------------------------------------------------------

interface AggregatedTicker {
  ticker: string;
  company_name: string;
  total_trades: number;
  buy_count: number;
  sell_count: number;
  total_buy_value: number;
  total_sell_value: number;
  net_value: number;
  unique_insiders: number;
  trades: OpenInsiderRecord[];
}

function isBuy(tradeType: string): boolean {
  const lower = tradeType.toLowerCase();
  return lower.includes('purchase') || lower.startsWith('p');
}

function aggregateByTicker(records: OpenInsiderRecord[]): AggregatedTicker[] {
  const map = new Map<string, { trades: OpenInsiderRecord[]; insiders: Set<string> }>();
  for (const rec of records) {
    if (!rec.ticker) continue;
    let entry = map.get(rec.ticker);
    if (!entry) {
      entry = { trades: [], insiders: new Set() };
      map.set(rec.ticker, entry);
    }
    entry.trades.push(rec);
    if (rec.insider_name) entry.insiders.add(rec.insider_name);
  }

  const result: AggregatedTicker[] = [];
  for (const [ticker, { trades, insiders }] of map) {
    let buyCount = 0, sellCount = 0, totalBuyValue = 0, totalSellValue = 0;
    for (const t of trades) {
      if (isBuy(t.trade_type)) {
        buyCount++;
        totalBuyValue += t.value ?? 0;
      } else {
        sellCount++;
        totalSellValue += t.value ?? 0;
      }
    }
    result.push({
      ticker,
      company_name: trades[0].company_name,
      total_trades: trades.length,
      buy_count: buyCount,
      sell_count: sellCount,
      total_buy_value: totalBuyValue,
      total_sell_value: totalSellValue,
      net_value: totalBuyValue - totalSellValue,
      unique_insiders: insiders.size,
      trades,
    });
  }
  return result.sort((a, b) => b.total_trades - a.total_trades);
}

type AggSortKey = keyof Omit<AggregatedTicker, 'trades' | 'company_name'> | 'company_name';

function compareAgg(a: AggregatedTicker, b: AggregatedTicker, key: AggSortKey, dir: SortDir): number {
  const av = a[key as keyof AggregatedTicker];
  const bv = b[key as keyof AggregatedTicker];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
  return dir === 'asc' ? cmp : -cmp;
}

function AggregatedTickerTable({ records }: { records: OpenInsiderRecord[] }) {
  const [sortKey, setSortKey] = useState<AggSortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  const aggregated = useMemo(() => aggregateByTicker(records), [records]);

  const sorted = useMemo(() => {
    if (!sortKey) return aggregated;
    return [...aggregated].sort((a, b) => compareAgg(a, b, sortKey, sortDir));
  }, [aggregated, sortKey, sortDir]);

  const handleSort = (key: AggSortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  if (records.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">
        No records found for this screener.
      </div>
    );
  }

  const AggHead = ({ label, sk, className = '' }: { label: string; sk: AggSortKey; className?: string }) => {
    const active = sortKey === sk;
    return (
      <TableHead className={`cursor-pointer select-none hover:bg-muted/50 ${className}`} onClick={() => handleSort(sk)}>
        <span className="inline-flex items-center gap-1">
          {label}
          {active ? (dir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />) : <ArrowUpDown className="h-3 w-3 opacity-30" />}
        </span>
      </TableHead>
    );
  };
  const dir = sortDir;

  return (
    <div className="rounded-md border overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[30px]" />
            <AggHead label="Ticker" sk="ticker" className="w-[70px]" />
            <AggHead label="Company" sk="company_name" />
            <AggHead label="Trades" sk="total_trades" className="text-right" />
            <AggHead label="Buys" sk="buy_count" className="text-right" />
            <AggHead label="Sells" sk="sell_count" className="text-right" />
            <AggHead label="Buy Value" sk="total_buy_value" className="text-right" />
            <AggHead label="Sell Value" sk="total_sell_value" className="text-right" />
            <AggHead label="Net Value" sk="net_value" className="text-right" />
            <AggHead label="Insiders" sk="unique_insiders" className="text-right" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((row) => {
            const isExpanded = expandedTicker === row.ticker;
            return (
              <React.Fragment key={row.ticker}>
                <TableRow
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => setExpandedTicker(isExpanded ? null : row.ticker)}
                >
                  <TableCell className="w-[30px] px-2">
                    {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </TableCell>
                  <TableCell><TickerLink ticker={row.ticker} /></TableCell>
                  <TableCell className="text-xs max-w-[180px] truncate">{row.company_name}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums font-medium">{row.total_trades}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums text-primary">{row.buy_count}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums text-destructive">{row.sell_count}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums text-primary">{formatValue(row.total_buy_value)}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums text-destructive">{formatValue(row.total_sell_value)}</TableCell>
                  <TableCell className={`text-right text-xs tabular-nums font-medium ${row.net_value >= 0 ? 'text-primary' : 'text-destructive'}`}>
                    {row.net_value >= 0 ? '+' : ''}{formatValue(row.net_value)}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums">{row.unique_insiders}</TableCell>
                </TableRow>
                {isExpanded && row.trades.map((t, i) => (
                  <TableRow key={`${row.ticker}-detail-${i}`} className="bg-muted/30">
                    <TableCell />
                    <TableCell className="text-xs text-muted-foreground">{t.filing_date}</TableCell>
                    <TableCell className="text-xs">{t.insider_name} <span className="text-muted-foreground">({t.title})</span></TableCell>
                    <TableCell />
                    <TableCell colSpan={2} className="text-xs">
                      <TradeTypeBadge tradeType={t.trade_type} />
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatPrice(t.price)}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatNumber(t.qty)}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{formatValue(t.value)}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{t.delta_own ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </React.Fragment>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Flat trades table
// ---------------------------------------------------------------------------

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
              <TableCell><TickerLink ticker={rec.ticker} /></TableCell>
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
// Category dropdown button
// ---------------------------------------------------------------------------

interface CategoryDropdownProps {
  categoryKey: string;
  category: Category;
  activePreset: string | null;
  onSelect: (presetKey: string) => void;
}

function CategoryDropdown({ categoryKey, category, activePreset, onSelect }: CategoryDropdownProps) {
  const activeCat = activePreset ? getCategoryForPreset(activePreset) : null;
  const isActive = activeCat === categoryKey;
  const activeLabel = isActive && activePreset ? getPresetLabel(activePreset) : null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant={isActive ? 'default' : 'outline'}
          size="sm"
          className="gap-1"
        >
          {category.label}
          {activeLabel && (
            <span className="text-xs opacity-80 ml-0.5">: {activeLabel}</span>
          )}
          <ChevronDown className="h-3.5 w-3.5 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel>{category.label}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {Object.entries(category.items).map(([key, item]) => (
          <DropdownMenuItem
            key={key}
            className={activePreset === key ? 'bg-accent font-medium' : ''}
            onClick={() => onSelect(key)}
          >
            {item.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// ---------------------------------------------------------------------------
// InsiderOpeninsiderPage
// ---------------------------------------------------------------------------

export function InsiderOpeninsiderPage() {
  const [activePreset, setActivePreset] = useState<string | null>('latest_ceo_cfo_buys_25k');
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [records, setRecords] = useState<OpenInsiderRecord[]>([]);
  const [response, setResponse] = useState<OpenInsiderResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customFilters, setCustomFilters] = useState<CustomFilters>(DEFAULT_CUSTOM);
  const [viewMode, setViewMode] = useState<'flat' | 'aggregated'>('flat');

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

  // Auto-fetch when switching to a preset
  useEffect(() => {
    if (activePreset && !isCustomMode) {
      fetchData(activePreset);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePreset]);

  const handlePresetSelect = (key: string) => {
    setIsCustomMode(false);
    setActivePreset(key);
  };

  const handleCustomMode = () => {
    setIsCustomMode(true);
    setActivePreset(null);
    setRecords([]);
    setResponse(null);
    setError(null);
  };

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
    if (activePreset && !isCustomMode) {
      fetchData(activePreset);
    } else {
      handleCustomSearch();
    }
  };

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header with sub-nav */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-wide uppercase">OpenInsider Screener</h1>
          <p className="text-sm text-muted-foreground">
            Curated insider trading data sourced from openinsider.com.
          </p>
        </div>
        <div className="flex items-center gap-1">
          <SubNavLink to="/insider" label="Edgar Insider" />
          <SubNavLink to="/insider/openinsider" label="OpenInsider" />
          <SubNavLink to="/insider/finnhub" label="Finnhub" />
          <SubNavLink to="/insider/political" label="Political" />
          <SubNavLink to="/insider/earnings" label="Earnings" />
        </div>
      </div>

      {/* Category dropdowns + Custom button */}
      <div className="flex items-center gap-2 flex-wrap">
        {Object.entries(CATEGORIES).map(([catKey, cat]) => (
          <CategoryDropdown
            key={catKey}
            categoryKey={catKey}
            category={cat}
            activePreset={isCustomMode ? null : activePreset}
            onSelect={handlePresetSelect}
          />
        ))}
        <Button
          variant={!isCustomMode && activePreset === 'screener' ? 'default' : 'outline'}
          size="sm"
          onClick={() => handlePresetSelect('screener')}
        >
          Screener
        </Button>
        <Button
          variant={isCustomMode ? 'default' : 'outline'}
          size="sm"
          onClick={handleCustomMode}
        >
          Custom
        </Button>
      </div>

      {/* Active selection label */}
      {activePreset && !isCustomMode && (
        <p className="text-sm text-muted-foreground">
          Showing: <span className="font-medium text-foreground">{getPresetLabel(activePreset)}</span>
        </p>
      )}

      {/* Custom filter form */}
      {isCustomMode && (
        <CustomFilterForm
          filters={customFilters}
          onChange={setCustomFilters}
          onSearch={handleCustomSearch}
          loading={loading}
        />
      )}

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
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">
              {response.total} record{response.total !== 1 ? 's' : ''} found
            </span>
            <div className="flex items-center gap-1 ml-auto">
              <Button
                variant={viewMode === 'flat' ? 'default' : 'outline'}
                size="sm"
                className="h-7 text-xs gap-1"
                onClick={() => setViewMode('flat')}
              >
                <List className="h-3 w-3" />
                Trades
              </Button>
              <Button
                variant={viewMode === 'aggregated' ? 'default' : 'outline'}
                size="sm"
                className="h-7 text-xs gap-1"
                onClick={() => setViewMode('aggregated')}
              >
                <BarChart3 className="h-3 w-3" />
                By Ticker
              </Button>
            </div>
          </div>
          {viewMode === 'flat' ? (
            <OpenInsiderTable records={records} />
          ) : (
            <AggregatedTickerTable records={records} />
          )}
        </>
      )}

      {/* Empty state for preset before first load */}
      {!loading && !error && !response && !isCustomMode && activePreset && (
        <div className="text-center py-20 text-muted-foreground text-sm">
          Loading screener data...
        </div>
      )}

      {/* Empty state for custom mode */}
      {!loading && !error && !response && isCustomMode && (
        <div className="text-center py-20 text-muted-foreground text-sm">
          Set your filters above and click Search to run the custom screener.
        </div>
      )}
    </div>
  );
}
