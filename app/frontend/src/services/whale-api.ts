const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

export interface WhaleFund {
  id: number;
  cik: number;
  name: string;
  notes: string | null;
  added_at: string | null;
}

export interface WhaleFundListResponse {
  items: WhaleFund[];
  total: number;
}

export interface WhaleFundCandidate {
  cik: number;
  company: string;
}

export interface WhaleFundCandidatesResponse {
  candidates: WhaleFundCandidate[];
}

export interface WhaleEntry {
  whale_cik: number;
  whale_name: string;
  ticker: string;
  entry_quarter_label: string | null;
  entry_period_start: string | null;
  entry_period_end: string | null;
  entry_vwap: number | null;
  entry_low: number | null;
  entry_high: number | null;
  share_count_at_entry: number | null;
  is_pre_lookback: boolean;
  computed_at: string | null;
}

export interface TickerWhaleSummary {
  ticker: string;
  current_price: number | null;
  best_entry_vwap: number | null;
  best_entry_whale_cik: number | null;
  best_entry_whale_name: string | null;
  distance_from_best_entry_pct: number | null;
  whale_count: number;
  entries: WhaleEntry[];
}

export interface WhaleRefreshResponse {
  refreshed: Record<number, number>;
  total_rows_written: number;
}

function extractDetail(body: unknown): string {
  if (!body || typeof body !== 'object') return '';
  const detail = (body as Record<string, unknown>).detail;
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((e) => (typeof e === 'string' ? e : (e?.msg ?? JSON.stringify(e)))).join('; ');
  }
  return JSON.stringify(detail);
}

class WhaleService {
  private base = `${API_BASE_URL}/whales`;

  async listFunds(): Promise<WhaleFundListResponse> {
    const response = await fetch(`${this.base}/funds`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(extractDetail(body) || `Failed to list whale funds: ${response.statusText}`);
    }
    return response.json();
  }

  async addFund(cik: number, name: string, notes?: string): Promise<WhaleFund> {
    const response = await fetch(`${this.base}/funds`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cik, name, notes: notes ?? null }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(extractDetail(body) || `Failed to add whale fund: ${response.statusText}`);
    }
    return response.json();
  }

  async removeFund(cik: number): Promise<void> {
    const response = await fetch(`${this.base}/funds/${cik}`, { method: 'DELETE' });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(extractDetail(body) || `Failed to remove whale fund: ${response.statusText}`);
    }
  }

  async searchCandidates(q: string, limit = 10): Promise<WhaleFundCandidatesResponse> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    const response = await fetch(`${this.base}/funds/search?${params}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(extractDetail(body) || `Failed to search whale candidates: ${response.statusText}`);
    }
    return response.json();
  }

  async refreshAll(force = false): Promise<WhaleRefreshResponse> {
    const params = new URLSearchParams({ force: String(force) });
    const response = await fetch(`${this.base}/refresh?${params}`, { method: 'POST' });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(extractDetail(body) || `Failed to refresh whales: ${response.statusText}`);
    }
    return response.json();
  }

  async getTickerSummary(ticker: string): Promise<TickerWhaleSummary> {
    const response = await fetch(`${this.base}/entries/${encodeURIComponent(ticker)}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(extractDetail(body) || `Failed to fetch whale entries: ${response.statusText}`);
    }
    return response.json();
  }
}

export const whaleService = new WhaleService();
