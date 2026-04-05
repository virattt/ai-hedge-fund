const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface NewsArticle {
  id: number;
  title: string;
  summary: string;
  market_insight: string;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  tickers_mentioned: string[];
  source_url: string;
  source_name: string;
  scraped_at: string;
  website_id: number;
}

export interface NewsSummarizeRequest {
  model_name: string;
  model_provider: string;
  result_ids?: number[];
  website_ids?: number[];
  limit?: number;
}

export interface RealtimeNewsItem {
  title: string;
  link: string;
  source: string;
  date: string;
  category: 'news' | 'blog';
  provider: 'finviz' | 'yfinance';
}

// Rank relevance
export interface RankRelevanceRequest {
  titles: string[];
  model_name: string;
  model_provider: string;
}

export interface RankedNewsItem {
  index: number;
  relevance_score: number;
  reason: string;
}

// Article analysis
export interface AnalyzeArticleInput {
  url: string;
  title: string;
  source: string;
}

export interface AnalyzeArticlesRequest {
  articles: AnalyzeArticleInput[];
  model_name: string;
  model_provider: string;
}

export interface AnalyzedArticle {
  url: string;
  title: string;
  summary: string;
  market_insight: string;
  sentiment: string;
  tickers_mentioned: string[];
  source_name: string;
  analyzed_at: string;
}

// Market Pulse
export interface MarketIndex {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_percent: number;
}

export interface MarketPulseData {
  indices: MarketIndex[];
  news: RealtimeNewsItem[];
}

class NewsService {
  private baseUrl = `${API_BASE_URL}/news`;

  async summarize(request: NewsSummarizeRequest): Promise<NewsArticle[]> {
    const response = await fetch(`${this.baseUrl}/summarize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to summarize news: ${response.statusText}`);
    }
    return response.json();
  }

  async getRealtimeNews(): Promise<RealtimeNewsItem[]> {
    const response = await fetch(`${this.baseUrl}/realtime`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch realtime news: ${response.statusText}`);
    }
    return response.json();
  }

  async rankRelevance(request: RankRelevanceRequest, signal?: AbortSignal): Promise<RankedNewsItem[]> {
    console.log('[rankRelevance] sending request, titles:', request.titles.length, 'model:', request.model_name);
    const response = await fetch(`${this.baseUrl}/rank-relevance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal,
    });
    console.log('[rankRelevance] response status:', response.status);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to rank news: ${response.statusText}`);
    }
    const data = await response.json();
    console.log('[rankRelevance] parsed data, items:', data?.length, 'first:', JSON.stringify(data?.[0]));
    return data;
  }

  async analyzeArticles(request: AnalyzeArticlesRequest): Promise<AnalyzedArticle[]> {
    const response = await fetch(`${this.baseUrl}/analyze-articles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to analyze articles: ${response.statusText}`);
    }
    return response.json();
  }

  async getBlogNews(): Promise<RealtimeNewsItem[]> {
    const response = await fetch(`${this.baseUrl}/blogs`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch blog news: ${response.statusText}`);
    }
    return response.json();
  }

  async getStocksNews(): Promise<RealtimeNewsItem[]> {
    const response = await fetch(`${this.baseUrl}/stocks`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch stocks news: ${response.statusText}`);
    }
    return response.json();
  }

  async getEtfNews(): Promise<RealtimeNewsItem[]> {
    const response = await fetch(`${this.baseUrl}/etf`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch ETF news: ${response.statusText}`);
    }
    return response.json();
  }

  async getMarketPulse(): Promise<MarketPulseData> {
    const response = await fetch(`${this.baseUrl}/market-pulse`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch market pulse: ${response.statusText}`);
    }
    return response.json();
  }
}

export const newsService = new NewsService();
