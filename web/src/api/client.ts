/** Typed fetch wrappers for /api endpoints. */

export interface AnalystInfo {
  key: string;
  display_name: string;
  order: number;
}

export interface ModelInfo {
  display_name: string;
  model_name: string;
  provider: string;
}

export interface RunListItem {
  id: string;
  status: "running" | "done" | "error";
  kind: "analyze" | "backtest";
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  tickers: string[];
  model_name: string;
  model_provider: string;
}

export interface RunListResponse {
  items: RunListItem[];
  next_cursor: string | null;
}

export interface Decision {
  action: "buy" | "sell" | "short" | "cover" | "hold";
  quantity: number;
  confidence: number;
  reasoning: string | null;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchAnalysts(): Promise<AnalystInfo[]> {
  return apiFetch<AnalystInfo[]>("/api/analysts");
}

export async function fetchModels(): Promise<ModelInfo[]> {
  return apiFetch<ModelInfo[]>("/api/models");
}

export async function fetchRuns(limit = 20): Promise<RunListResponse> {
  return apiFetch<RunListResponse>(`/api/runs?limit=${limit}`);
}

export interface AnalyzeRequest {
  tickers: string[];
  selected_analysts: string[];
  model_name: string;
  model_provider: string;
  start_date?: string;
  end_date?: string;
  show_reasoning?: boolean;
}
