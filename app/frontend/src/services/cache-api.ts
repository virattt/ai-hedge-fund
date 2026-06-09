const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

export interface CacheFlushResponse {
  cleared: Record<string, number>;
  total_entries: number;
}

class CacheService {
  private base = `${API_BASE_URL}/cache`;

  async flush(): Promise<CacheFlushResponse> {
    const response = await fetch(`${this.base}/flush`, { method: 'POST' });
    if (!response.ok) {
      throw new Error(`Cache flush failed: ${response.statusText}`);
    }
    return response.json();
  }
}

export const cacheService = new CacheService();
