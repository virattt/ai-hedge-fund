import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, Check, Loader2, Search, TrendingDown, TrendingUp, Minus } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { SubNavLink } from '@/components/insider/insider-sub-nav';
import { useSettings } from '@/contexts/settings-context';
import {
  insiderService,
  type EarningsAnalysisResponse,
  type ConvictionResponse,
  type ConvictionSignal,
} from '@/services/insider-api';
import { formatValue } from '@/utils/format';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type EarningsTab = 'sentiment' | 'conviction';
type ConvictionSortKey = keyof ConvictionSignal;
type SortDir = 'asc' | 'desc';

// ---------------------------------------------------------------------------
// Sortable header (reused pattern from finnhub page)
// ---------------------------------------------------------------------------

interface SortableHeadProps<K> {
  label: string;
  sortKey: K;
  activeKey: K | null;
  dir: SortDir;
  onSort: (key: K) => void;
  className?: string;
}

function SortableHead<K>({ label, sortKey, activeKey, dir, onSort, className = '' }: SortableHeadProps<K>) {
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
// Helpers
// ---------------------------------------------------------------------------

function sentimentColor(sentiment: string): string {
  if (sentiment === 'bullish') return 'text-primary';
  if (sentiment === 'bearish') return 'text-destructive';
  return 'text-muted-foreground';
}

function sentimentBadge(sentiment: string) {
  const variant = sentiment === 'bullish' ? 'success' : sentiment === 'bearish' ? 'destructive' : 'secondary';
  return <Badge variant={variant}>{sentiment}</Badge>;
}

function deltaIcon(direction: string) {
  if (direction === 'improving') return <TrendingUp className="h-4 w-4 text-primary" />;
  if (direction === 'deteriorating') return <TrendingDown className="h-4 w-4 text-destructive" />;
  return <Minus className="h-4 w-4 text-muted-foreground" />;
}

function convictionColor(score: number): string {
  if (score >= 70) return 'text-primary';
  if (score >= 40) return 'text-foreground';
  return 'text-destructive';
}

function convictionBg(score: number): string {
  if (score >= 70) return 'bg-primary/10';
  if (score >= 40) return 'bg-muted';
  return 'bg-destructive/10';
}

function compareConviction(a: ConvictionSignal, b: ConvictionSignal, key: ConvictionSortKey, dir: SortDir): number {
  const av = a[key];
  const bv = b[key];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
  return dir === 'asc' ? cmp : -cmp;
}

// ---------------------------------------------------------------------------
// Tab 1: Transcript Sentiment
// ---------------------------------------------------------------------------

function TranscriptSentimentTab() {
  const { selectedModel } = useSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const [ticker, setTicker] = useState('');
  const [data, setData] = useState<EarningsAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoRunDoneRef = useRef<string | null>(null);

  const handleAnalyze = async (override?: string) => {
    const sym = (override ?? ticker).trim().toUpperCase();
    if (!sym || !selectedModel) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await insiderService.getEarningsAnalysis(sym, selectedModel.model_name, selectedModel.provider);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch earnings analysis');
    } finally {
      setLoading(false);
    }
  };

  // Deep-link support: read ?ticker=XYZ&autoRun=1 from URL, prefill, and auto-run once
  useEffect(() => {
    const urlTicker = searchParams.get('ticker');
    const autoRun = searchParams.get('autoRun');
    if (!urlTicker) return;
    const sym = urlTicker.toUpperCase();
    if (sym !== ticker) setTicker(sym);
    if (autoRun === '1' && selectedModel && autoRunDoneRef.current !== sym) {
      autoRunDoneRef.current = sym;
      handleAnalyze(sym);
      // Strip autoRun param so a refresh doesn't re-fire (keep ticker for shareability)
      setSearchParams({ ticker: sym }, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, selectedModel]);

  const current = data?.transcripts?.[0];
  const previous = data?.transcripts?.[1];
  const delta = data?.delta;

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="flex gap-2 max-w-md">
        <Input
          placeholder="Enter ticker (e.g. AAPL)"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
        />
        <Button onClick={() => handleAnalyze()} disabled={loading || !ticker.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Analyze
        </Button>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {loading && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
          <p className="text-sm">Analyzing earnings transcripts with LLM...</p>
          <p className="text-xs">This may take 10-30 seconds</p>
        </div>
      )}

      {data && !loading && (
        <>
          {data.cached && <Badge variant="secondary" className="text-xs">Cached</Badge>}

          {current && (
            <div className="space-y-4">
              {/* Current Quarter */}
              <h3 className="text-sm font-medium text-muted-foreground">
                Current: {current.quarter} {current.year} ({current.source.toUpperCase()})
              </h3>
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                <Card>
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-xs font-medium text-muted-foreground">Sentiment</CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4">
                    <div className="text-2xl font-bold">
                      {sentimentBadge(current.analysis.overall_sentiment)}
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-xs font-medium text-muted-foreground">Confidence</CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4">
                    <div className="text-2xl font-bold">{current.analysis.confidence}%</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-xs font-medium text-muted-foreground">Management Tone</CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4">
                    <div className="text-lg font-medium">{current.analysis.management_tone}</div>
                  </CardContent>
                </Card>
              </div>

              {/* Key Themes */}
              {current.analysis.key_themes.length > 0 && (
                <Card>
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-xs font-medium text-muted-foreground">Key Themes</CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4 flex flex-wrap gap-2">
                    {current.analysis.key_themes.map((theme, i) => (
                      <Badge key={i} variant="outline">{theme}</Badge>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* Forward Guidance */}
              {current.analysis.forward_guidance && (
                <Card>
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-xs font-medium text-muted-foreground">Forward Guidance</CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4">
                    <p className="text-sm">{current.analysis.forward_guidance}</p>
                  </CardContent>
                </Card>
              )}

              {/* Notable Quotes */}
              {current.analysis.notable_quotes.length > 0 && (
                <Card>
                  <CardHeader className="pb-2 pt-4 px-4">
                    <CardTitle className="text-xs font-medium text-muted-foreground">Notable Quotes</CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4 space-y-2">
                    {current.analysis.notable_quotes.map((quote, i) => (
                      <blockquote key={i} className="border-l-2 pl-3 text-sm italic text-muted-foreground">
                        &ldquo;{quote}&rdquo;
                      </blockquote>
                    ))}
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {/* Sentiment Delta */}
          {delta && (
            <Card className={`border-l-4 ${delta.delta_direction === 'improving' ? 'border-l-primary' : delta.delta_direction === 'deteriorating' ? 'border-l-destructive' : 'border-l-muted-foreground'}`}>
              <CardHeader className="pb-2 pt-4 px-4">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  {deltaIcon(delta.delta_direction)}
                  Sentiment Delta: {delta.delta_direction}
                  <span className="text-xs text-muted-foreground font-normal ml-2">
                    Magnitude: {delta.delta_magnitude.toFixed(1)}%
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                <ul className="space-y-1">
                  {delta.key_changes.map((change, i) => (
                    <li key={i} className="text-sm text-muted-foreground">• {change}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Previous Quarter (compact) */}
          {previous && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-muted-foreground">
                Previous: {previous.quarter} {previous.year}
              </h3>
              <div className="grid grid-cols-3 gap-3">
                <Card className="opacity-75">
                  <CardContent className="px-4 py-3">
                    <p className="text-xs text-muted-foreground">Sentiment</p>
                    <p className={`text-sm font-medium ${sentimentColor(previous.analysis.overall_sentiment)}`}>
                      {previous.analysis.overall_sentiment} ({previous.analysis.confidence}%)
                    </p>
                  </CardContent>
                </Card>
                <Card className="opacity-75">
                  <CardContent className="px-4 py-3">
                    <p className="text-xs text-muted-foreground">Tone</p>
                    <p className="text-sm font-medium">{previous.analysis.management_tone}</p>
                  </CardContent>
                </Card>
                <Card className="opacity-75">
                  <CardContent className="px-4 py-3">
                    <p className="text-xs text-muted-foreground">Themes</p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {previous.analysis.key_themes.slice(0, 3).map((t, i) => (
                        <Badge key={i} variant="outline" className="text-xs">{t}</Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {data.transcripts.length === 0 && (
            <div className="text-center py-12 text-muted-foreground text-sm">
              No earnings transcripts found for {data.ticker}.
            </div>
          )}
        </>
      )}

      {!data && !loading && !error && (
        <div className="text-center py-20 text-muted-foreground text-sm">
          Enter a ticker to analyze earnings call transcripts with AI-powered sentiment analysis.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 2: Conviction Scanner
// ---------------------------------------------------------------------------

function ConvictionScannerTab() {
  const { selectedModel } = useSettings();
  const [tickerInput, setTickerInput] = useState('');
  const [data, setData] = useState<ConvictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<ConvictionSortKey | null>('conviction_score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleScan = async () => {
    const tickers = tickerInput
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    if (tickers.length === 0 || !selectedModel) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await insiderService.getConvictionSignals(tickers, selectedModel.model_name, selectedModel.provider);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch conviction signals');
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (key: ConvictionSortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sortedSignals = useMemo(() => {
    if (!data) return [];
    if (!sortKey) return data.signals;
    return [...data.signals].sort((a, b) => compareConviction(a, b, sortKey, sortDir));
  }, [data, sortKey, sortDir]);

  return (
    <div className="space-y-4">
      {/* Input */}
      <div className="flex gap-2 max-w-lg">
        <Input
          placeholder="Enter tickers (e.g. AAPL, MSFT, NVDA)"
          value={tickerInput}
          onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleScan()}
        />
        <Button onClick={handleScan} disabled={loading || !tickerInput.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Scan
        </Button>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      {loading && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
          <p className="text-sm">Analyzing earnings + insider activity...</p>
          <p className="text-xs">This may take 30-60 seconds for multiple tickers</p>
        </div>
      )}

      {data && !loading && (
        <>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>{data.total} signals</span>
            {data.cached && <Badge variant="secondary" className="text-xs">Cached</Badge>}
          </div>

          {sortedSignals.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              No conviction signals generated.
            </div>
          ) : (
            <div className="rounded-md border overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <SortableHead label="Ticker" sortKey="ticker" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortableHead label="Conviction" sortKey="conviction_score" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortableHead label="Sentiment" sortKey="sentiment_delta" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortableHead label="Tone" sortKey="management_tone" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortableHead label="Insider" sortKey="insider_activity" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                    <TableHead>CEO/CFO</TableHead>
                    <SortableHead label="Buys" sortKey="insider_buy_count" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortableHead label="Buy Value" sortKey="insider_buy_value" activeKey={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <TableHead>Themes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedSignals.map((s) => (
                    <TableRow key={s.ticker} className={convictionBg(s.conviction_score)}>
                      <TableCell className="font-medium text-sm">{s.ticker}</TableCell>
                      <TableCell className={`text-right text-sm font-bold tabular-nums ${convictionColor(s.conviction_score)}`}>
                        {s.conviction_score.toFixed(0)}
                      </TableCell>
                      <TableCell className="text-sm">
                        <span className="inline-flex items-center gap-1">
                          {deltaIcon(s.sentiment_delta)}
                          {s.sentiment_delta}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">{s.management_tone}</TableCell>
                      <TableCell className="text-sm">
                        {s.insider_activity === 'net_buying' ? (
                          <Badge variant="success" className="bg-primary text-primary-foreground text-xs">Buying</Badge>
                        ) : s.insider_activity === 'net_selling' ? (
                          <Badge variant="destructive" className="text-xs">Selling</Badge>
                        ) : (
                          <Badge variant="secondary" className="text-xs">Neutral</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        {s.ceo_cfo_buying ? (
                          <Check className="h-4 w-4 text-primary mx-auto" />
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {s.insider_buy_count > 0 ? (
                          <span className="text-primary font-medium">{s.insider_buy_count}</span>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {s.insider_buy_value > 0 ? (
                          <span className="text-primary">{formatValue(s.insider_buy_value)}</span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="max-w-[200px]">
                        <div className="flex flex-wrap gap-1">
                          {s.key_themes.slice(0, 3).map((t, i) => (
                            <Badge key={i} variant="outline" className="text-xs">{t}</Badge>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Reasoning details */}
          {sortedSignals.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-muted-foreground">Reasoning</h4>
              {sortedSignals.map((s) => (
                <div key={s.ticker} className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{s.ticker}:</span> {s.reasoning}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!data && !loading && !error && (
        <div className="text-center py-20 text-muted-foreground text-sm">
          Enter ticker symbols to scan for high-conviction signals combining earnings sentiment with insider trading activity.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main InsiderEarningsPage
// ---------------------------------------------------------------------------

export function InsiderEarningsPage() {
  const [activeTab, setActiveTab] = useState<EarningsTab>('sentiment');

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-wide uppercase">Earnings Sentiment</h1>
          <p className="text-sm text-muted-foreground">
            AI-powered earnings call analysis with sentiment delta and conviction scoring
          </p>
        </div>
        <div className="flex items-center gap-1">
          <SubNavLink to="/insider" label="Edgar Insider" />
          <SubNavLink to="/insider/openinsider" label="OpenInsider" />
          <SubNavLink to="/insider/finnhub" label="Short Interest" />
          <SubNavLink to="/insider/political" label="Political" />
          <SubNavLink to="/insider/earnings" label="Earnings" />
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as EarningsTab)}>
        <TabsList>
          <TabsTrigger value="sentiment">Transcript Sentiment</TabsTrigger>
          <TabsTrigger value="conviction">Conviction Scanner</TabsTrigger>
        </TabsList>
      </Tabs>

      {activeTab === 'sentiment' && <TranscriptSentimentTab />}
      {activeTab === 'conviction' && <ConvictionScannerTab />}
    </div>
  );
}
