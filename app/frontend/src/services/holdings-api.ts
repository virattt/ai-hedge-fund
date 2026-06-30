import type {
  Holding,
  HoldingCreate,
  HoldingUpdate,
  DashboardResponse,
  HoldingImportRequest,
  HoldingImportResponse,
  Account,
  AccountCreate,
  AnalysisJob,
  AnalysisResult,
  WatchlistItem,
  WatchlistCreate,
} from '@/types/holdings';
import { API_ROUTES, ApiError, fetchWithTimeout } from '@/services/api-routes';

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const apiKey = localStorage.getItem('app_api_key');
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }
  return headers;
}

async function apiRequest<T>(url: string, options: RequestInit = {}): Promise<T> {
  const res = await fetchWithTimeout(url, options);
  if (!res.ok) {
    throw new ApiError(`Request failed: ${res.status} ${res.statusText}`, res.status, url);
  }
  return res.json();
}

export const holdingsApi = {
  // Holdings
  async listHoldings(portfolio?: string, accountId?: number): Promise<Holding[]> {
    const params = new URLSearchParams();
    if (portfolio) params.set('portfolio', portfolio);
    if (accountId) params.set('account_id', String(accountId));
    const qs = params.toString() ? `?${params}` : '';
    return apiRequest<Holding[]>(`${API_ROUTES.holdings.list}${qs}`, { headers: getHeaders() });
  },

  async listPortfolios(): Promise<string[]> {
    return apiRequest<string[]>(API_ROUTES.holdings.portfolios, { headers: getHeaders() });
  },

  async getHolding(id: number): Promise<Holding> {
    return apiRequest<Holding>(API_ROUTES.holdings.detail(id), { headers: getHeaders() });
  },

  async createHolding(data: HoldingCreate): Promise<Holding> {
    return apiRequest<Holding>(API_ROUTES.holdings.list, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
  },

  async updateHolding(id: number, data: HoldingUpdate): Promise<Holding> {
    return apiRequest<Holding>(API_ROUTES.holdings.detail(id), {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
  },

  async deleteHolding(id: number): Promise<void> {
    await fetchWithTimeout(API_ROUTES.holdings.detail(id), {
      method: 'DELETE',
      headers: getHeaders(),
    });
  },

  async importCsv(data: HoldingImportRequest): Promise<HoldingImportResponse> {
    return apiRequest<HoldingImportResponse>(API_ROUTES.holdings.importCsv, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
  },

  // Dashboard
  async getDashboard(portfolio?: string, accountId?: number): Promise<DashboardResponse> {
    const params = new URLSearchParams();
    if (portfolio) params.set('portfolio', portfolio);
    if (accountId) params.set('account_id', String(accountId));
    const qs = params.toString() ? `?${params}` : '';
    return apiRequest<DashboardResponse>(`${API_ROUTES.dashboard}${qs}`, { headers: getHeaders() });
  },

  // Accounts
  async listAccounts(): Promise<Account[]> {
    return apiRequest<Account[]>(API_ROUTES.accounts.list, { headers: getHeaders() });
  },

  async createAccount(data: AccountCreate): Promise<Account> {
    return apiRequest<Account>(API_ROUTES.accounts.list, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
  },

  async deleteAccount(id: number): Promise<void> {
    await fetchWithTimeout(API_ROUTES.accounts.detail(id), {
      method: 'DELETE',
      headers: getHeaders(),
    });
  },

  // Export
  getExportCsvUrl(portfolio?: string, accountId?: number): string {
    const params = new URLSearchParams();
    if (portfolio) params.set('portfolio', portfolio);
    if (accountId) params.set('account_id', String(accountId));
    const qs = params.toString() ? `?${params}` : '';
    return `${API_ROUTES.export.csv}${qs}`;
  },

  // Portfolio Analysis
  async analyzePortfolio(holdingIds?: number[], modelName?: string, modelProvider?: string, analysisMode?: string): Promise<AnalysisJob> {
    const body: Record<string, unknown> = {};
    if (holdingIds) body.holding_ids = holdingIds;
    if (modelName) body.model_name = modelName;
    if (modelProvider) body.model_provider = modelProvider;
    if (analysisMode) body.analysis_mode = analysisMode;
    return apiRequest<AnalysisJob>(API_ROUTES.portfolio.analyze, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(body),
    });
  },

  async getAnalysisJob(jobId: number): Promise<AnalysisJob> {
    return apiRequest<AnalysisJob>(API_ROUTES.portfolio.job(jobId), { headers: getHeaders() });
  },

  async getLatestAnalysis(): Promise<AnalysisResult[]> {
    return apiRequest<AnalysisResult[]>(API_ROUTES.portfolio.latestAnalysis, { headers: getHeaders() });
  },

  // Watchlist
  async listWatchlist(): Promise<WatchlistItem[]> {
    return apiRequest<WatchlistItem[]>(API_ROUTES.watchlist.list, { headers: getHeaders() });
  },

  async addToWatchlist(data: WatchlistCreate): Promise<WatchlistItem> {
    return apiRequest<WatchlistItem>(API_ROUTES.watchlist.list, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
  },

  async removeFromWatchlist(id: number): Promise<void> {
    await fetchWithTimeout(API_ROUTES.watchlist.detail(id), {
      method: 'DELETE',
      headers: getHeaders(),
    });
  },

  async analyzeWatchlist(watchlistIds?: number[], analysisMode?: string): Promise<AnalysisJob> {
    const body: Record<string, unknown> = {};
    if (watchlistIds) body.watchlist_ids = watchlistIds;
    if (analysisMode) body.analysis_mode = analysisMode;
    return apiRequest<AnalysisJob>(API_ROUTES.watchlist.analyze, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(body),
    });
  },

  async getLatestWatchlistAnalysis(): Promise<AnalysisResult[]> {
    return apiRequest<AnalysisResult[]>(API_ROUTES.watchlist.latestAnalysis, { headers: getHeaders() });
  },
};
