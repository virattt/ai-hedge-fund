const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

export interface IdeaSignal {
  source: string;
  score: number;
  label: string;
  detail: Record<string, unknown> | null;
}

export interface DiscoveryIdea {
  ticker: string;
  company: string | null;
  cik: number | null;
  score: number;
  signals: IdeaSignal[];
  is_ticker: boolean;
  return_30d_pct: number | null;
  alpha_30d_pct: number | null;
  distance_from_whale_entry_pct: number | null;
}

export interface DiscoveryResponse {
  ideas: DiscoveryIdea[];
  total: number;
  cached: boolean;
  generated_at: string;
}

class DiscoveryService {
  private baseUrl = `${API_BASE_URL}/discovery`;

  async getIdeas(limit: number = 50, maxAboveWhalePct?: number): Promise<DiscoveryResponse> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (maxAboveWhalePct != null && maxAboveWhalePct > 0) {
      params.set('max_above_whale_pct', String(maxAboveWhalePct));
    }
    const r = await fetch(`${this.baseUrl}/ideas?${params.toString()}`);
    if (!r.ok) {
      const body = await r.json().catch(() => null);
      throw new Error(body?.detail || `Discovery fetch failed: ${r.statusText}`);
    }
    return r.json();
  }
}

export const discoveryService = new DiscoveryService();
