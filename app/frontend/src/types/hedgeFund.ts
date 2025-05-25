export interface AgentInfo {
    name: string;
    description: string;
}

export interface HedgeFundRequest {
    tickers: string[];
    selected_agents: string[];
    initial_cash: number;
    margin_requirement: number;
    start_date?: string;
    end_date?: string;
    model_name: string;
    model_provider: string;
    show_reasoning: boolean;
}

export interface TradingDecision {
    ticker: string;
    action: 'BUY' | 'SELL' | 'HOLD';
    quantity?: number;
    price?: number;
    reasoning: string;
    confidence: number;
    timestamp: string;
}

export interface Position {
    ticker: string;
    quantity: number;
    average_price: number;
    current_price: number;
    market_value: number;
    unrealized_pnl: number;
    unrealized_pnl_percent: number;
}

export interface PortfolioSnapshot {
    cash: number;
    positions: { [ticker: string]: Position };
    total_value: number;
    timestamp: string;
}

export interface AnalystSignal {
    ticker: string;
    analyst: string;
    signal: 'BUY' | 'SELL' | 'HOLD';
    confidence: number;
    reasoning: string;
    timestamp: string;
}

export interface HedgeFundResponse {
    decisions: TradingDecision[];
    portfolio_snapshot: PortfolioSnapshot;
    analyst_signals: { [ticker: string]: AnalystSignal[] };
}

export interface ProgressUpdate {
    agent: string;
    ticker: string;
    status: string;
    analysis?: string;
    timestamp: string;
} 