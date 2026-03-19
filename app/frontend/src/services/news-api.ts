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
}

export const newsService = new NewsService();
