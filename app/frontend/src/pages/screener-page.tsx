import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Search, ArrowUpDown, ChevronUp, ChevronDown } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TickerLink } from '@/components/ui/ticker-link';
import { screenerService, type ScreenerFilters, type ScreenerResponse } from '@/services/screener-api';

const VIEWS = ['overview', 'valuation', 'financial', 'technical', 'performance', 'ownership'] as const;
type View = (typeof VIEWS)[number];

// Preset filter strategies
interface Preset {
  label: string;
  description: string;
  filters: Record<string, string>;
  signal: string;
  view: View;
}

const PRESETS: Record<string, Preset> = {
  undervalued: {
    label: 'Undervalued Stocks',
    description: 'Value investing — cheap relative to earnings, book value, and growth',
    filters: {
      'P/E': 'Under 15',
      'P/B': 'Under 1',
      'PEG': 'Under 1',
      'Debt/Equity': 'Under 0.5',
    },
    signal: '',
    view: 'valuation',
  },
  overvalued: {
    label: 'Overvalued Stocks',
    description: 'Expensive stocks at risk of pullback — high P/E, overbought RSI',
    filters: {
      'P/E': 'Over 50',
      'P/S': 'Over 10',
      'Price/Cash': 'Over 50',
      'RSI (14)': 'Overbought (70)',
      '20-Day Simple Moving Average': 'Price above SMA20',
      '50-Day Simple Moving Average': 'Price above SMA50',
      '200-Day Simple Moving Average': 'Price above SMA200',
    },
    signal: '',
    view: 'valuation',
  },
  good_to_buy: {
    label: 'Good to Buy',
    description: 'Growth & momentum — strong earnings growth, analyst buys, uptrend',
    filters: {
      'EPS growthnext 5 years': 'Over 15%',
      'Return on Equity': 'Over +15%',
      'Analyst Recom.': 'Buy or better',
      '20-Day Simple Moving Average': 'Price above SMA20',
      'Average Volume': 'Over 500K',
    },
    signal: '',
    view: 'overview',
  },
  better_to_sell: {
    label: 'Better to Sell',
    description: 'Bearish signals — negative EPS, high debt, analyst holds/sells, downtrend',
    filters: {
      'EPS growththis year': 'Negative (<0%)',
      'Debt/Equity': 'Over 1',
      'Analyst Recom.': 'Hold or worse',
      '20-Day Simple Moving Average': 'Price below SMA20',
      '50-Day Simple Moving Average': 'Price below SMA50',
    },
    signal: '',
    view: 'overview',
  },
};

// Filter categories matching finviz screener tabs — ordered arrays to control grid layout
const FILTER_CATEGORIES: Record<string, { label: string; filters: string[] }> = {
  descriptive: {
    label: 'Descriptive',
    // 4-column layout matching finviz: row by row, left to right
    filters: [
      'Exchange',          'Index',             'Sector',            'Industry',
      'Country',           'Market Cap.',       'Dividend Yield',    'Float Short',
      'Analyst Recom.',    'Option/Short',      'Earnings Date',     'Average Volume',
      'Relative Volume',   'Current Volume',    'Price',             'Target Price',
      'IPO Date',          'Shares Outstanding','Float',             'Net Expense Ratio',
    ],
  },
  fundamental: {
    label: 'Fundamental',
    filters: [
      // Row 1
      'P/E',                     'Forward P/E',              'PEG',                      'P/S',
      // Row 2
      'P/B',                     'Price/Cash',               'Price/Free Cash Flow',     'EPS growththis year',
      // Row 3 (EV/EBITDA, EV/Sales, Dividend Growth not in library yet)
      'EPS growthnext year',     'EPS growthqtr over qtr',   'EPS growth ttm',           'EPS growthpast 5 years',
      // Row 4
      'EPS growthnext 5 years',  'Sales growthqtr over qtr', 'Sales growthpast 5 years', 'Return on Assets',
      // Row 5
      'Return on Equity',        'Return on Investment',     'Current Ratio',            'Quick Ratio',
      // Row 6
      'LT Debt/Equity',          'Debt/Equity',              'Gross Margin',             'Operating Margin',
      // Row 7
      'Net Profit Margin',       'Payout Ratio',             'Dividend Yield',           'InsiderOwnership',
      // Row 8
      'InsiderTransactions',     'InstitutionalOwnership',   'InstitutionalTransactions','Float Short',
    ],
  },
  technical: {
    label: 'Technical',
    filters: [
      'Performance',                  'Performance 2',                'Volatility',                   'RSI (14)',
      'Gap',                          '20-Day Simple Moving Average', '50-Day Simple Moving Average', '200-Day Simple Moving Average',
      'Change',                       'Change from Open',             '20-Day High/Low',              '50-Day High/Low',
      '52-Week High/Low',             'Pattern',                      'Candlestick',                  'Beta',
      'Average True Range',
    ],
  },
  all: {
    label: 'All',
    // Matches finviz.com "All" tab order exactly
    filters: [
      // Descriptive
      'Exchange',                     'Index',                        'Sector',                       'Industry',
      'Country',                      'Market Cap.',
      // Fundamental — valuation
      'P/E',                          'Forward P/E',                  'PEG',                          'P/S',
      'P/B',                          'Price/Cash',                   'Price/Free Cash Flow',
      // Fundamental — growth
      'EPS growththis year',          'EPS growthnext year',          'EPS growthqtr over qtr',       'EPS growth ttm',
      'EPS growthpast 5 years',       'EPS growthnext 5 years',
      'Sales growthqtr over qtr',     'Sales growthpast 5 years',
      // Fundamental — profitability & ratios
      'Dividend Yield',               'Return on Assets',             'Return on Equity',             'Return on Investment',
      'Current Ratio',                'Quick Ratio',                  'LT Debt/Equity',               'Debt/Equity',
      'Gross Margin',                 'Operating Margin',             'Net Profit Margin',            'Payout Ratio',
      // Ownership
      'InsiderOwnership',             'InsiderTransactions',          'InstitutionalOwnership',       'InstitutionalTransactions',
      // Descriptive continued
      'Float Short',                  'Analyst Recom.',               'Option/Short',                 'Earnings Date',
      // Technical
      'Performance',                  'Performance 2',                'Volatility',                   'RSI (14)',
      'Gap',                          '20-Day Simple Moving Average', '50-Day Simple Moving Average', '200-Day Simple Moving Average',
      'Change',                       'Change from Open',             '20-Day High/Low',              '50-Day High/Low',
      '52-Week High/Low',             'Pattern',                      'Candlestick',                  'Beta',
      'Average True Range',
      // Descriptive — volume & price
      'Average Volume',               'Relative Volume',              'Current Volume',
      'Price',                        'Target Price',                 'IPO Date',                     'Shares Outstanding',
      'Float',                        'Net Expense Ratio',
    ],
  },
};

type FilterCategory = keyof typeof FILTER_CATEGORIES;

// Columns whose values should be color-coded green/red
const COLOR_COLUMNS = new Set(['Change', 'Perf Week', 'Perf Month', 'Perf Quart', 'Perf Half', 'Perf Year', 'Perf YTD', 'SMA20', 'SMA50', 'SMA200', 'Change from Open']);

function formatCellValue(_col: string, value: any): string {
  if (value === null || value === undefined || value === '') return '-';
  return String(value);
}

function cellColor(col: string, value: any): string {
  if (!COLOR_COLUMNS.has(col)) return '';
  const str = String(value);
  if (str.startsWith('-')) return 'text-destructive';
  if (str !== '-' && str !== '0' && str !== '0%' && str !== '0.00%') return 'text-primary';
  return '';
}

export function ScreenerPage() {
  // Filter metadata
  const [filterMeta, setFilterMeta] = useState<ScreenerFilters | null>(null);
  const [metaLoading, setMetaLoading] = useState(true);
  const [metaError, setMetaError] = useState('');

  // Search state
  const [activeFilters, setActiveFilters] = useState<Record<string, string>>({});
  const [signal, setSignal] = useState('');
  const [ticker, setTicker] = useState('');
  const [order, setOrder] = useState('Ticker');
  const [ascend, setAscend] = useState(true);
  const [limit] = useState(200);
  const [view, setView] = useState<View>('overview');

  // Results
  const [results, setResults] = useState<ScreenerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Collapsed filter section
  const [filtersExpanded, setFiltersExpanded] = useState(true);
  const [filterCategory, setFilterCategory] = useState<FilterCategory>('descriptive');

  // Load filter metadata once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await screenerService.getFilters();
        if (!cancelled) setFilterMeta(data);
      } catch (e: any) {
        if (!cancelled) setMetaError(e.message || 'Failed to load filters');
      } finally {
        if (!cancelled) setMetaLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const doSearch = useCallback(async (viewOverride?: View) => {
    setLoading(true);
    setError('');
    try {
      const data = await screenerService.search({
        filters: activeFilters,
        signal,
        ticker,
        order,
        ascend,
        limit,
        view: viewOverride ?? view,
      });
      setResults(data);
    } catch (e: any) {
      setError(e.message || 'Search failed');
    } finally {
      setLoading(false);
    }
  }, [activeFilters, signal, ticker, order, ascend, limit, view]);

  // Auto-search on mount once metadata is loaded
  useEffect(() => {
    if (!metaLoading && filterMeta) {
      doSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [metaLoading]);

  // Re-search when view tab changes
  const handleViewChange = useCallback((v: string) => {
    setView(v as View);
    // Trigger search with new view immediately
    setLoading(true);
    setError('');
    (async () => {
      try {
        const data = await screenerService.search({
          filters: activeFilters,
          signal,
          ticker,
          order,
          ascend,
          limit,
          view: v,
        });
        setResults(data);
      } catch (e: any) {
        setError(e.message || 'Search failed');
      } finally {
        setLoading(false);
      }
    })();
  }, [activeFilters, signal, ticker, order, ascend, limit]);

  const handleFilterChange = useCallback((name: string, value: string) => {
    setActiveFilters(prev => {
      const next = { ...prev };
      if (!value || value === '') {
        delete next[name];
      } else {
        next[name] = value;
      }
      return next;
    });
  }, []);

  const handleReset = useCallback(() => {
    setActiveFilters({});
    setSignal('');
    setTicker('');
    setOrder('Ticker');
    setAscend(true);
    setSelectedPreset('');
  }, []);

  // Preset selection
  const [selectedPreset, setSelectedPreset] = useState('');

  const handlePresetChange = useCallback((key: string) => {
    setSelectedPreset(key);
    if (!key) return;
    const preset = PRESETS[key];
    if (!preset) return;
    setActiveFilters(preset.filters);
    setSignal(preset.signal);
    setView(preset.view);
    // Auto-search with preset
    setLoading(true);
    setError('');
    (async () => {
      try {
        const data = await screenerService.search({
          filters: preset.filters,
          signal: preset.signal,
          ticker,
          order,
          ascend,
          limit,
          view: preset.view,
        });
        setResults(data);
      } catch (e: any) {
        setError(e.message || 'Search failed');
      } finally {
        setLoading(false);
      }
    })();
  }, [ticker, order, ascend, limit]);

  // Filter names filtered by selected category (preserving category order, not alphabetical)
  const filterNames = useMemo(() => {
    if (!filterMeta) return [];
    const available = new Set(Object.keys(filterMeta.filters));
    const ordered = FILTER_CATEGORIES[filterCategory].filters;
    return ordered.filter(n => available.has(n));
  }, [filterMeta, filterCategory]);

  const activeFilterCount = Object.keys(activeFilters).length + (signal ? 1 : 0) + (ticker ? 1 : 0);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold tracking-wide uppercase">Screener</h1>
          {results && (
            <span className="text-sm text-muted-foreground">
              {results.total} result{results.total !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleReset} disabled={activeFilterCount === 0}>
            Reset
          </Button>
          <Button size="sm" onClick={() => doSearch()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Search className="h-4 w-4 mr-1" />}
            Search
          </Button>
        </div>
      </div>

      {/* Controls */}
      <div className="px-4 py-2 border-b border-border space-y-2 shrink-0">
        {/* Signal + Ticker + Order row */}
        <div className="flex flex-wrap items-end gap-3">
          {/* Preset strategies */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Strategy Preset</label>
            <select
              className="h-8 rounded-md border border-input bg-background px-2 text-sm font-medium"
              value={selectedPreset}
              onChange={e => handlePresetChange(e.target.value)}
            >
              <option value="">Custom (no preset)</option>
              {Object.entries(PRESETS).map(([key, preset]) => (
                <option key={key} value={key}>{preset.label}</option>
              ))}
            </select>
          </div>

          <div className="w-px h-8 bg-border self-end" />

          {/* Signal */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Signal</label>
            <select
              className="h-8 rounded-md border border-input bg-background px-2 text-sm"
              value={signal}
              onChange={e => setSignal(e.target.value)}
            >
              <option value="">None (all stocks)</option>
              {filterMeta?.signals.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {/* Ticker */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Ticker</label>
            <Input
              className="h-8 w-48"
              placeholder="e.g. AAPL,MSFT"
              value={ticker}
              onChange={e => setTicker(e.target.value)}
            />
          </div>

          {/* Order */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Order by</label>
            <select
              className="h-8 rounded-md border border-input bg-background px-2 text-sm"
              value={order}
              onChange={e => setOrder(e.target.value)}
            >
              {filterMeta?.orders.map(o => (
                <option key={o} value={o}>{o}</option>
              ))}
              {(!filterMeta || filterMeta.orders.length === 0) && <option value="Ticker">Ticker</option>}
            </select>
          </div>

          {/* Asc/Desc */}
          <Button variant="outline" size="sm" className="h-8" onClick={() => setAscend(a => !a)}>
            <ArrowUpDown className="h-3.5 w-3.5 mr-1" />
            {ascend ? 'Asc' : 'Desc'}
          </Button>

          {/* Filter toggle */}
          <Button variant="ghost" size="sm" className="h-8 ml-auto" onClick={() => setFiltersExpanded(e => !e)}>
            {filtersExpanded ? <ChevronUp className="h-3.5 w-3.5 mr-1" /> : <ChevronDown className="h-3.5 w-3.5 mr-1" />}
            Filters {activeFilterCount > 0 && `(${activeFilterCount})`}
          </Button>
        </div>

        {/* Preset description */}
        {selectedPreset && PRESETS[selectedPreset] && (
          <p className="text-xs text-muted-foreground italic">
            {PRESETS[selectedPreset].description}
          </p>
        )}

        {/* Filter grid */}
        {filtersExpanded && (
          <div>
            {/* Filter category tabs */}
            <div className="flex gap-1 mb-2">
              {(['descriptive', 'fundamental', 'technical', 'all'] as FilterCategory[]).map(cat => (
                <button
                  key={cat}
                  className={`px-3 py-1 text-xs rounded-md transition-colors ${
                    filterCategory === cat
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
                  }`}
                  onClick={() => setFilterCategory(cat)}
                >
                  {FILTER_CATEGORIES[cat].label}
                </button>
              ))}
            </div>

            <div className="max-h-64 overflow-y-auto">
            {metaLoading ? (
              <div className="grid grid-cols-4 gap-2">
                {Array.from({ length: 16 }).map((_, i) => (
                  <Skeleton key={i} className="h-8" />
                ))}
              </div>
            ) : metaError ? (
              <p className="text-sm text-destructive">{metaError}</p>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1.5">
                {filterNames.map(name => (
                  <div key={name} className="flex items-center gap-1.5">
                    <label className="text-[11px] text-muted-foreground whitespace-nowrap shrink-0 min-w-[100px] text-right" title={name}>{name}</label>
                    <select
                      className="h-7 flex-1 min-w-0 rounded border border-input bg-background px-1.5 text-xs"
                      value={activeFilters[name] || ''}
                      onChange={e => handleFilterChange(name, e.target.value)}
                    >
                      <option value="">Any</option>
                      {filterMeta!.filters[name]?.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            )}
          </div>
          </div>
        )}
      </div>

      {/* View tabs */}
      <div className="px-4 pt-2 shrink-0">
        <Tabs value={view} onValueChange={handleViewChange}>
          <TabsList>
            {VIEWS.map(v => (
              <TabsTrigger key={v} value={v} className="capitalize text-xs">
                {v}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-auto px-4 pb-4">
        {error && <p className="text-sm text-destructive mt-2">{error}</p>}

        {loading ? (
          <div className="mt-4 space-y-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : results && results.columns.length > 0 ? (
          <div className="mt-2 border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  {results.columns.map(col => (
                    <TableHead key={col} className="text-xs whitespace-nowrap">{col}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.rows.map((row, i) => (
                  <TableRow key={i}>
                    {results.columns.map(col => (
                      <TableCell key={col} className={`text-xs whitespace-nowrap ${cellColor(col, row[col])}`}>
                        {col === 'Ticker' && row[col] ? (
                          <TickerLink ticker={String(row[col])} />
                        ) : (
                          formatCellValue(col, row[col])
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : !loading && results && results.total === 0 ? (
          <p className="text-sm text-muted-foreground mt-4">No stocks found matching the selected criteria.</p>
        ) : null}
      </div>
    </div>
  );
}
