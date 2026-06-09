const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

export interface WatchlistItem {
  id: number;
  ticker: string;
  notes: string | null;
  added_at: string;
  last_analyzed_at: string | null;
  last_overall_sentiment: string | null;
  last_delta_direction: string | null;
  last_management_tone: string | null;
  last_payload: Record<string, unknown> | null;
  last_error: string | null;
  return_pct_since_added: number | null;
  alpha_pct_vs_spy: number | null;
  distance_from_whale_entry_pct: number | null;
}

export interface WatchlistListResponse {
  items: WatchlistItem[];
  total: number;
}

export interface BatchRunResponse {
  analyzed: number;
  succeeded: number;
  failed: number;
}

class WatchlistService {
  private baseUrl = `${API_BASE_URL}/watchlist`;

  async list(): Promise<WatchlistListResponse> {
    const r = await fetch(`${this.baseUrl}/`);
    if (!r.ok) throw new Error(`Failed to load watchlist: ${r.statusText}`);
    return r.json();
  }

  async add(ticker: string, notes?: string): Promise<WatchlistItem> {
    const r = await fetch(`${this.baseUrl}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, notes }),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || `Add failed: ${r.statusText}`);
    return r.json();
  }

  async remove(ticker: string): Promise<void> {
    const r = await fetch(`${this.baseUrl}/${encodeURIComponent(ticker)}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(`Remove failed: ${r.statusText}`);
  }

  async updateNotes(ticker: string, notes: string | null): Promise<WatchlistItem> {
    const r = await fetch(`${this.baseUrl}/${encodeURIComponent(ticker)}/notes`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    });
    if (!r.ok) throw new Error(`Notes update failed: ${r.statusText}`);
    return r.json();
  }

  async runBatch(): Promise<BatchRunResponse> {
    const r = await fetch(`${this.baseUrl}/batch/run`, { method: 'POST' });
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || `Batch failed: ${r.statusText}`);
    return r.json();
  }

  async refreshOne(ticker: string): Promise<WatchlistItem> {
    const r = await fetch(`${this.baseUrl}/${encodeURIComponent(ticker)}/refresh`, { method: 'POST' });
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || `Refresh failed: ${r.statusText}`);
    return r.json();
  }
}

export const watchlistService = new WatchlistService();
