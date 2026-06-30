import { CsvImporter } from '@/components/holdings/CsvImporter';
import { HoldingForm } from '@/components/holdings/HoldingForm';
import { HoldingsTable } from '@/components/holdings/HoldingsTable';
import { Button } from '@/components/ui/button';
import { holdingsApi } from '@/services/holdings-api';
import type { Account, AnalysisJob, AnalysisMode, AnalysisResult, DashboardHolding, DashboardResponse, HoldingCreate, AllocationItem, AccountSummaryItem, WatchlistItem } from '@/types/holdings';
import { Plus, Upload, RefreshCw, Download, Shield, Brain, Eye, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

type View = 'table' | 'add' | 'import' | 'watchlist';

export function Dashboard() {
  const [view, setView] = useState<View>('table');
  const [holdings, setHoldings] = useState<DashboardHolding[]>([]);
  const [summary, setSummary] = useState<Omit<DashboardResponse, 'holdings'> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useDashboard, setUseDashboard] = useState(true);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | undefined>(undefined);

  // Analysis state
  const [analysisResults, setAnalysisResults] = useState<Record<number, AnalysisResult>>({});
  const [analysisJob, setAnalysisJob] = useState<AnalysisJob | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Analysis mode & limits
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>('quick_scan');
  const [analysisLimits, setAnalysisLimits] = useState<{
    deep_dive_enabled?: boolean;
    standard_used_today?: number;
    standard_daily_limit?: number;
    deep_dive_used_today?: number;
    deep_dive_daily_limit?: number;
  }>({});

  // Watchlist state
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [watchlistTicker, setWatchlistTicker] = useState('');

  const fetchAccounts = useCallback(async () => {
    try {
      const accts = await holdingsApi.listAccounts();
      setAccounts(accts);
    } catch {
      // Accounts endpoint may not exist yet — non-critical
    }
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (useDashboard) {
        const data = await holdingsApi.getDashboard(undefined, selectedAccountId);
        setHoldings(data.holdings);
        setSummary({
          total_cost: data.total_cost,
          total_value: data.total_value,
          total_profit_loss: data.total_profit_loss,
          total_profit_loss_pct: data.total_profit_loss_pct,
          overall_risk_score: data.overall_risk_score,
          allocation_by_sector: data.allocation_by_sector || [],
          allocation_by_account: data.allocation_by_account || [],
          account_summaries: data.account_summaries || [],
        });
      } else {
        const raw = await holdingsApi.listHoldings(undefined, selectedAccountId);
        const mapped: DashboardHolding[] = raw.map(h => ({
          ...h,
          account_label: null,
          cost_basis: h.cost_basis || h.quantity * h.buy_price,
          current_price: null,
          current_value: null,
          profit_loss: null,
          profit_loss_pct: null,
          rsi_14: null,
          sma_20: null,
          sma_50: null,
          trend: null,
          action_label: 'WATCH',
          risk_score: null,
        }));
        setHoldings(mapped);
        setSummary(null);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load data');
      if (useDashboard) {
        setUseDashboard(false);
      }
    } finally {
      setLoading(false);
    }
  }, [useDashboard, selectedAccountId]);

  const fetchLatestAnalysis = useCallback(async () => {
    try {
      const results = await holdingsApi.getLatestAnalysis();
      const map: Record<number, AnalysisResult> = {};
      for (const r of results) {
        if (r.holding_id) map[r.holding_id] = r;
      }
      setAnalysisResults(map);
    } catch {
      // Non-critical — analysis may not have been run yet
    }
  }, []);

  const fetchWatchlist = useCallback(async () => {
    try {
      const items = await holdingsApi.listWatchlist();
      setWatchlist(items);
    } catch {
      // Non-critical
    }
  }, []);

  const fetchLimits = useCallback(async () => {
    try {
      const key = localStorage.getItem('app_api_key');
      const headers: Record<string, string> = {};
      if (key) headers['X-API-Key'] = key;
      const resp = await fetch('/portfolio/analysis/limits', { headers });
      if (resp.ok) setAnalysisLimits(await resp.json());
    } catch { /* non-critical */ }
  }, []);

  useEffect(() => { fetchAccounts(); }, [fetchAccounts]);
  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { fetchLatestAnalysis(); }, [fetchLatestAnalysis]);
  useEffect(() => { fetchWatchlist(); }, [fetchWatchlist]);
  useEffect(() => { fetchLimits(); }, [fetchLimits]);

  // Cleanup poll on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleAdd = async (data: HoldingCreate) => {
    try {
      await holdingsApi.createHolding({ ...data, account_id: selectedAccountId });
      setView('table');
      fetchData();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleImport = async (csvText: string, portfolioName: string) => {
    try {
      const result = await holdingsApi.importCsv({ csv_text: csvText, portfolio_name: portfolioName });
      if (result.errors.length > 0) {
        setError(`Imported ${result.imported} holdings. Errors: ${result.errors.join('; ')}`);
      }
      setView('table');
      fetchData();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await holdingsApi.deleteHolding(id);
      fetchData();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleExport = () => {
    const url = holdingsApi.getExportCsvUrl(undefined, selectedAccountId);
    window.open(url, '_blank');
  };

  const handleAnalyze = async () => {
    if (analysisMode === 'deep_dive') {
      if (!analysisLimits.deep_dive_enabled) {
        setError('Deep Dive is not enabled. Set DEEP_DIVE_ENABLED=true in environment.');
        return;
      }
      const confirmed = window.confirm(
        'Deep Dive is slower and uses more AI tokens. Use for selected stocks only.\n\n' +
        `Daily limit: ${analysisLimits.deep_dive_daily_limit ?? 5} runs. ` +
        `Used today: ${analysisLimits.deep_dive_used_today ?? 0}.\n\nContinue?`
      );
      if (!confirmed) return;
    }

    if (analysisMode === 'standard') {
      const confirmed = window.confirm(
        `Standard analysis uses AI tokens (limited to ${analysisLimits.standard_daily_limit ?? 10} runs/day).\n\nQuick Scan is free and instant. Continue with Standard?`
      );
      if (!confirmed) return;
    }

    try {
      setAnalyzing(true);
      setError(null);
      const job = await holdingsApi.analyzePortfolio(undefined, undefined, undefined, analysisMode);
      setAnalysisJob(job);

      // Start polling
      pollRef.current = setInterval(async () => {
        try {
          const updated = await holdingsApi.getAnalysisJob(job.job_id);
          setAnalysisJob(updated);
          if (updated.status === 'completed' || updated.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setAnalyzing(false);
            if (updated.status === 'completed') {
              fetchLatestAnalysis();
            } else if (updated.error_message) {
              setError(`Analysis failed: ${updated.error_message}`);
            }
          }
        } catch {
          // Ignore poll errors
        }
      }, 3000);
    } catch (e: any) {
      setError(e.message);
      setAnalyzing(false);
    }
  };

  const handleAddWatchlist = async () => {
    if (!watchlistTicker.trim()) return;
    try {
      await holdingsApi.addToWatchlist({ ticker: watchlistTicker.trim() });
      setWatchlistTicker('');
      fetchWatchlist();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleRemoveWatchlist = async (id: number) => {
    try {
      await holdingsApi.removeFromWatchlist(id);
      fetchWatchlist();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleAnalyzeWatchlist = async () => {
    try {
      setAnalyzing(true);
      setError(null);
      const job = await holdingsApi.analyzeWatchlist(undefined, analysisMode);
      setAnalysisJob(job);

      pollRef.current = setInterval(async () => {
        try {
          const updated = await holdingsApi.getAnalysisJob(job.job_id);
          setAnalysisJob(updated);
          if (updated.status === 'completed' || updated.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setAnalyzing(false);
            if (updated.status === 'failed' && updated.error_message) {
              setError(`Watchlist analysis failed: ${updated.error_message}`);
            }
          }
        } catch {
          // Ignore poll errors
        }
      }, 3000);
    } catch (e: any) {
      setError(e.message);
      setAnalyzing(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6 bg-background">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">My Portfolio</h1>
            <p className="text-xs text-muted-foreground mt-1">
              Educational analysis only — not financial advice
            </p>
          </div>
          <div className="flex gap-2 items-center flex-wrap">
            {/* Account filter */}
            {accounts.length > 0 && (
              <select
                className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                value={selectedAccountId ?? ''}
                onChange={e => setSelectedAccountId(e.target.value ? Number(e.target.value) : undefined)}
              >
                <option value="">All Accounts</option>
                {accounts.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.label || `${a.owner_name} ${a.account_type}`}
                  </option>
                ))}
              </select>
            )}
            <Button variant="ghost" size="sm" onClick={fetchData} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </Button>
            <Button variant="ghost" size="sm" onClick={handleExport} title="Export CSV">
              <Download size={14} />
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setView('import')}>
              <Upload size={14} className="mr-1" /> Import CSV
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setView('watchlist')}>
              <Eye size={14} className="mr-1" /> Watchlist
            </Button>
            <Button size="sm" onClick={() => setView('add')}>
              <Plus size={14} className="mr-1" /> Add Holding
            </Button>
            <div className="flex items-center gap-1">
              <select
                value={analysisMode}
                onChange={(e) => setAnalysisMode(e.target.value as AnalysisMode)}
                disabled={analyzing}
                className="h-8 rounded-md border border-border bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                title={analysisMode === 'quick_scan' ? 'Free — uses market data only' : analysisMode === 'standard' ? `Uses AI (${analysisLimits.standard_used_today ?? 0}/${analysisLimits.standard_daily_limit ?? 10} today)` : 'Full multi-agent analysis'}
              >
                <option value="quick_scan">Quick Scan (free)</option>
                <option value="standard">{`Standard (${analysisLimits.standard_used_today ?? 0}/${analysisLimits.standard_daily_limit ?? 10})`}</option>
                <option value="deep_dive" disabled={!analysisLimits.deep_dive_enabled}>
                  {analysisLimits.deep_dive_enabled ? `Deep Dive (${analysisLimits.deep_dive_used_today ?? 0}/${analysisLimits.deep_dive_daily_limit ?? 5})` : 'Deep Dive (not enabled)'}
                </option>
              </select>
              <Button
                size="sm"
                variant="default"
                onClick={handleAnalyze}
                disabled={analyzing || holdings.length === 0}
                className="bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 dark:text-slate-900"
              >
                <Brain size={14} className={`mr-1 ${analyzing ? 'animate-pulse' : ''}`} />
                {analyzing ? 'Analyzing...' : 'Analyze'}
              </Button>
            </div>
          </div>
        </div>

        {/* Analysis Status Banner */}
        {analysisJob && analyzing && (
          <div className="rounded border-l-4 border-l-blue-500 border border-border bg-card px-4 py-2 text-sm text-foreground flex items-center gap-2">
            <Brain size={14} className="animate-pulse text-blue-500" />
            Running {analysisJob.analysis_mode === 'quick_scan' ? 'quick scan' : analysisJob.analysis_mode === 'deep_dive' ? 'deep analysis' : 'standard analysis'} — {analysisJob.status === 'running' ? 'processing...' : 'starting...'}
            {analysisJob.total_tickers && ` (${analysisJob.completed_tickers || 0}/${analysisJob.total_tickers} tickers)`}
          </div>
        )}

        {/* Summary Cards */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <SummaryCard label="Total Cost" value={`£${formatLarge(summary.total_cost)}`} />
            <SummaryCard label="Current Value" value={`£${formatLarge(summary.total_value)}`} />
            <SummaryCard
              label="Profit / Loss"
              value={`£${formatLarge(summary.total_profit_loss)}`}
              className={summary.total_profit_loss >= 0 ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}
            />
            <SummaryCard
              label="Return"
              value={summary.total_profit_loss_pct !== null ? `${summary.total_profit_loss_pct.toFixed(2)}%` : '—'}
              className={summary.total_profit_loss_pct !== null && summary.total_profit_loss_pct >= 0 ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}
            />
            <RiskCard score={summary.overall_risk_score} />
          </div>
        )}

        {/* Account Summaries */}
        {summary && summary.account_summaries.length > 0 && !selectedAccountId && (
          <div className="space-y-2">
            <h2 className="text-sm font-medium text-muted-foreground">By Account</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {summary.account_summaries.map(a => (
                <AccountCard key={a.account_id} account={a} onSelect={() => setSelectedAccountId(a.account_id)} />
              ))}
            </div>
          </div>
        )}

        {/* Allocation Breakdown */}
        {summary && summary.allocation_by_sector.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <AllocationPanel title="Sector Allocation" items={summary.allocation_by_sector} />
            {summary.allocation_by_account.length > 0 && (
              <AllocationPanel title="Account Allocation" items={summary.allocation_by_account} />
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded border-l-4 border-l-red-600 border border-border bg-card px-4 py-2 text-sm text-foreground">
            {error}
            <button className="ml-2 underline text-red-600 dark:text-red-400" onClick={() => setError(null)}>dismiss</button>
          </div>
        )}

        {/* Content */}
        {view === 'add' && (
          <div className="rounded-lg border border-border p-4 bg-card">
            <h2 className="text-sm font-medium mb-4">Add Holding</h2>
            <HoldingForm onSubmit={handleAdd} onCancel={() => setView('table')} />
          </div>
        )}

        {view === 'import' && (
          <div className="rounded-lg border border-border p-4 bg-card">
            <h2 className="text-sm font-medium mb-4">Import Holdings from CSV</h2>
            <CsvImporter onImport={handleImport} onCancel={() => setView('table')} />
          </div>
        )}

        {view === 'watchlist' && (
          <div className="rounded-lg border border-border p-4 bg-card space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium">Watchlist</h2>
              <Button variant="ghost" size="sm" onClick={() => setView('table')}>Back to Portfolio</Button>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Ticker (e.g. NVDA, AAPL)"
                value={watchlistTicker}
                onChange={e => setWatchlistTicker(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && handleAddWatchlist()}
                className="h-8 rounded-md border border-input bg-background px-3 text-sm flex-1 max-w-xs"
              />
              <Button size="sm" onClick={handleAddWatchlist} disabled={!watchlistTicker.trim()}>
                <Plus size={14} className="mr-1" /> Add
              </Button>
              {watchlist.length > 0 && (
                <Button
                  size="sm"
                  variant="default"
                  onClick={handleAnalyzeWatchlist}
                  disabled={analyzing}
                  className="bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 dark:text-slate-900"
                >
                  <Brain size={14} className="mr-1" /> Analyze
                </Button>
              )}
            </div>
            {watchlist.length === 0 ? (
              <p className="text-muted-foreground text-sm">No watchlist items. Add a ticker above.</p>
            ) : (
              <div className="space-y-1">
                {watchlist.map(w => (
                  <div key={w.id} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-muted/30">
                    <div>
                      <span className="font-mono font-medium text-sm">{w.ticker}</span>
                      {w.investment_name && <span className="text-xs text-muted-foreground ml-2">{w.investment_name}</span>}
                    </div>
                    <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-muted-foreground hover:text-red-400" onClick={() => handleRemoveWatchlist(w.id)}>
                      <Trash2 size={14} />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {view === 'table' && (
          <div className="rounded-lg border border-border bg-card">
            <HoldingsTable holdings={holdings} analysisResults={analysisResults} onDelete={handleDelete} />
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={`text-lg font-bold mt-1.5 tabular-nums ${className || ''}`}>{value}</div>
    </div>
  );
}

function RiskCard({ score }: { score: number | null }) {
  if (score === null) return <SummaryCard label="Risk Score" value="—" />;

  const getColor = (s: number) => {
    if (s <= 3) return 'text-green-700 dark:text-green-400';
    if (s <= 6) return 'text-amber-700 dark:text-amber-400';
    return 'text-red-700 dark:text-red-400';
  };

  const getLabel = (s: number) => {
    if (s <= 3) return 'Low';
    if (s <= 6) return 'Medium';
    return 'High';
  };

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="text-xs text-muted-foreground flex items-center gap-1">
        <Shield size={12} /> Risk Score
      </div>
      <div className={`text-lg font-semibold mt-1 ${getColor(score)}`}>
        {score}/10 <span className="text-sm font-normal">({getLabel(score)})</span>
      </div>
    </div>
  );
}

function AccountCard({ account, onSelect }: { account: AccountSummaryItem; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      className="rounded-lg border border-border bg-card p-3 text-left hover:border-primary/50 transition-colors w-full"
    >
      <div className="text-xs text-muted-foreground">{account.owner_name}</div>
      <div className="text-sm font-medium mt-0.5">{account.label}</div>
      <div className="flex justify-between mt-2 text-xs">
        <span className="text-muted-foreground">{account.holdings_count} holdings</span>
        <span className={account.profit_loss >= 0 ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}>
          {account.profit_loss_pct !== null ? `${account.profit_loss_pct > 0 ? '+' : ''}${account.profit_loss_pct.toFixed(1)}%` : '—'}
        </span>
      </div>
    </button>
  );
}

function AllocationPanel({ title, items }: { title: string; items: AllocationItem[] }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-xs font-medium text-muted-foreground mb-3">{title}</h3>
      <div className="space-y-2">
        {items.map(item => (
          <div key={item.label} className="flex items-center gap-2">
            <div className="flex-1">
              <div className="flex justify-between text-xs">
                <span>{item.label}</span>
                <span className="text-muted-foreground">{item.percentage}%</span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary/70"
                  style={{ width: `${Math.min(item.percentage, 100)}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatLarge(n: number): string {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
