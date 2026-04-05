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

/** One row from the ownership changes endpoint. */
export interface OwnershipChangeRecord {
  filing_date: string;
  accession_no: string;
  insider_name: string;
  position: string;
  shares_before: number | null;
  shares_after: number | null;
  net_change: number;
  form_type: string;
}

/**
 * Top-level response from GET /insider/ownership.
 * Includes records list, deduplicated insiders list, total count, and skipped_count.
 */
export interface OwnershipChangesResponse {
  ticker: string;
  records: OwnershipChangeRecord[];
  insiders: string[];
  total: number;
  skipped_count: number;
}

/** One derivative trade row from the grants endpoint. */
export interface GrantRecord {
  filing_date: string;
  accession_no: string;
  insider_name: string;
  position: string;
  transaction_type: string;
  security_title: string;
  exercise_price: number | null;
  expiration_date: string | null;
  shares: number | null;
  underlying_security: string | null;
  acquired_disposed: string;
  code: string;
}

/**
 * Top-level response from GET /insider/grants.
 * Includes records list, total count, and skipped_count for error reporting.
 */
export interface GrantsResponse {
  ticker: string;
  records: GrantRecord[];
  total: number;
  skipped_count: number;
}

/** One row from the OpenInsider screener table. */
export interface OpenInsiderRecord {
  filing_date: string;
  trade_date: string;
  ticker: string;
  company_name: string;
  insider_name: string;
  title: string;
  trade_type: string;
  price: number | null;
  qty: number | null;
  owned: number | null;
  delta_own: string | null;
  value: number | null;
}

/**
 * Top-level response from GET /insider/openinsider/screener.
 * Includes screener records, total count, preset name, and cache status.
 */
export interface OpenInsiderResponse {
  preset: string;
  records: OpenInsiderRecord[];
  total: number;
  cached: boolean;
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

  /**
   * Fetch ownership change records for a ticker.
   * Maps to GET /insider/ownership.
   */
  async getOwnership(
    ticker: string,
    formType: string = '4',
    limit: number = 50,
    offset: number = 0
  ): Promise<OwnershipChangesResponse> {
    const params = new URLSearchParams({
      ticker: ticker,
      form_type: formType,
      limit: String(limit),
      offset: String(offset),
    });
    const response = await fetch(`${this.baseUrl}/ownership?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch ownership changes: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Fetch derivative grants and exercises records for a ticker.
   * Maps to GET /insider/grants.
   */
  async getGrants(
    ticker: string,
    formType: string = '4',
    limit: number = 50,
    offset: number = 0
  ): Promise<GrantsResponse> {
    const params = new URLSearchParams({
      ticker: ticker,
      form_type: formType,
      limit: String(limit),
      offset: String(offset),
    });
    const response = await fetch(`${this.baseUrl}/grants?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch grants data: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Fetch insider trading records from openinsider.com via the screener endpoint.
   * Maps to GET /insider/openinsider/screener.
   * For preset modes (ceo_cfo_conviction, cluster_buy, significant_increase), customParams are ignored by the backend.
   */
  async getOpenInsiderScreener(
    preset: string,
    customParams?: Record<string, string>
  ): Promise<OpenInsiderResponse> {
    const params = new URLSearchParams({ preset });
    if (customParams) {
      Object.entries(customParams).forEach(([key, value]) => {
        params.set(key, value);
      });
    }
    const response = await fetch(`${this.baseUrl}/openinsider/screener?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch OpenInsider screener data: ${response.statusText}`);
    }
    return response.json();
  }
}

export const insiderService = new InsiderService();
