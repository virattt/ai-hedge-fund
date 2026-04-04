const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** Monthly buy/sell activity entry for the activity chart. */
export interface ActivityByDate {
  date: string;
  purchases: number;
  sales: number;
  purchase_value: number;
  sale_value: number;
}

/**
 * One row per filing from the summary endpoint.
 * Uses accession_no as the stable SEC filing identifier.
 */
export interface InsiderFilingSummary {
  filing_date: string;
  accession_no: string;
  insider_name: string;
  position: string;
  primary_activity: string;
  net_change: number;
  net_value: number | null;
  remaining_shares: number | null;
  has_10b5_1_plan: boolean | null;
  transaction_types: string[];
  transaction_count: number;
  form_type: string;
  // Form 3 (InitialOwnershipSummary) specific fields
  total_holdings: number | null;
  has_derivatives: boolean | null;
}

/** Computed dashboard-level statistics across all processed filings. */
export interface InsiderAggregates {
  total_filings: number;
  total_purchases: number;
  total_sales: number;
  total_other: number;
  net_sentiment: number;
  largest_transaction_value: number | null;
  largest_transaction_insider: string | null;
  plan_10b5_1_count: number;
  plan_10b5_1_ratio: number;
  activity_by_date: ActivityByDate[];
}

/**
 * Top-level response from GET /insider/summary.
 * Includes filings list, aggregates, and skipped_count for error reporting.
 */
export interface InsiderSummaryResponse {
  ticker: string;
  form_type: string;
  filings: InsiderFilingSummary[];
  aggregates: InsiderAggregates;
  total: number;
  skipped_count: number;
}

/** One row per transaction from the detail endpoint. */
export interface InsiderTransactionDetail {
  transaction_type: string;
  code: string;
  description: string | null;
  shares: number | null;
  price_per_share: number | null;
  value: number | null;
  security_type: string | null;
  security_title: string | null;
  is_10b5_1_plan: boolean | null;
  is_derivative: boolean;
}

/**
 * Response from GET /insider/detail.
 * Keyed by accession_no which is the stable SEC filing identifier.
 */
export interface InsiderDetailResponse {
  ticker: string;
  filing_date: string;
  accession_no: string;
  insider_name: string;
  position: string;
  form_type: string;
  transactions: InsiderTransactionDetail[];
  market_trades_count: number;
  derivative_trades_count: number;
}

class InsiderService {
  private baseUrl = `${API_BASE_URL}/insider`;

  /**
   * Fetch filing summaries for a ticker and form type.
   * Maps to GET /insider/summary.
   */
  async getSummary(
    ticker: string,
    formType: string = '4',
    limit: number = 50,
    offset: number = 0
  ): Promise<InsiderSummaryResponse> {
    const params = new URLSearchParams({
      ticker: ticker,
      form_type: formType,
      limit: String(limit),
      offset: String(offset),
    });
    const response = await fetch(`${this.baseUrl}/summary?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch insider summary: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Fetch per-transaction detail for a specific filing identified by accession_no.
   * Maps to GET /insider/detail.
   */
  async getDetail(
    ticker: string,
    formType: string,
    accessionNo: string
  ): Promise<InsiderDetailResponse> {
    const params = new URLSearchParams({
      ticker: ticker,
      form_type: formType,
      accession_no: accessionNo,
    });
    const response = await fetch(`${this.baseUrl}/detail?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch insider detail: ${response.statusText}`);
    }
    return response.json();
  }
}

export const insiderService = new InsiderService();
