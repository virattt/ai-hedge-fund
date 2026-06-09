const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

/**
 * Coerce the FastAPI error `detail` field into a flat string. FastAPI's 422
 * validation responses emit `detail` as an array of objects, which the default
 * `String(arr)` would render as "[object Object]" — so we join `.msg` fields
 * instead. Returns empty string when there is no detail.
 */
function extractDetail(body: unknown): string {
  if (!body || typeof body !== 'object') return '';
  const detail = (body as Record<string, unknown>).detail;
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((entry) => {
        if (typeof entry === 'string') return entry;
        if (entry && typeof entry === 'object' && 'msg' in entry) {
          return String((entry as Record<string, unknown>).msg);
        }
        return JSON.stringify(entry);
      })
      .join('; ');
  }
  return JSON.stringify(detail);
}

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

/** Lightweight filing entry for the 13F-HR listing. */
export interface ThirteenFFilingListItem {
  filing_date: string;
  accession_no: string;
  company: string;
  cik: number;
  form: string;
  signer_name: string | null;
  signer_title: string | null;
  total_value: number | null;
  total_holdings: number | null;
}

/** Paginated response from GET /insider/thirteenf. */
export interface ThirteenFListResponse {
  filings: ThirteenFFilingListItem[];
  total: number;
  has_more: boolean;
  skipped_count: number;
}

/** Company name + CIK pair for the filter dropdown. */
export interface ThirteenFCompanyItem {
  company: string;
  cik: number;
}

/** Response from GET /insider/thirteenf/companies. */
export interface ThirteenFCompaniesResponse {
  companies: ThirteenFCompanyItem[];
  total: number;
}

/** Response from GET /insider/thirteenf/selections. */
export interface ThirteenFSavedSelectionsResponse {
  selections: ThirteenFCompanyItem[];
  total: number;
}

/** Per-company breakdown within an aggregated ticker row. */
export interface AggregateHoldingCompanyDetail {
  company: string;
  cik: number;
  shares: number | null;
  prev_shares: number | null;
  share_change_pct: number | null;
  value: number | null;
  prev_value: number | null;
  value_change_pct: number | null;
  status: string;
}

/** One ticker row aggregated across multiple 13F-HR filers. */
export interface AggregateHoldingRecord {
  ticker: string;
  issuer: string;
  companies: number;
  company_details: AggregateHoldingCompanyDetail[];
  total_shares: number;
  total_value: number;
  total_prev_shares: number;
  total_prev_value: number;
  avg_share_change_pct: number | null;
  avg_value_change_pct: number | null;
}

/** Response from GET /insider/thirteenf/aggregate. */
export interface AggregateHoldingsResponse {
  records: AggregateHoldingRecord[];
  total: number;
  companies_processed: number;
  errors: string[];
}

/** One row from the compare_holdings DataFrame. */
export interface CompareHoldingsRecord {
  cusip: string;
  ticker: string | null;
  issuer: string;
  shares: number | null;
  prev_shares: number | null;
  value: number | null;
  prev_value: number | null;
  share_change: number | null;
  share_change_pct: number | null;
  value_change: number | null;
  value_change_pct: number | null;
  status: string;
}

/**
 * Response from GET /insider/thirteenf/compare.
 * Contains quarter-over-quarter holding comparison for a specific filing.
 */
export interface CompareHoldingsResponse {
  accession_no: string;
  current_period: string;
  previous_period: string;
  manager_name: string;
  records: CompareHoldingsRecord[];
  total: number;
}

/** One row from the holding_history DataFrame. Dynamic period columns nested under periods_data. */
export interface HoldingHistoryRecord {
  cusip: string;
  ticker: string | null;
  issuer: string;
  periods_data: Record<string, number | null>;
  change_pct: number | null;
}

/**
 * Response from GET /insider/thirteenf/history.
 * Contains multi-period holding history for a specific filing.
 */
export interface HoldingHistoryResponse {
  accession_no: string;
  manager_name: string;
  periods: string[];
  records: HoldingHistoryRecord[];
  total: number;
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

// ---------------------------------------------------------------------------
// Finnhub Short Interest types
// ---------------------------------------------------------------------------

/** Short interest metrics for a single ticker from Finnhub. */
export interface ShortInterestData {
  symbol: string;
  short_pct_float: number | null;
  days_to_cover: number | null;
  shares_short: number | null;
  float_shares: number | null;
}

/** Response from GET /insider/finnhub/short-interest. */
export interface ShortInterestResponse {
  symbol: string;
  data: ShortInterestData | null;
  cached: boolean;
}

/** One squeeze candidate from the cross-reference screener. */
export interface SqueezeCandidate {
  ticker: string;
  company_name: string;
  short_pct_float: number | null;
  days_to_cover: number | null;
  shares_short: number | null;
  insider_buy_count: number;
  insider_buy_value: number;
  latest_insider_buy_date: string | null;
}

/** Response from GET /insider/finnhub/squeeze. */
export interface SqueezeScreenerResponse {
  candidates: SqueezeCandidate[];
  total: number;
}

// ---------------------------------------------------------------------------
// Political & Policy types
// ---------------------------------------------------------------------------

/** One government contract award from the USA Spending API. */
export interface GovContract {
  award_id: string | null;
  recipient_name: string | null;
  award_amount: number | null;
  awarding_agency: string | null;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
}

/** Response from GET /insider/political/contracts. */
export interface GovContractsResponse {
  contracts: GovContract[];
  total: number;
  cached: boolean;
}

/** One congressional stock trade from House Stock Watcher. */
export interface CongressTrade {
  representative: string | null;
  ticker: string | null;
  transaction_type: string | null;
  amount: string | null;
  transaction_date: string | null;
  disclosure_date: string | null;
  district: string | null;
  ptr_link: string | null;
}

/** Response from GET /insider/political/congress. */
export interface CongressTradesResponse {
  trades: CongressTrade[];
  total: number;
  source_available: boolean;
  cached: boolean;
}

// ---------------------------------------------------------------------------
// Earnings Sentiment types
// ---------------------------------------------------------------------------

/** LLM-structured output for a single earnings call transcript. */
export interface TranscriptAnalysis {
  overall_sentiment: string;
  confidence: number;
  management_tone: string;
  key_themes: string[];
  forward_guidance: string;
  notable_quotes: string[];
}

/** Full sentiment record for one earnings call. */
export interface TranscriptSentiment {
  ticker: string;
  quarter: string;
  year: number;
  date: string;
  analysis: TranscriptAnalysis;
  source: string;
}

/** Comparison between two consecutive transcripts. */
export interface SentimentDelta {
  current: TranscriptSentiment;
  previous: TranscriptSentiment | null;
  delta_direction: string;
  delta_magnitude: number;
  key_changes: string[];
}

/** Response from GET /insider/earnings/analysis. */
export interface EarningsAnalysisResponse {
  ticker: string;
  transcripts: TranscriptSentiment[];
  delta: SentimentDelta | null;
  cached: boolean;
}

/** One conviction signal combining earnings sentiment + insider activity. */
export interface ConvictionSignal {
  ticker: string;
  sentiment_delta: string;
  management_tone: string;
  key_themes: string[];
  insider_activity: string;
  insider_buy_count: number;
  insider_buy_value: number;
  ceo_cfo_buying: boolean;
  conviction_score: number;
  reasoning: string;
}

/** Response from GET /insider/earnings/conviction. */
export interface ConvictionResponse {
  signals: ConvictionSignal[];
  total: number;
  cached: boolean;
}

class InsiderService {
  private baseUrl = `${API_BASE_URL}/insider`;

  // -----------------------------------------------------------------------
  // Finnhub Short Interest
  // -----------------------------------------------------------------------

  /**
   * Fetch short interest metrics for a single ticker from Finnhub.
   * Maps to GET /insider/finnhub/short-interest.
   */
  async getShortInterest(symbol: string): Promise<ShortInterestResponse> {
    const params = new URLSearchParams({ symbol });
    const response = await fetch(`${this.baseUrl}/finnhub/short-interest?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(extractDetail(body) || `Failed to fetch short interest: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Fetch squeeze screener candidates (insider buys + short interest).
   * Maps to GET /insider/finnhub/squeeze.
   */
  async getSqueezeScreener(): Promise<SqueezeScreenerResponse> {
    const response = await fetch(`${this.baseUrl}/finnhub/squeeze`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch squeeze screener: ${response.statusText}`);
    }
    return response.json();
  }

  // -----------------------------------------------------------------------
  // SEC Insider
  // -----------------------------------------------------------------------

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
      throw new Error(extractDetail(body) || `Failed to fetch insider summary: ${response.statusText}`);
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

  /**
   * Fetch paginated 13F-HR filings across all companies.
   * Maps to GET /insider/thirteenf.
   * When companyName is provided, filters filings by fuzzy company name match via the backend.
   */
  async getThirteenFFilings(
    limit?: number,
    offset?: number,
    year?: number,
    quarter?: number,
    companyName?: string,
    ciks?: number[],
    dateFrom?: string,
    dateTo?: string
  ): Promise<ThirteenFListResponse> {
    const params = new URLSearchParams();
    if (limit !== undefined) params.set('limit', String(limit));
    if (offset !== undefined) params.set('offset', String(offset));
    if (year !== undefined) params.set('year', String(year));
    if (quarter !== undefined) params.set('quarter', String(quarter));
    if (companyName) params.set('company_name', companyName);
    if (ciks && ciks.length > 0) params.set('ciks', ciks.join(','));
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    const response = await fetch(`${this.baseUrl}/thirteenf?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch 13F filings: ${response.statusText}`);
    }
    return response.json();
  }

  /** Fetch unique company names across all 13F-HR filings. Maps to GET /insider/thirteenf/companies. */
  async getThirteenFCompanies(): Promise<ThirteenFCompaniesResponse> {
    const response = await fetch(`${this.baseUrl}/thirteenf/companies`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch 13F companies: ${response.statusText}`);
    }
    return response.json();
  }

  /** Fetch saved company selections from DB. Maps to GET /insider/thirteenf/selections. */
  async getThirteenFSelections(): Promise<ThirteenFSavedSelectionsResponse> {
    const response = await fetch(`${this.baseUrl}/thirteenf/selections`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch saved selections: ${response.statusText}`);
    }
    return response.json();
  }

  /** Save company selections to DB. Maps to PUT /insider/thirteenf/selections. */
  async saveThirteenFSelections(ciks: number[]): Promise<void> {
    const response = await fetch(`${this.baseUrl}/thirteenf/selections`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ciks }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to save selections: ${response.statusText}`);
    }
  }

  /** Fetch aggregated holdings across multiple companies. Maps to GET /insider/thirteenf/aggregate. */
  async getAggregateHoldings(ciks: number[]): Promise<AggregateHoldingsResponse> {
    const params = new URLSearchParams({ ciks: ciks.join(',') });
    const response = await fetch(`${this.baseUrl}/thirteenf/aggregate?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch aggregate holdings: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Fetch quarter-over-quarter holding comparison for a specific 13F-HR filing.
   * Maps to GET /insider/thirteenf/compare.
   */
  async getCompareHoldings(accessionNo: string): Promise<CompareHoldingsResponse> {
    const params = new URLSearchParams({ accession_no: accessionNo });
    const response = await fetch(`${this.baseUrl}/thirteenf/compare?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch compare holdings: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Fetch multi-period holding history for a specific 13F-HR filing.
   * Maps to GET /insider/thirteenf/history.
   */
  async getHoldingHistory(
    accessionNo: string,
    periods?: number
  ): Promise<HoldingHistoryResponse> {
    const params = new URLSearchParams({ accession_no: accessionNo });
    if (periods !== undefined) params.set('periods', String(periods));
    const response = await fetch(`${this.baseUrl}/thirteenf/history?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch holding history: ${response.statusText}`);
    }
    return response.json();
  }

  // -----------------------------------------------------------------------
  // Political & Policy
  // -----------------------------------------------------------------------

  /**
   * Fetch government contract awards from USA Spending API.
   * Maps to GET /insider/political/contracts.
   */
  async getGovContracts(companies: string[]): Promise<GovContractsResponse> {
    const params = new URLSearchParams({ companies: companies.join(',') });
    const response = await fetch(`${this.baseUrl}/political/contracts?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch gov contracts: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Fetch congressional stock trades from House Stock Watcher.
   * Maps to GET /insider/political/congress.
   */
  async getCongressTrades(ticker?: string): Promise<CongressTradesResponse> {
    const params = new URLSearchParams();
    if (ticker) params.set('ticker', ticker);
    const response = await fetch(`${this.baseUrl}/political/congress?${params.toString()}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch congress trades: ${response.statusText}`);
    }
    return response.json();
  }

  // -----------------------------------------------------------------------
  // Earnings Sentiment
  // -----------------------------------------------------------------------

  /**
   * Fetch LLM-powered earnings call transcript analysis with sentiment delta.
   * Maps to POST /insider/earnings/analysis.
   */
  async getEarningsAnalysis(ticker: string, modelName: string, modelProvider: string): Promise<EarningsAnalysisResponse> {
    const response = await fetch(`${this.baseUrl}/earnings/analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, model_name: modelName, model_provider: modelProvider }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch earnings analysis: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Fetch conviction signals for multiple tickers (earnings sentiment + insider activity).
   * Maps to POST /insider/earnings/conviction.
   */
  async getConvictionSignals(tickers: string[], modelName: string, modelProvider: string): Promise<ConvictionResponse> {
    const response = await fetch(`${this.baseUrl}/earnings/conviction`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tickers, model_name: modelName, model_provider: modelProvider }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `Failed to fetch conviction signals: ${response.statusText}`);
    }
    return response.json();
  }
}

export const insiderService = new InsiderService();
