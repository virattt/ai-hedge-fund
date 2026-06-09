const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

export interface SpinoffFiling {
  accession_no: string;
  cik: number;
  company: string;
  form: string;
  filing_date: string;
  primary_doc_url: string | null;
  primary_doc_description: string | null;
}

export interface SpinoffListResponse {
  filings: SpinoffFiling[];
  total: number;
  cached: boolean;
}

export interface InsiderPurchase {
  filing_date: string;
  accession_no: string;
  insider_name: string;
  insider_title: string | null;
  shares: number | null;
  price_per_share: number | null;
  value: number | null;
}

export interface SpinoffInsiderSummary {
  cik: number;
  purchase_count: number;
  total_value: number;
  purchases: InsiderPurchase[];
  cached: boolean;
}

class CatalystService {
  private baseUrl = `${API_BASE_URL}/catalysts`;

  async getSpinoffs(
    dateFrom?: string,
    dateTo?: string,
    limit: number = 50,
    offset: number = 0,
  ): Promise<SpinoffListResponse> {
    const params = new URLSearchParams();
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    params.set('limit', String(limit));
    params.set('offset', String(offset));

    const response = await fetch(`${this.baseUrl}/spinoffs?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch spin-offs: ${response.statusText}`);
    }
    return response.json();
  }

  async getSpinoffInsiders(cik: number): Promise<SpinoffInsiderSummary> {
    const response = await fetch(`${this.baseUrl}/spinoffs/${cik}/insiders`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch insider activity: ${response.statusText}`);
    }
    return response.json();
  }
}

export const catalystService = new CatalystService();
