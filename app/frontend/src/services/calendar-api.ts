const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

export interface EarningsCalendarItem {
  date: string;
  ticker: string;
  company: string | null;
  eps_estimate: number | null;
  eps_actual: number | null;
  revenue_estimate: number | null;
  revenue_actual: number | null;
  hour: string | null;
  quarter: number | null;
  fiscal_year: number | null;
}

export interface EarningsCalendarResponse {
  items: EarningsCalendarItem[];
  date_from: string;
  date_to: string;
  total: number;
  cached: boolean;
}

class CalendarService {
  private baseUrl = `${API_BASE_URL}/calendar`;

  async getEarnings(dateFrom?: string, dateTo?: string): Promise<EarningsCalendarResponse> {
    const params = new URLSearchParams();
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    const r = await fetch(`${this.baseUrl}/earnings?${params.toString()}`);
    if (!r.ok) {
      const body = await r.json().catch(() => null);
      throw new Error(body?.detail || `Calendar fetch failed: ${r.statusText}`);
    }
    return r.json();
  }
}

export const calendarService = new CalendarService();
