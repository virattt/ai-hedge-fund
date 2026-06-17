import { ActionBadge } from '@/components/holdings/ActionBadge';
import type { AnalysisResult, DashboardHolding, PriceEstimate } from '@/types/holdings';
import { Trash2, ChevronDown, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Fragment, useState } from 'react';

interface HoldingsTableProps {
  holdings: DashboardHolding[];
  analysisResults?: Record<number, AnalysisResult>;
  onDelete?: (id: number) => void;
}

function formatNum(val: number | null, decimals = 2): string {
  if (val === null || val === undefined) return '—';
  return val.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function TrendIndicator({ trend }: { trend: string | null }) {
  if (!trend) return <span className="text-muted-foreground">—</span>;
  const colors: Record<string, string> = {
    up: 'text-green-700 dark:text-green-400',
    down: 'text-red-700 dark:text-red-400',
    sideways: 'text-amber-700 dark:text-amber-400',
  };
  const arrows: Record<string, string> = { up: '▲', down: '▼', sideways: '►' };
  return <span className={colors[trend] || ''}>{arrows[trend] || trend}</span>;
}

function RiskBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted-foreground">—</span>;
  const getColor = (s: number) => {
    if (s <= 3) return 'bg-green-100 text-green-800 border-green-300 dark:bg-green-950 dark:text-green-200 dark:border-green-700';
    if (s <= 6) return 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-200 dark:border-amber-700';
    return 'bg-red-100 text-red-800 border-red-300 dark:bg-red-950 dark:text-red-200 dark:border-red-700';
  };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium border ${getColor(score)}`}>
      {score}
    </span>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number | undefined }) {
  if (confidence === undefined || confidence === null) return <span className="text-muted-foreground">—</span>;
  const getColor = (c: number) => {
    if (c >= 70) return 'text-green-700 dark:text-green-400';
    if (c >= 50) return 'text-amber-700 dark:text-amber-400';
    return 'text-muted-foreground';
  };
  return <span className={`text-xs font-medium ${getColor(confidence)}`}>{confidence.toFixed(0)}%</span>;
}

function PriceEstimateCell({ estimate }: { estimate: PriceEstimate | null | undefined }) {
  if (!estimate) return <span className="text-muted-foreground text-xs">—</span>;

  const confColor = {
    'High': 'text-green-700 dark:text-green-400',
    'Moderate': 'text-amber-700 dark:text-amber-400',
    'Low': 'text-muted-foreground',
  }[estimate.estimate_confidence] || 'text-muted-foreground';

  return (
    <div className="text-xs leading-tight">
      <div className="font-medium">{formatNum(estimate.estimated_next_price)}</div>
      <div className={`text-[10px] ${confColor}`}>
        {formatNum(estimate.expected_low)}–{formatNum(estimate.expected_high)}
      </div>
    </div>
  );
}

function parseSummary(summary: string | null): Record<string, unknown> | null {
  if (!summary) return null;
  try {
    return JSON.parse(summary);
  } catch {
    return null;
  }
}

function AnalysisExpandedRow({ analysis }: { analysis: AnalysisResult }) {
  return (
    <div className="px-4 sm:px-6 py-4 space-y-4 text-xs">
      {/* Portfolio Manager Summary — lead with the synthesis */}
      {analysis.portfolio_manager_summary && (
        <div className="pb-3 border-b border-border/40">
          <h4 className="text-xs font-bold uppercase tracking-wide text-foreground/60 mb-1.5">Synthesis</h4>
          <p className="text-sm text-foreground/90 leading-relaxed">{analysis.portfolio_manager_summary}</p>
        </div>
      )}

      {/* Factors */}
      {(analysis.positive_factors.length > 0 || analysis.risk_factors.length > 0 || analysis.uncertainties.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 pb-3 border-b border-border/40">
          {analysis.positive_factors.length > 0 && (
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wide text-green-700 dark:text-green-400 mb-1.5">Positive Factors</h4>
              <ul className="space-y-1 text-foreground/80">
                {analysis.positive_factors.map((f, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="text-green-600 dark:text-green-400 mt-0.5 shrink-0">+</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {analysis.risk_factors.length > 0 && (
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wide text-red-700 dark:text-red-400 mb-1.5">Risk Factors</h4>
              <ul className="space-y-1 text-foreground/80">
                {analysis.risk_factors.map((f, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="text-red-600 dark:text-red-400 mt-0.5 shrink-0">!</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {analysis.uncertainties.length > 0 && (
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wide text-amber-700 dark:text-amber-400 mb-1.5">Uncertainties</h4>
              <ul className="space-y-1 text-foreground/80">
                {analysis.uncertainties.map((f, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="text-amber-600 dark:text-amber-400 mt-0.5 shrink-0">?</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Agent Summaries — each in its own block with clear separation */}
      <div className="space-y-3 pb-3 border-b border-border/40">
        <h4 className="text-xs font-bold uppercase tracking-wide text-foreground/60">Analysis Detail</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-3">
          <AgentSummaryCard title="Technical" summary={analysis.technical_summary} />
          <AgentSummaryCard title="Fundamental" summary={analysis.fundamental_summary} />
          <AgentSummaryCard title="Sentiment" summary={analysis.sentiment_summary} />
          <AgentSummaryCard title="Valuation" summary={analysis.valuation_summary} />
          <AgentSummaryCard title="Risk" summary={analysis.risk_summary} />
        </div>
      </div>

      {/* Experimental Price Estimate */}
      {analysis.price_estimate && (
        <div className="pb-3 border-b border-border/40">
          <div className="flex items-center gap-2 mb-2">
            <h4 className="text-xs font-bold uppercase tracking-wide text-foreground/60">Price Estimate</h4>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200 border border-amber-300 dark:border-amber-700">
              EXPERIMENTAL
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <div className="text-muted-foreground">Estimate</div>
              <div className="font-medium text-sm">{formatNum(analysis.price_estimate.estimated_next_price)}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Range</div>
              <div className="font-medium">{formatNum(analysis.price_estimate.expected_low)} – {formatNum(analysis.price_estimate.expected_high)}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Confidence</div>
              <div className={`font-medium ${
                analysis.price_estimate.estimate_confidence === 'High' ? 'text-green-700 dark:text-green-400' :
                analysis.price_estimate.estimate_confidence === 'Moderate' ? 'text-amber-700 dark:text-amber-400' :
                'text-muted-foreground'
              }`}>{analysis.price_estimate.estimate_confidence}</div>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <div className="text-muted-foreground">Basis</div>
              <div className="text-foreground/80">{analysis.price_estimate.estimate_reason}</div>
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground/60 mt-2">
            Experimental estimate based on momentum, volatility, sentiment, and agent consensus. Not financial advice.
          </p>
        </div>
      )}

      <div className="text-muted-foreground/50 text-[10px] flex flex-wrap gap-x-2">
        <span>Analyzed: {analysis.created_at ? new Date(analysis.created_at).toLocaleString() : 'Unknown'}</span>
        <span>|</span>
        <span>Ticker: {analysis.analysis_ticker}</span>
        <span>|</span>
        <span>Educational only — not financial advice</span>
      </div>
    </div>
  );
}

function formatJsonToReadable(data: Record<string, unknown>, depth = 0): string {
  if (depth > 2) return JSON.stringify(data).slice(0, 100);
  const parts: string[] = [];
  for (const [key, value] of Object.entries(data)) {
    const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    if (value === null || value === undefined) continue;
    if (typeof value === 'object' && !Array.isArray(value)) {
      const nested = formatJsonToReadable(value as Record<string, unknown>, depth + 1);
      if (nested) parts.push(`${label}: ${nested}`);
    } else if (typeof value === 'number') {
      const formatted = Math.abs(value) < 1 ? `${(value * 100).toFixed(1)}%` :
        Math.abs(value) > 1000000 ? `$${(value / 1e6).toFixed(1)}M` :
        value.toLocaleString(undefined, { maximumFractionDigits: 2 });
      parts.push(`${label}: ${formatted}`);
    } else if (typeof value === 'string' && value.length > 0) {
      parts.push(`${label}: ${value}`);
    }
  }
  return parts.slice(0, 6).join(' | ');
}

function AgentSummaryCard({ title, summary }: { title: string; summary: string | null }) {
  if (!summary) return null;

  const parsed = parseSummary(summary);

  const signalColors: Record<string, string> = {
    bullish: 'text-green-700 dark:text-green-400',
    bearish: 'text-red-700 dark:text-red-400',
    neutral: 'text-amber-700 dark:text-amber-400',
  };

  if (!parsed) {
    return (
      <div className="min-w-0">
        <div className="font-semibold text-foreground/80 text-[11px] mb-0.5">{title}</div>
        <p className="text-foreground/70 leading-relaxed break-words">{summary}</p>
      </div>
    );
  }

  const signal = parsed.signal as string | undefined;
  const readable = formatJsonToReadable(parsed);

  return (
    <div className="min-w-0">
      <div className="font-semibold text-foreground/80 text-[11px] mb-0.5">{title}</div>
      <div className="text-foreground/70 break-words">
        {signal && (
          <span className={`font-medium ${signalColors[signal] || ''}`}>{signal}</span>
        )}
        {signal && readable && ' — '}
        {!signal && readable && <span>{readable}</span>}
        {signal && readable && <span className="text-[11px]">{readable}</span>}
      </div>
    </div>
  );
}

export function HoldingsTable({ holdings, analysisResults, onDelete }: HoldingsTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  if (holdings.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No holdings yet. Add a holding or import from CSV.
      </div>
    );
  }

  const hasAccounts = holdings.some(h => h.account_label);
  const hasAnalysis = analysisResults && Object.keys(analysisResults).length > 0;

  const toggleRow = (id: number) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b-2 border-border bg-muted/30 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
            {hasAnalysis && <th className="py-2 px-1 w-14"></th>}
            {hasAccounts && <th className="py-2 px-2">Account</th>}
            <th className="py-2 px-2">Ticker</th>
            <th className="py-2 px-2">Investment</th>
            <th className="py-2 px-2 text-right">Qty</th>
            <th className="py-2 px-2 text-right">Buy Price</th>
            <th className="py-2 px-2 text-right">Current</th>
            <th className="py-2 px-2 text-right">Value</th>
            <th className="py-2 px-2 text-right">P&L</th>
            <th className="py-2 px-2 text-right">P&L %</th>
            <th className="py-2 px-2 text-center">Risk</th>
            <th className="py-2 px-2 text-center">Trend</th>
            <th className="py-2 px-2 text-center">Action</th>
            {hasAnalysis && <th className="py-2 px-2 text-center">Conf.</th>}
            {hasAnalysis && <th className="py-2 px-2 text-right">Next Est.</th>}
            <th className="py-2 px-2"></th>
          </tr>
        </thead>
        <tbody>
          {holdings.map(h => {
            const analysis = analysisResults?.[h.id];
            const isExpanded = expandedRows.has(h.id);
            const displayAction = analysis?.final_action || h.action_label;

            return (
              <Fragment key={h.id}>
                <tr className={`border-b border-border/60 hover:bg-muted/40 transition-colors ${isExpanded ? 'bg-muted/20 border-b-0' : ''}`}>
                  {hasAnalysis && (
                    <td className="py-2 px-1">
                      {analysis && (
                        <button
                          onClick={() => toggleRow(h.id)}
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-semibold transition-all ${
                            isExpanded
                              ? 'bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900 shadow-sm'
                              : 'bg-muted/60 text-foreground/70 hover:bg-muted hover:text-foreground border border-border/50'
                          }`}
                        >
                          {isExpanded ? <ChevronDown size={12} /> : <FileText size={12} />}
                          <span className="hidden sm:inline">{isExpanded ? 'Close' : 'Details'}</span>
                        </button>
                      )}
                    </td>
                  )}
                  {hasAccounts && (
                    <td className="py-2 px-2 text-xs text-muted-foreground max-w-[120px] truncate" title={h.account_label || ''}>
                      {h.account_label || '—'}
                    </td>
                  )}
                  <td className="py-2 px-2 font-mono font-medium">{h.ticker}</td>
                  <td className="py-2 px-2 max-w-[200px] truncate" title={h.investment_name}>{h.investment_name}</td>
                  <td className="py-2 px-2 text-right">{formatNum(h.quantity)}</td>
                  <td className="py-2 px-2 text-right">{formatNum(h.buy_price)}</td>
                  <td className="py-2 px-2 text-right">{formatNum(h.current_price)}</td>
                  <td className="py-2 px-2 text-right">{formatNum(h.current_value)}</td>
                  <td className={`py-2 px-2 text-right ${h.profit_loss !== null && h.profit_loss >= 0 ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
                    {formatNum(h.profit_loss)}
                  </td>
                  <td className={`py-2 px-2 text-right ${h.profit_loss_pct !== null && h.profit_loss_pct >= 0 ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
                    {h.profit_loss_pct !== null ? `${formatNum(h.profit_loss_pct)}%` : '—'}
                  </td>
                  <td className="py-2 px-2 text-center"><RiskBadge score={h.risk_score} /></td>
                  <td className="py-2 px-2 text-center"><TrendIndicator trend={h.trend} /></td>
                  <td className="py-2 px-2 text-center"><ActionBadge label={displayAction} /></td>
                  {hasAnalysis && (
                    <td className="py-2 px-2 text-center">
                      <ConfidenceBadge confidence={analysis?.confidence} />
                    </td>
                  )}
                  {hasAnalysis && (
                    <td className="py-2 px-2 text-right">
                      <PriceEstimateCell estimate={analysis?.price_estimate} />
                    </td>
                  )}
                  <td className="py-2 px-2">
                    {onDelete && (
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-muted-foreground hover:text-red-400" onClick={() => onDelete(h.id)}>
                        <Trash2 size={14} />
                      </Button>
                    )}
                  </td>
                </tr>
                {isExpanded && analysis && (
                  <tr className="border-b-2 border-primary/20">
                    <td colSpan={hasAccounts ? (hasAnalysis ? 16 : 13) : (hasAnalysis ? 15 : 12)} className="p-0">
                      <div className="border-t-2 border-primary/20 bg-muted/40">
                        <AnalysisExpandedRow analysis={analysis} />
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
