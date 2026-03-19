import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Check, ChevronsUpDown, ExternalLink, Lightbulb, Newspaper, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ModelSelector } from '@/components/ui/llm-selector';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { type LanguageModel, getModels, getDefaultModel } from '@/data/models';
import { type NewsArticle, type RealtimeNewsItem, newsService } from '@/services/news-api';
import { scrapingService, Website } from '@/services/scraping-api';

/* -------------------------------------------------------------------------- */
/*  News Insights tab components (existing)                                   */
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

function ArticleCard({ article }: { article: NewsArticle }) {
  const date = new Date(article.scraped_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });

  return (
    <Card className="border-0 shadow-none bg-transparent">
      <CardContent className="px-0 py-6 space-y-3">
        <p className="text-xs text-muted-foreground font-medium tracking-wide uppercase">
          {article.source_name}
        </p>
        <a
          href={article.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="block group"
        >
          <h2 className="text-xl font-bold text-foreground group-hover:text-primary transition-colors leading-tight">
            {article.title}
          </h2>
        </a>
        <p className="text-muted-foreground leading-relaxed line-clamp-3">
          {article.summary}
        </p>
        <div className="flex items-start gap-2 rounded-md bg-amber-500/5 border border-amber-500/10 px-3 py-2">
          <Lightbulb size={14} className="text-amber-500 mt-0.5 shrink-0" />
          <p className="text-sm text-amber-700 dark:text-amber-400">{article.market_insight}</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap text-sm">
          <SentimentBadge sentiment={article.sentiment} />
          {article.tickers_mentioned.map((ticker) => (
            <Badge key={ticker} variant="secondary" className="text-xs font-mono">
              {ticker}
            </Badge>
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
/*  Real-time news tab components                                             */
/* -------------------------------------------------------------------------- */

function ProviderBadge({ provider }: { provider: string }) {
  const config: Record<string, { label: string; className: string }> = {
    finviz: { label: 'FinViz', className: 'bg-blue-500/10 text-blue-600 border-blue-500/30' },
    yfinance: { label: 'Yahoo', className: 'bg-purple-500/10 text-purple-600 border-purple-500/30' },
  };
  const { label, className } = config[provider] ?? { label: provider, className: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/30' };
  return <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${className}`}>{label}</Badge>;
}

function RealtimeNewsCard({ item }: { item: RealtimeNewsItem }) {
  return (
    <a
      href={item.link}
      target="_blank"
      rel="noopener noreferrer"
      className="block group py-4"
    >
      <div className="space-y-1.5">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <ProviderBadge provider={item.provider} />
          <span className="font-medium uppercase tracking-wide">{item.source}</span>
          <span>&middot;</span>
          <span>{item.date}</span>
          {item.category === 'blogs' && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0">Blog</Badge>
          )}
        </div>
        <h3 className="text-base font-semibold text-foreground group-hover:text-primary transition-colors leading-snug">
          {item.title}
        </h3>
        <div className="flex items-center gap-1 text-xs text-muted-foreground/60">
          <ExternalLink size={10} />
          <span className="truncate max-w-xs">{item.source}</span>
        </div>
      </div>
    </a>
  );
}

function RealtimeNewsSkeleton() {
  return (
    <div className="py-4 space-y-2">
      <div className="flex gap-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3 w-16" />
      </div>
      <Skeleton className="h-5 w-full" />
      <Skeleton className="h-5 w-4/5" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Main page                                                                 */
/* -------------------------------------------------------------------------- */

export function NewsPage() {
  const [models, setModels] = useState<LanguageModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<LanguageModel | null>(null);
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedWebsiteIds, setSelectedWebsiteIds] = useState<number[]>([]);
  const [websiteDropdownOpen, setWebsiteDropdownOpen] = useState(false);

  // Real-time news state
  const [realtimeNews, setRealtimeNews] = useState<RealtimeNewsItem[]>([]);
  const [realtimeLoading, setRealtimeLoading] = useState(false);
  const [realtimeLoaded, setRealtimeLoaded] = useState(false);

  // Load models and websites on mount
  useEffect(() => {
    (async () => {
      try {
        const [fetched, defaultModel, sites] = await Promise.all([
          getModels(),
          getDefaultModel(),
          scrapingService.getWebsites(),
        ]);
        setModels(fetched);
        setSelectedModel(defaultModel);
        setWebsites(sites);
      } catch {
        toast.error('Failed to load models');
      } finally {
        setInitialized(true);
      }
    })();
  }, []);

  // Auto-load real-time news on mount
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

  const toggleWebsite = (id: number) => {
    setSelectedWebsiteIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleGenerate = async () => {
    if (!selectedModel) {
      toast.error('Please select a model first');
      return;
    }
    setLoading(true);
    try {
      const results = await newsService.summarize({
        model_name: selectedModel.model_name,
        model_provider: selectedModel.provider,
        website_ids: selectedWebsiteIds.length > 0 ? selectedWebsiteIds : undefined,
        limit: 20,
      });
      setArticles(results);
      if (results.length === 0) {
        toast.info('No scraped content found. Add websites in the Scraping page first.');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to generate insights');
    } finally {
      setLoading(false);
    }
  };

  const websiteButtonLabel = selectedWebsiteIds.length === 0
    ? 'All websites'
    : selectedWebsiteIds.length === 1
      ? websites.find(w => w.id === selectedWebsiteIds[0])?.name ?? '1 website'
      : `${selectedWebsiteIds.length} websites`;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <BookOpen size={22} className="text-primary" />
          <h1 className="text-2xl font-bold text-foreground">News</h1>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="realtime" className="w-full">
          <TabsList className="mb-6">
            <TabsTrigger value="realtime" className="gap-1.5">
              <Newspaper size={14} />
              Real-time News
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
                Latest financial news from FinViz &amp; Yahoo Finance{realtimeNews.length > 0 ? ` (${realtimeNews.length} articles)` : ''}
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={loadRealtimeNews}
                disabled={realtimeLoading}
              >
                <RefreshCw size={14} className={realtimeLoading ? 'animate-spin mr-1.5' : 'mr-1.5'} />
                Refresh
              </Button>
            </div>

            {realtimeLoading && !realtimeLoaded && (
              <div className="divide-y divide-border">
                {Array.from({ length: 8 }).map((_, i) => (
                  <RealtimeNewsSkeleton key={i} />
                ))}
              </div>
            )}

            {realtimeLoaded && realtimeNews.length > 0 && (
              <div className="divide-y divide-border">
                {realtimeNews.map((item, idx) => (
                  <RealtimeNewsCard key={`${item.link}-${idx}`} item={item} />
                ))}
              </div>
            )}

            {realtimeLoaded && realtimeNews.length === 0 && !realtimeLoading && (
              <div className="text-center py-20 text-muted-foreground space-y-3">
                <Newspaper size={40} className="mx-auto opacity-30" />
                <p className="text-lg font-medium">No news available</p>
                <p className="text-sm">Could not fetch real-time news. Check your internet connection and try again.</p>
              </div>
            )}
          </TabsContent>

          {/* ---- News Insights Tab ---- */}
          <TabsContent value="insights">
            {/* Controls */}
            <div className="flex items-center gap-3 mb-4">
              <div className="flex-1">
                <ModelSelector
                  models={models}
                  value={selectedModel?.model_name ?? ''}
                  onChange={(m) => setSelectedModel(m)}
                  placeholder="Select an LLM model..."
                />
              </div>
              <Button onClick={handleGenerate} disabled={loading || !selectedModel}>
                <RefreshCw size={14} className={loading ? 'animate-spin mr-2' : 'mr-2'} />
                {loading ? 'Generating...' : 'Generate Insights'}
              </Button>
            </div>

            {/* Website filter */}
            {websites.length > 0 && (
              <div className="relative mb-8">
                <button
                  type="button"
                  className="flex items-center justify-between w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  onClick={() => setWebsiteDropdownOpen(!websiteDropdownOpen)}
                >
                  <span className="text-muted-foreground">{websiteButtonLabel}</span>
                  <ChevronsUpDown className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
                {websiteDropdownOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setWebsiteDropdownOpen(false)}
                    />
                    <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md py-1 max-h-56 overflow-y-auto">
                      <button
                        type="button"
                        className="flex items-center gap-2 w-full px-3 py-1.5 text-sm hover:bg-accent/50"
                        onClick={() => {
                          setSelectedWebsiteIds([]);
                          setWebsiteDropdownOpen(false);
                        }}
                      >
                        <span className="w-4 h-4 flex items-center justify-center">
                          {selectedWebsiteIds.length === 0 && <Check className="h-3.5 w-3.5" />}
                        </span>
                        <span>All websites</span>
                      </button>
                      {websites.map(website => (
                        <button
                          key={website.id}
                          type="button"
                          className="flex items-center gap-2 w-full px-3 py-1.5 text-sm hover:bg-accent/50"
                          onClick={() => toggleWebsite(website.id)}
                        >
                          <span className="w-4 h-4 flex items-center justify-center">
                            {selectedWebsiteIds.includes(website.id) && <Check className="h-3.5 w-3.5" />}
                          </span>
                          <span className="truncate">{website.name}</span>
                          <span className="text-xs text-muted-foreground ml-auto truncate max-w-[200px]">{website.url}</span>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Loading */}
            {loading && (
              <div className="divide-y divide-border">
                {Array.from({ length: 3 }).map((_, i) => (
                  <SkeletonCard key={i} />
                ))}
              </div>
            )}

            {/* Articles */}
            {!loading && articles.length > 0 && (
              <div className="divide-y divide-border">
                {articles.map((article) => (
                  <ArticleCard key={article.id} article={article} />
                ))}
              </div>
            )}

            {/* Empty state */}
            {!loading && articles.length === 0 && initialized && (
              <div className="text-center py-20 text-muted-foreground space-y-3">
                <BookOpen size={40} className="mx-auto opacity-30" />
                <p className="text-lg font-medium">No news insights yet</p>
                <p className="text-sm">
                  Add websites in the{' '}
                  <Link to="/scraping" className="text-primary hover:underline">
                    Scraping page
                  </Link>{' '}
                  and scrape some content, then come back to generate insights.
                </p>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
