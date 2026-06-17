export interface Holding {
  id: number;
  portfolio_name: string;
  account_id: number | null;
  ticker: string;
  investment_name: string;
  quantity: number;
  buy_price: number;
  cost_basis: number | null;
  currency: string;
  sector: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface HoldingCreate {
  portfolio_name?: string;
  account_id?: number;
  ticker: string;
  investment_name: string;
  quantity: number;
  buy_price: number;
  cost_basis?: number;
  currency?: string;
  sector?: string;
}

export interface HoldingUpdate {
  portfolio_name?: string;
  account_id?: number;
  ticker?: string;
  investment_name?: string;
  quantity?: number;
  buy_price?: number;
  cost_basis?: number;
  currency?: string;
  sector?: string;
}

export interface DashboardHolding {
  id: number;
  portfolio_name: string;
  account_id: number | null;
  account_label: string | null;
  ticker: string;
  investment_name: string;
  quantity: number;
  buy_price: number;
  cost_basis: number;
  currency: string;
  sector: string | null;
  current_price: number | null;
  current_value: number | null;
  profit_loss: number | null;
  profit_loss_pct: number | null;
  rsi_14: number | null;
  sma_20: number | null;
  sma_50: number | null;
  trend: string | null;
  action_label: string;
  risk_score: number | null;
}

export interface AllocationItem {
  label: string;
  value: number;
  percentage: number;
}

export interface AccountSummaryItem {
  account_id: number;
  label: string;
  owner_name: string;
  total_cost: number;
  total_value: number;
  profit_loss: number;
  profit_loss_pct: number | null;
  holdings_count: number;
}

export interface DashboardResponse {
  holdings: DashboardHolding[];
  total_cost: number;
  total_value: number;
  total_profit_loss: number;
  total_profit_loss_pct: number | null;
  overall_risk_score: number | null;
  allocation_by_sector: AllocationItem[];
  allocation_by_account: AllocationItem[];
  account_summaries: AccountSummaryItem[];
}

export interface HoldingImportRequest {
  portfolio_name?: string;
  csv_text: string;
}

export interface HoldingImportResponse {
  imported: number;
  errors: string[];
}

export interface Account {
  id: number;
  owner_name: string;
  account_type: string;
  provider: string;
  label: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface AccountCreate {
  owner_name: string;
  account_type?: string;
  provider?: string;
  label?: string;
}

export interface PriceEstimate {
  estimated_next_price: number;
  expected_low: number;
  expected_high: number;
  estimate_confidence: 'Low' | 'Moderate' | 'High';
  estimate_reason: string;
}

export interface AnalysisResult {
  id: number;
  holding_id: number | null;
  watchlist_id: number | null;
  ticker: string;
  analysis_ticker: string;
  final_action: string;
  confidence: number;
  technical_summary: string | null;
  fundamental_summary: string | null;
  sentiment_summary: string | null;
  valuation_summary: string | null;
  risk_summary: string | null;
  portfolio_manager_summary: string | null;
  positive_factors: string[];
  risk_factors: string[];
  uncertainties: string[];
  price_estimate: PriceEstimate | null;
  created_at: string | null;
}

export type AnalysisMode = 'quick_scan' | 'standard' | 'deep_dive';

export interface AnalysisJob {
  job_id: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  job_type: string;
  total_tickers: number | null;
  completed_tickers: number | null;
  error_message: string | null;
  results: AnalysisResult[] | null;
  created_at: string | null;
  analysis_mode: AnalysisMode | null;
  model_name: string | null;
  agent_count: number | null;
  estimated_tokens: number | null;
  elapsed_seconds: number | null;
}

export interface WatchlistItem {
  id: number;
  ticker: string;
  investment_name: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface WatchlistCreate {
  ticker: string;
  investment_name?: string;
  notes?: string;
}
