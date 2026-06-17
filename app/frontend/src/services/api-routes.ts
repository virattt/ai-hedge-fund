const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export { API_BASE_URL };

export const API_ROUTES = {
  holdings: {
    list: `${API_BASE_URL}/holdings`,
    portfolios: `${API_BASE_URL}/holdings/portfolios`,
    detail: (id: number) => `${API_BASE_URL}/holdings/${id}`,
    importCsv: `${API_BASE_URL}/holdings/import-csv`,
  },
  dashboard: `${API_BASE_URL}/dashboard`,
  accounts: {
    list: `${API_BASE_URL}/accounts`,
    detail: (id: number) => `${API_BASE_URL}/accounts/${id}`,
  },
  export: {
    csv: `${API_BASE_URL}/export/csv`,
  },
  portfolio: {
    analyze: `${API_BASE_URL}/portfolio/analyze`,
    job: (jobId: number) => `${API_BASE_URL}/portfolio/analyze/${jobId}`,
    latestAnalysis: `${API_BASE_URL}/portfolio/analysis/latest`,
  },
  watchlist: {
    list: `${API_BASE_URL}/watchlist`,
    detail: (id: number) => `${API_BASE_URL}/watchlist/${id}`,
    analyze: `${API_BASE_URL}/watchlist/analyze`,
    latestAnalysis: `${API_BASE_URL}/watchlist/analysis/latest`,
  },
  hedgeFund: {
    agents: `${API_BASE_URL}/hedge-fund/agents`,
    run: `${API_BASE_URL}/hedge-fund/run`,
    backtest: `${API_BASE_URL}/hedge-fund/backtest`,
  },
  languageModels: `${API_BASE_URL}/language-models/`,
  storage: {
    saveJson: `${API_BASE_URL}/storage/save-json`,
  },
  apiKeys: `${API_BASE_URL}/api-keys`,
  flows: {
    list: `${API_BASE_URL}/flows/`,
    detail: (id: string) => `${API_BASE_URL}/flows/${id}`,
    duplicate: (id: string, newName?: string) =>
      `${API_BASE_URL}/flows/${id}/duplicate${newName ? `?new_name=${encodeURIComponent(newName)}` : ''}`,
  },
  ollama: {
    status: `${API_BASE_URL}/ollama/status`,
    start: `${API_BASE_URL}/ollama/start`,
    stop: `${API_BASE_URL}/ollama/stop`,
    recommendedModels: `${API_BASE_URL}/ollama/models/recommended`,
    downloadProgress: `${API_BASE_URL}/ollama/models/download/progress`,
    downloadModel: (name: string) => `${API_BASE_URL}/ollama/models/download/${encodeURIComponent(name)}`,
    deleteModel: (name: string) => `${API_BASE_URL}/ollama/models/${encodeURIComponent(name)}`,
    activeDownloads: `${API_BASE_URL}/ollama/models/downloads/active`,
  },
  languageModelProviders: `${API_BASE_URL}/language-models/providers`,
} as const;

const DEFAULT_TIMEOUT_MS = 15000;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public url: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class ApiTimeoutError extends Error {
  constructor(public url: string) {
    super(`Request timed out: ${url}`);
    this.name = 'ApiTimeoutError';
  }
}

export async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return res;
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new ApiTimeoutError(url);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}
