import { useEffect, useState, useCallback, useRef } from 'react';
import { BookOpen, ExternalLink, Lightbulb, Newspaper, RefreshCw, TrendingUp, Search, XCircle, BarChart3, Rss, DollarSign, PieChart } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { ModelSelector } from '@/components/ui/llm-selector';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { type LanguageModel, getModels, getDefaultModel } from '@/data/models';
import {
  type AnalyzedArticle,
  type MarketPulseData,
  type RankedNewsItem,
  type RealtimeNewsItem,
  newsService,
} from '@/services/news-api';

/* -------------------------------------------------------------------------- */
/*  Shared components                                                         */
/* -------------------------------------------------------------------------- */

function SentimentBadge({ sentiment }: { sentiment: string }) {
  const config: Record<string, { label: string; className: string }> = {
    bullish: { label: 'Bullish', className: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30' },
    bearish: { label: 'Bearish', className: 'bg-red-500/10 text-red-600 border-red-500/30' },
    neutral: { label: 'Neutral', className: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/30' },
  };
  const { label, className } = config[sentiment] ?? config.neutral;
  return <Badge variant="outline" className={className}>{label}</Badge>;
}

function ProviderBadge({ provider }: { provider: string }) {
  const config: Record<string, { label: string; className: string }> = {
    finviz: { label: 'FinViz', className: 'bg-blue-500/10 text-blue-600 border-blue-500/30' },
    yfinance: { label: 'Yahoo', className: 'bg-purple-500/10 text-purple-600 border-purple-500/30' },
  };
  const { label, className } = config[provider] ?? { label: provider, className: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/30' };
  return <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${className}`}>{label}</Badge>;
}

/* -------------------------------------------------------------------------- */
/*  Real-time news tab components                                             */
/* -------------------------------------------------------------------------- */

function RankedNewsCard({ item, rank, reason }: { item: RealtimeNewsItem; rank: number; reason: string }) {
  return (
    <a href={item.link} target="_blank" rel="noopener noreferrer" className="block group py-3">
      <div className="flex gap-3">
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
          {rank}
        </div>
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ProviderBadge provider={item.provider} />
            <span className="font-medium uppercase tracking-wide">{item.source}</span>
            <span>&middot;</span>
            <span>{item.date}</span>
          </div>
          <h3 className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors leading-snug">
            {item.title}
          </h3>
          <p className="text-xs text-muted-foreground line-clamp-1">{reason}</p>
        </div>
      </div>
    </a>
  );
}

function RealtimeNewsCard({ item }: { item: RealtimeNewsItem }) {
  return (
    <a href={item.link} target="_blank" rel="noopener noreferrer" className="block group py-3">
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <ProviderBadge provider={item.provider} />
          <span className="font-medium uppercase tracking-wide">{item.source}</span>
          <span>&middot;</span>
          <span>{item.date}</span>
        </div>
        <h3 className="text-sm font-medium text-foreground group-hover:text-primary transition-colors leading-snug">
          {item.title}
        </h3>
      </div>
    </a>
  );
}

function SmallSkeleton() {
  return (
    <div className="py-3 space-y-2">
      <div className="flex gap-2">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-20" />
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-3 w-3/5" />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Insights tab components                                                   */
/* -------------------------------------------------------------------------- */

function AnalyzedArticleCard({ article }: { article: AnalyzedArticle }) {
  const date = new Date(article.analyzed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  return (
    <Card className="border-0 shadow-none bg-transparent">
      <CardContent className="px-0 py-6 space-y-3">
        <p className="text-xs text-muted-foreground font-medium tracking-wide uppercase">
          {article.source_name}
        </p>
        <a href={article.url} target="_blank" rel="noopener noreferrer" className="block group">
          <h2 className="text-xl font-bold text-foreground group-hover:text-primary transition-colors leading-tight">
            {article.title}
          </h2>
        </a>
        <p className="text-muted-foreground leading-relaxed line-clamp-3">{article.summary}</p>
        <div className="flex items-start gap-2 rounded-md bg-amber-500/5 border border-amber-500/10 px-3 py-2">
          <Lightbulb size={14} className="text-amber-500 mt-0.5 shrink-0" />
          <p className="text-sm text-amber-700 dark:text-amber-400">{article.market_insight}</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap text-sm">
          <SentimentBadge sentiment={article.sentiment} />
          {article.tickers_mentioned.map((ticker) => (
            <Badge key={ticker} variant="secondary" className="text-xs font-mono">{ticker}</Badge>
          ))}
          <span className="text-muted-foreground ml-auto text-xs">{date}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function SkeletonCard() {
  return (
    <div className="py-6 space-y-3">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-6 w-3/4" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-10 w-full rounded-md" />
      <div className="flex gap-2">
        <Skeleton className="h-5 w-16 rounded-full" />
        <Skeleton className="h-5 w-12 rounded-full" />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Market Index Card                                                         */
/* -------------------------------------------------------------------------- */

function MarketIndexCard({ index }: { index: { symbol: string; name: string; price: number; change: number; change_percent: number } }) {
  const isPositive = index.change >= 0;
  return (
    <Card className="border shadow-sm">
      <CardContent className="p-4 space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{index.symbol}</span>
          <span className="text-xs text-muted-foreground">{index.name}</span>
        </div>
        <div className="text-xl font-bold text-foreground">${index.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        <div className={`text-sm font-semibold ${isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
          {isPositive ? '+' : ''}{index.change.toFixed(2)} ({isPositive ? '+' : ''}{index.change_percent.toFixed(2)}%)
        </div>
      </CardContent>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/*  News list component (reused across tabs)                                  */
/* -------------------------------------------------------------------------- */

function NewsListTab({ items, loading, icon, emptyMessage }: { items: RealtimeNewsItem[]; loading: boolean; icon: React.ReactNode; emptyMessage: string }) {
  if (loading) {
    return (
      <div className="divide-y divide-border">
        {Array.from({ length: 8 }).map((_, i) => <SmallSkeleton key={i} />)}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="text-center py-20 text-muted-foreground space-y-3">
        {icon}
        <p className="text-lg font-medium">No news available</p>
        <p className="text-sm">{emptyMessage}</p>
      </div>
    );
  }
  return (
    <div className="divide-y divide-border">
      {items.map((item, idx) => (
        <RealtimeNewsCard key={`${item.link}-${idx}`} item={item} />
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Main page                                                                 */
/* -------------------------------------------------------------------------- */

export function NewsPage() {
  const [models, setModels] = useState<LanguageModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<LanguageModel | null>(null);

  // Real-time news state
  const [realtimeNews, setRealtimeNews] = useState<RealtimeNewsItem[]>([]);
  const [realtimeLoading, setRealtimeLoading] = useState(false);
  const [realtimeLoaded, setRealtimeLoaded] = useState(false);

  // Ranked top-10 state
  const [rankedItems, setRankedItems] = useState<RankedNewsItem[]>([]);
  const [rankingLoading, setRankingLoading] = useState(false);
  const rankAbortRef = useRef<AbortController | null>(null);

  // Insights tab state
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const [analyzedArticles, setAnalyzedArticles] = useState<AnalyzedArticle[]>([]);
  const [analyzingLoading, setAnalyzingLoading] = useState(false);

  // New category tabs state
  const [blogNews, setBlogNews] = useState<RealtimeNewsItem[]>([]);
  const [blogLoading, setBlogLoading] = useState(false);
  const [stocksNews, setStocksNews] = useState<RealtimeNewsItem[]>([]);
  const [stocksLoading, setStocksLoading] = useState(false);
  const [etfNews, setEtfNews] = useState<RealtimeNewsItem[]>([]);
  const [etfLoading, setEtfLoading] = useState(false);
  const [marketPulse, setMarketPulse] = useState<MarketPulseData | null>(null);
  const [marketPulseLoading, setMarketPulseLoading] = useState(false);
  const [loadedTabs, setLoadedTabs] = useState<Set<string>>(new Set());

  // Load models on mount
  useEffect(() => {
    (async () => {
      try {
        const [fetched, defaultModel] = await Promise.all([getModels(), getDefaultModel()]);
        setModels(fetched);
        setSelectedModel(defaultModel);
      } catch {
        toast.error('Failed to load models');
      }
    })();
  }, []);

  // Auto-load realtime news on mount
  useEffect(() => {
    loadRealtimeNews();
  }, []);

  const loadRealtimeNews = async () => {
    setRealtimeLoading(true);
    try {
      const items = await newsService.getRealtimeNews();
      setRealtimeNews(items);
      setRealtimeLoaded(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to fetch real-time news');
    } finally {
      setRealtimeLoading(false);
    }
  };

  // Auto-rank when news + model are available
  useEffect(() => {
    if (realtimeNews.length > 0 && selectedModel && !rankingLoading && rankedItems.length === 0) {
      rankNews();
    }
  }, [realtimeNews, selectedModel]);

  const cancelRanking = useCallback(() => {
    if (rankAbortRef.current) {
      rankAbortRef.current.abort();
      rankAbortRef.current = null;
    }
    setRankingLoading(false);
  }, []);

  const rankNews = useCallback(async () => {
    if (!selectedModel || realtimeNews.length === 0) return;
    // Cancel any in-flight ranking
    if (rankAbortRef.current) rankAbortRef.current.abort();
    const controller = new AbortController();
    rankAbortRef.current = controller;

    setRankingLoading(true);
    setRankedItems([]);
    try {
      const items = await newsService.rankRelevance(
        {
          titles: realtimeNews.map((n) => n.title),
          model_name: selectedModel.model_name,
          model_provider: selectedModel.provider,
        },
        controller.signal,
      );
      console.log('[rankNews] received items:', JSON.stringify(items?.slice(0, 2)));
      console.log('[rankNews] items count:', items?.length, 'first index:', items?.[0]?.index, 'realtimeNews length:', realtimeNews.length);
      setRankedItems(items);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // User cancelled — do nothing
        return;
      }
      toast.error(err instanceof Error ? err.message : 'Failed to rank news');
    } finally {
      setRankingLoading(false);
      rankAbortRef.current = null;
    }
  }, [selectedModel, realtimeNews]);

  // Insights: toggle article selection
  const toggleUrl = (url: string) => {
    setSelectedUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  };

  const selectAll = () => setSelectedUrls(new Set(realtimeNews.map((n) => n.link)));
  const clearSelection = () => setSelectedUrls(new Set());

  const handleAnalyze = async () => {
    if (!selectedModel || selectedUrls.size === 0) return;
    setAnalyzingLoading(true);
    try {
      const articles = realtimeNews
        .filter((n) => selectedUrls.has(n.link))
        .map((n) => ({ url: n.link, title: n.title, source: n.source }));
      const results = await newsService.analyzeArticles({
        articles,
        model_name: selectedModel.model_name,
        model_provider: selectedModel.provider,
      });
      setAnalyzedArticles(results);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to analyze articles');
    } finally {
      setAnalyzingLoading(false);
    }
  };

  // Lazy-load tab data on first visit
  const handleTabChange = async (tab: string) => {
    if (loadedTabs.has(tab)) return;
    setLoadedTabs((prev) => new Set(prev).add(tab));

    if (tab === 'blogs') {
      setBlogLoading(true);
      try {
        const items = await newsService.getBlogNews();
        setBlogNews(items);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to fetch blog news');
      } finally {
        setBlogLoading(false);
      }
    } else if (tab === 'market-pulse') {
      setMarketPulseLoading(true);
      try {
        const data = await newsService.getMarketPulse();
        setMarketPulse(data);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to fetch market pulse');
      } finally {
        setMarketPulseLoading(false);
      }
    } else if (tab === 'stocks') {
      setStocksLoading(true);
      try {
        const items = await newsService.getStocksNews();
        setStocksNews(items);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to fetch stocks news');
      } finally {
        setStocksLoading(false);
      }
    } else if (tab === 'etf') {
      setEtfLoading(true);
      try {
        const items = await newsService.getEtfNews();
        setEtfNews(items);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to fetch ETF news');
      } finally {
        setEtfLoading(false);
      }
    }
  };

  // Build ranked top-10 list
  const rankedNews = rankedItems
    .sort((a, b) => b.relevance_score - a.relevance_score)
    .map((ri) => ({ ...ri, item: realtimeNews[ri.index] }))
    .filter((r) => r.item);
  if (rankedItems.length > 0) {
    console.log('[rankedNews] rankedItems:', rankedItems.length, 'mapped:', rankedNews.length, 'indices:', rankedItems.map(r => r.index));
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="w-full px-6 py-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <BookOpen size={22} className="text-primary" />
          <h1 className="text-2xl font-bold text-foreground">News</h1>
        </div>

        {/* Shared model selector */}
        <div className="mb-6">
          <ModelSelector
            models={models}
            value={selectedModel?.model_name ?? ''}
            onChange={(m) => setSelectedModel(m)}
            placeholder="Select an LLM model..."
          />
        </div>

        {/* Tabs */}
        <Tabs defaultValue="realtime" className="w-full" onValueChange={handleTabChange}>
          <TabsList className="mb-6">
            <TabsTrigger value="realtime" className="gap-1.5">
              <Newspaper size={14} />
              Real-time News
            </TabsTrigger>
            <TabsTrigger value="blogs" className="gap-1.5">
              <Rss size={14} />
              Blogs
            </TabsTrigger>
            <TabsTrigger value="market-pulse" className="gap-1.5">
              <BarChart3 size={14} />
              Market Pulse
            </TabsTrigger>
            <TabsTrigger value="stocks" className="gap-1.5">
              <DollarSign size={14} />
              Stocks News
            </TabsTrigger>
            <TabsTrigger value="etf" className="gap-1.5">
              <PieChart size={14} />
              ETF News
            </TabsTrigger>
            <TabsTrigger value="insights" className="gap-1.5">
              <Lightbulb size={14} />
              News Insights
            </TabsTrigger>
          </TabsList>

          {/* ---- Real-time News Tab ---- */}
          <TabsContent value="realtime">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-muted-foreground">
                Latest financial news{realtimeNews.length > 0 ? ` (${realtimeNews.length} articles)` : ''}
              </p>
              <div className="flex gap-2">
                {rankingLoading ? (
                  <Button variant="destructive" size="sm" onClick={cancelRanking}>
                    <XCircle size={14} className="mr-1.5" />
                    Cancel Ranking
                  </Button>
                ) : (
                  <Button variant="outline" size="sm" onClick={rankNews} disabled={!selectedModel || realtimeNews.length === 0}>
                    <TrendingUp size={14} className="mr-1.5" />
                    Rank Top 10
                  </Button>
                )}
                <Button variant="outline" size="sm" onClick={loadRealtimeNews} disabled={realtimeLoading}>
                  <RefreshCw size={14} className={realtimeLoading ? 'animate-spin mr-1.5' : 'mr-1.5'} />
                  Refresh
                </Button>
              </div>
            </div>

            <div className="flex gap-6">
              {/* Left column: Top 10 */}
              <div className="w-[520px] flex-shrink-0">
                <div className="sticky top-4">
                  <div className="rounded-xl border-2 border-primary/20 bg-primary/[0.04] p-4 shadow-sm">
                    <div className="flex items-center gap-2 mb-3 pb-2 border-b border-primary/10">
                      <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-primary/10">
                        <TrendingUp size={16} className="text-primary" />
                      </div>
                      <div>
                        <h2 className="text-sm font-bold text-foreground">Top 10 Market-Moving</h2>
                        <p className="text-[11px] text-muted-foreground">AI-ranked by impact</p>
                      </div>
                    </div>
                    {rankingLoading && rankedNews.length === 0 ? (
                      <div className="divide-y divide-border">
                        {Array.from({ length: 5 }).map((_, i) => <SmallSkeleton key={i} />)}
                      </div>
                    ) : rankedNews.length > 0 ? (
                      <div className="divide-y divide-border">
                        {rankedNews.map((r, idx) => (
                          <RankedNewsCard key={r.item.link} item={r.item} rank={idx + 1} reason={r.reason} />
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground text-center py-6">
                        Click &quot;Rank Top 10&quot; to analyze headlines
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Right column: All News */}
              <div className="flex-1 min-w-0">
                {realtimeLoading && !realtimeLoaded && (
                  <div className="divide-y divide-border">
                    {Array.from({ length: 8 }).map((_, i) => <SmallSkeleton key={i} />)}
                  </div>
                )}

                {realtimeLoaded && realtimeNews.length > 0 && (
                  <>
                    <h2 className="text-sm font-semibold text-muted-foreground mb-2">All News</h2>
                    <div className="divide-y divide-border">
                      {realtimeNews.map((item, idx) => (
                        <RealtimeNewsCard key={`${item.link}-${idx}`} item={item} />
                      ))}
                    </div>
                  </>
                )}

                {realtimeLoaded && realtimeNews.length === 0 && !realtimeLoading && (
                  <div className="text-center py-20 text-muted-foreground space-y-3">
                    <Newspaper size={40} className="mx-auto opacity-30" />
                    <p className="text-lg font-medium">No news available</p>
                    <p className="text-sm">Could not fetch real-time news. Check your internet connection and try again.</p>
                  </div>
                )}
              </div>
            </div>
          </TabsContent>

          {/* ---- Blogs Tab ---- */}
          <TabsContent value="blogs">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-muted-foreground">
                Blog posts from financial sources{blogNews.length > 0 ? ` (${blogNews.length} posts)` : ''}
              </p>
            </div>
            <NewsListTab items={blogNews} loading={blogLoading} icon={<Rss size={40} className="mx-auto opacity-30" />} emptyMessage="No blog posts available. Try refreshing." />
          </TabsContent>

          {/* ---- Market Pulse Tab ---- */}
          <TabsContent value="market-pulse">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-muted-foreground">Major market indices and related news</p>
            </div>
            {marketPulseLoading ? (
              <div className="space-y-6">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Card key={i} className="border shadow-sm">
                      <CardContent className="p-4 space-y-2">
                        <Skeleton className="h-3 w-16" />
                        <Skeleton className="h-6 w-24" />
                        <Skeleton className="h-4 w-20" />
                      </CardContent>
                    </Card>
                  ))}
                </div>
                <div className="divide-y divide-border">
                  {Array.from({ length: 6 }).map((_, i) => <SmallSkeleton key={i} />)}
                </div>
              </div>
            ) : marketPulse ? (
              <div className="space-y-6">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {marketPulse.indices.map((idx) => (
                    <MarketIndexCard key={idx.symbol} index={idx} />
                  ))}
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-muted-foreground mb-2">Related News</h2>
                  <div className="divide-y divide-border">
                    {marketPulse.news.map((item, i) => (
                      <RealtimeNewsCard key={`${item.link}-${i}`} item={item} />
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-20 text-muted-foreground space-y-3">
                <BarChart3 size={40} className="mx-auto opacity-30" />
                <p className="text-lg font-medium">No market data</p>
                <p className="text-sm">Click this tab to load market pulse data.</p>
              </div>
            )}
          </TabsContent>

          {/* ---- Stocks News Tab ---- */}
          <TabsContent value="stocks">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-muted-foreground">
                News for popular stocks (AAPL, MSFT, NVDA, GOOGL, AMZN...){stocksNews.length > 0 ? ` (${stocksNews.length} articles)` : ''}
              </p>
            </div>
            <NewsListTab items={stocksNews} loading={stocksLoading} icon={<DollarSign size={40} className="mx-auto opacity-30" />} emptyMessage="No stocks news available. Try refreshing." />
          </TabsContent>

          {/* ---- ETF News Tab ---- */}
          <TabsContent value="etf">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-muted-foreground">
                News for popular ETFs (SPY, QQQ, DIA, IWM, VTI...){etfNews.length > 0 ? ` (${etfNews.length} articles)` : ''}
              </p>
            </div>
            <NewsListTab items={etfNews} loading={etfLoading} icon={<PieChart size={40} className="mx-auto opacity-30" />} emptyMessage="No ETF news available. Try refreshing." />
          </TabsContent>

          {/* ---- News Insights Tab ---- */}
          <TabsContent value="insights">
            {/* Analyzed results */}
            {analyzedArticles.length > 0 && !analyzingLoading && (
              <div className="mb-8">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold text-foreground">Analysis Results</h2>
                  <Button variant="ghost" size="sm" onClick={() => setAnalyzedArticles([])}>
                    Clear Results
                  </Button>
                </div>
                <div className="divide-y divide-border">
                  {analyzedArticles.map((article) => (
                    <AnalyzedArticleCard key={article.url} article={article} />
                  ))}
                </div>
              </div>
            )}

            {/* Loading */}
            {analyzingLoading && (
              <div className="mb-8 divide-y divide-border">
                {Array.from({ length: selectedUrls.size || 3 }).map((_, i) => <SkeletonCard key={i} />)}
              </div>
            )}

            {/* Article selection */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-foreground">
                  Select articles to analyze{selectedUrls.size > 0 && ` (${selectedUrls.size} selected)`}
                </h2>
                <div className="flex items-center gap-3">
                  <button type="button" className="text-xs text-primary hover:underline" onClick={selectAll}>
                    Select all
                  </button>
                  <button type="button" className="text-xs text-muted-foreground hover:underline" onClick={clearSelection}>
                    Clear
                  </button>
                  <Button size="sm" onClick={handleAnalyze} disabled={analyzingLoading || selectedUrls.size === 0 || !selectedModel}>
                    <Search size={14} className={analyzingLoading ? 'animate-spin mr-1.5' : 'mr-1.5'} />
                    {analyzingLoading ? 'Analyzing...' : `Analyze (${selectedUrls.size})`}
                  </Button>
                </div>
              </div>

              {realtimeLoading && !realtimeLoaded && (
                <div className="divide-y divide-border">
                  {Array.from({ length: 6 }).map((_, i) => <SmallSkeleton key={i} />)}
                </div>
              )}

              {realtimeLoaded && realtimeNews.length > 0 && (
                <div className="divide-y divide-border">
                  {realtimeNews.map((item, idx) => (
                    <label
                      key={`${item.link}-${idx}`}
                      className="flex items-start gap-3 py-3 cursor-pointer hover:bg-accent/30 -mx-2 px-2 rounded-md transition-colors"
                    >
                      <Checkbox
                        checked={selectedUrls.has(item.link)}
                        onCheckedChange={() => toggleUrl(item.link)}
                        className="mt-0.5"
                      />
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <ProviderBadge provider={item.provider} />
                          <span className="font-medium uppercase tracking-wide">{item.source}</span>
                          <span>&middot;</span>
                          <span>{item.date}</span>
                        </div>
                        <p className="text-sm font-medium text-foreground leading-snug">{item.title}</p>
                        <div className="flex items-center gap-1 text-xs text-muted-foreground/60">
                          <ExternalLink size={10} />
                          <span className="truncate max-w-xs">{item.source}</span>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              )}

              {realtimeLoaded && realtimeNews.length === 0 && !realtimeLoading && (
                <div className="text-center py-16 text-muted-foreground space-y-3">
                  <Newspaper size={40} className="mx-auto opacity-30" />
                  <p className="text-lg font-medium">No articles available</p>
                  <p className="text-sm">Load real-time news first from the Real-time News tab.</p>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
