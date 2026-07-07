// Shared types for API requests and responses.
// Values must match the backend ModelProvider enum (src/llm/models.py); the runtime
// model list is fetched from the backend, so this is a type-safety mirror only.
export enum ModelProvider {
  ALIBABA = 'Alibaba',
  ANTHROPIC = 'Anthropic',
  DEEPSEEK = 'DeepSeek',
  GOOGLE = 'Google',
  GROQ = 'Groq',
  KIMI = 'Kimi',
  META = 'Meta',
  MISTRAL = 'Mistral',
  OPENAI = 'OpenAI',
  OLLAMA = 'Ollama',
  OPENROUTER = 'OpenRouter',
  GIGACHAT = 'GigaChat',
  AZURE_OPENAI = 'Azure OpenAI',
  XAI = 'xAI',
}

export interface AgentModelConfig {
  agent_id: string;
  model_name?: string;
  model_provider?: ModelProvider;
}

export interface GraphNode {
  id: string;
  type?: string;
  data?: any;
  position?: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  data?: any;
}

export interface PortfolioPosition {
  ticker: string;
  quantity: number;
  trade_price: number;
}

// Base interface for shared fields between HedgeFundRequest and BacktestRequest
export interface BaseHedgeFundRequest {
  tickers: string[];
  graph_nodes: GraphNode[];
  graph_edges: GraphEdge[];
  agent_models?: AgentModelConfig[];
  model_name?: string;
  model_provider?: ModelProvider;
  margin_requirement?: number;
  portfolio_positions?: PortfolioPosition[];
}

export interface HedgeFundRequest extends BaseHedgeFundRequest {
  end_date?: string;
  start_date?: string;
  initial_cash?: number;
}

export interface BacktestRequest extends BaseHedgeFundRequest {
  start_date: string;
  end_date: string;
  initial_capital?: number;
}

export interface BacktestDayResult {
  date: string;
  portfolio_value: number;
  cash: number;
  decisions: Record<string, any>;
  executed_trades: Record<string, number>;
  analyst_signals: Record<string, any>;
  current_prices: Record<string, number>;
  long_exposure: number;
  short_exposure: number;
  gross_exposure: number;
  net_exposure: number;
  long_short_ratio: number | null;
}

export interface BacktestPerformanceMetrics {
  sharpe_ratio?: number;
  sortino_ratio?: number;
  max_drawdown?: number;
  max_drawdown_date?: string;
  long_short_ratio?: number;
  gross_exposure?: number;
  net_exposure?: number;
} 