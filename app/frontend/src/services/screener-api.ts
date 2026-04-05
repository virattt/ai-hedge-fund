const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ScreenerFilters {
  filters: Record<string, string[]>;
  signals: string[];
  orders: string[];
}

export interface ScreenerRequest {
  filters: Record<string, string>;
  signal: string;
  ticker: string;
  order: string;
  ascend: boolean;
  limit: number;
  view: string;
}

export interface ScreenerResponse {
  columns: string[];
  rows: Record<string, any>[];
  total: number;
}

class ScreenerService {
  private baseUrl = `${API_BASE_URL}/screener`;

  async getFilters(): Promise<ScreenerFilters> {
    const response = await fetch(`${this.baseUrl}/filters`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch screener filters: ${response.statusText}`);
    }
    return response.json();
  }

  async search(request: ScreenerRequest): Promise<ScreenerResponse> {
    const response = await fetch(`${this.baseUrl}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to run screener search: ${response.statusText}`);
    }
    return response.json();
  }
}

export const screenerService = new ScreenerService();
