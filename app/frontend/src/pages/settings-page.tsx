import { useEffect, useState } from 'react';
import { Anchor, Bell, Database, Loader2, Send, Settings, Trash2, UserCheck, Zap } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ModelSelector } from '@/components/ui/llm-selector';
import { useSettings } from '@/contexts/settings-context';
import { alertService, type AlertSettingsResponse } from '@/services/alert-api';
import { cacheService } from '@/services/cache-api';
import { whaleService, type WhaleFund, type WhaleFundCandidate } from '@/services/whale-api';

const PANEL_CLASS =
  'hud-corner-bracket border border-primary/25 bg-card/60 backdrop-blur-md backdrop-saturate-150 p-6 rounded-md space-y-4 shadow-[0_4px_24px_hsl(210_55%_3%/0.45),inset_0_1px_0_hsl(var(--primary)/0.1)]';

export function SettingsPage() {
  const { selectedModel, models, setSelectedModel, loading: llmLoading } = useSettings();

  // Alerts state
  const [alertSettings, setAlertSettings] = useState<AlertSettingsResponse | null>(null);
  const [alertLoading, setAlertLoading] = useState(true);
  const [savingTelegram, setSavingTelegram] = useState(false);
  const [savingThresholds, setSavingThresholds] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [testing, setTesting] = useState(false);

  // Editable form state
  const [tokenInput, setTokenInput] = useState('');
  const [chatIdInput, setChatIdInput] = useState('');
  const [enabled, setEnabled] = useState(false);

  // Whale funds state
  const [whaleFunds, setWhaleFunds] = useState<WhaleFund[]>([]);
  const [whaleLoading, setWhaleLoading] = useState(true);
  const [whaleSearchQuery, setWhaleSearchQuery] = useState('');
  const [whaleSearchResults, setWhaleSearchResults] = useState<WhaleFundCandidate[]>([]);
  const [whaleSearching, setWhaleSearching] = useState(false);
  const [whaleRefreshing, setWhaleRefreshing] = useState(false);

  const [flushingCache, setFlushingCache] = useState(false);
  const [lastFlushSummary, setLastFlushSummary] = useState<string | null>(null);
  const [interval, setIntervalHours] = useState(4);
  const [minShortPct, setMinShortPct] = useState(25);
  const [minDaysToCover, setMinDaysToCover] = useState(2);
  const [requireInsiderBuy, setRequireInsiderBuy] = useState(true);
  const [csuiteMinValue, setCsuiteMinValue] = useState(250000);
  const [savingCsuite, setSavingCsuite] = useState(false);

  const loadAlertSettings = async () => {
    try {
      const s = await alertService.getSettings();
      setAlertSettings(s);
      setChatIdInput(s.telegram_chat_id);
      setEnabled(s.telegram_enabled);
      setIntervalHours(s.scan_interval_hours);
      setMinShortPct(s.squeeze_min_short_pct);
      setMinDaysToCover(s.squeeze_min_days_to_cover);
      setRequireInsiderBuy(s.squeeze_require_insider_buy);
      setCsuiteMinValue(s.csuite_min_value);
    } catch (e) {
      toast.error('Failed to load alert settings');
    } finally {
      setAlertLoading(false);
    }
  };

  useEffect(() => {
    loadAlertSettings();
  }, []);

  const loadWhales = async () => {
    setWhaleLoading(true);
    try {
      const res = await whaleService.listFunds();
      setWhaleFunds(res.items);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Whale fund load failed');
    } finally {
      setWhaleLoading(false);
    }
  };

  useEffect(() => {
    loadWhales();
  }, []);

  // Debounced whale candidate search
  useEffect(() => {
    if (whaleSearchQuery.trim().length < 2) {
      setWhaleSearchResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setWhaleSearching(true);
      try {
        const res = await whaleService.searchCandidates(whaleSearchQuery, 8);
        setWhaleSearchResults(res.candidates);
      } catch {
        setWhaleSearchResults([]);
      } finally {
        setWhaleSearching(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [whaleSearchQuery]);

  const handleAddWhale = async (cik: number, company: string) => {
    try {
      await whaleService.addFund(cik, company);
      toast.success(`Added ${company} to whales`);
      setWhaleSearchQuery('');
      setWhaleSearchResults([]);
      await loadWhales();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Add failed');
    }
  };

  const handleRemoveWhale = async (cik: number, name: string) => {
    try {
      await whaleService.removeFund(cik);
      toast.success(`Removed ${name}`);
      await loadWhales();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Remove failed');
    }
  };

  const handleRefreshWhales = async () => {
    setWhaleRefreshing(true);
    try {
      const res = await whaleService.refreshAll(false);
      toast.success(`Refreshed entries (${res.total_rows_written} rows written)`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Refresh failed');
    } finally {
      setWhaleRefreshing(false);
    }
  };

  const handleFlushCache = async () => {
    setFlushingCache(true);
    try {
      const res = await cacheService.flush();
      const populated = Object.entries(res.cleared)
        .filter(([, n]) => n > 0)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 5)
        .map(([name, n]) => `${name} (${n})`)
        .join(', ');
      const summary = populated
        ? `Cleared ${res.total_entries} entries — top: ${populated}`
        : `All ${Object.keys(res.cleared).length} caches were already empty`;
      setLastFlushSummary(summary);
      toast.success(summary);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Cache flush failed');
    } finally {
      setFlushingCache(false);
    }
  };

  const handleSaveTelegram = async () => {
    setSavingTelegram(true);
    try {
      // Only send token if user typed a new one
      const updated = await alertService.updateSettings({
        telegram_bot_token: tokenInput.trim() ? tokenInput.trim() : undefined,
        telegram_chat_id: chatIdInput,
        telegram_enabled: enabled,
      });
      setAlertSettings(updated);
      setTokenInput('');
      toast.success('Telegram settings saved');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSavingTelegram(false);
    }
  };

  const handleSaveThresholds = async () => {
    setSavingThresholds(true);
    try {
      const updated = await alertService.updateSettings({
        scan_interval_hours: interval,
        squeeze_min_short_pct: minShortPct,
        squeeze_min_days_to_cover: minDaysToCover,
        squeeze_require_insider_buy: requireInsiderBuy,
      });
      setAlertSettings(updated);
      toast.success('Rule thresholds saved');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSavingThresholds(false);
    }
  };

  const handleSaveCsuite = async () => {
    setSavingCsuite(true);
    try {
      const updated = await alertService.updateSettings({
        csuite_min_value: csuiteMinValue,
      });
      setAlertSettings(updated);
      toast.success('C-suite threshold saved');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSavingCsuite(false);
    }
  };

  const handleTestTelegram = async () => {
    setTesting(true);
    try {
      const r = await alertService.testTelegram();
      if (r.success) toast.success('Telegram test message sent');
      else toast.error(r.error || 'Telegram test failed');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  const handleScanNow = async () => {
    setScanning(true);
    try {
      const r = await alertService.scanNow();
      toast.success(`Scan complete: ${r.candidates_evaluated} candidates evaluated, ${r.alerts_created} alerts created`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Scan failed');
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        <div className="space-y-2 mb-2">
          <div className="flex items-center gap-3">
            <Settings size={22} className="text-primary" />
            <h1 className="text-2xl font-bold text-foreground tracking-wide uppercase">Settings</h1>
            <span className="text-[10px] font-data uppercase tracking-widest text-primary/70">// system config</span>
          </div>
          <div className="hud-divider" />
        </div>

        {/* LLM Model section */}
        <section className={PANEL_CLASS}>
          <div>
            <h2 className="text-lg font-semibold text-foreground tracking-wide">LLM Model</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Select the LLM model used for News analysis and Earnings sentiment.
            </p>
          </div>
          {llmLoading ? (
            <div className="text-sm text-muted-foreground font-data">Loading models...</div>
          ) : (
            <ModelSelector
              models={models}
              value={selectedModel?.model_name ?? ''}
              onChange={(m) => m && setSelectedModel(m)}
              placeholder="Select an LLM model..."
            />
          )}
          {selectedModel && (
            <p className="text-xs text-muted-foreground font-data">
              Active: <span className="text-primary">{selectedModel.model_name}</span> ({selectedModel.provider})
            </p>
          )}
        </section>

        {/* Alerts: Telegram */}
        <section className={PANEL_CLASS}>
          <div className="flex items-center gap-2">
            <Send size={16} className="text-primary" />
            <h2 className="text-lg font-semibold text-foreground tracking-wide">Telegram</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Configure your Telegram bot to receive alerts. Create a bot via{' '}
            <a className="text-primary underline" href="https://t.me/BotFather" target="_blank" rel="noreferrer">@BotFather</a>{' '}
            and find your chat ID via <a className="text-primary underline" href="https://t.me/userinfobot" target="_blank" rel="noreferrer">@userinfobot</a>.
          </p>

          {alertLoading ? (
            <div className="text-sm text-muted-foreground font-data">Loading...</div>
          ) : (
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Bot Token</label>
                <Input
                  type="password"
                  placeholder={alertSettings?.telegram_bot_token || 'Paste new token to update'}
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  className="font-data"
                />
                {alertSettings?.telegram_bot_token && (
                  <p className="text-[10px] text-muted-foreground font-data">
                    Current: {alertSettings.telegram_bot_token} (leave empty to keep)
                  </p>
                )}
              </div>
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Chat ID</label>
                <Input
                  placeholder="123456789"
                  value={chatIdInput}
                  onChange={(e) => setChatIdInput(e.target.value)}
                  className="font-data"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="telegram-enabled"
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                  className="accent-primary"
                />
                <label htmlFor="telegram-enabled" className="text-sm text-foreground">
                  Enable Telegram alerts
                </label>
              </div>
              <div className="flex gap-2">
                <Button onClick={handleSaveTelegram} disabled={savingTelegram} size="sm">
                  {savingTelegram && <Loader2 className="h-3 w-3 animate-spin mr-1.5" />}
                  Save
                </Button>
                <Button onClick={handleTestTelegram} disabled={testing} size="sm" variant="outline">
                  {testing && <Loader2 className="h-3 w-3 animate-spin mr-1.5" />}
                  Send test message
                </Button>
              </div>
            </div>
          )}
        </section>

        {/* Alerts: Squeeze rule + scheduler */}
        <section className={PANEL_CLASS}>
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-primary" />
            <h2 className="text-lg font-semibold text-foreground tracking-wide">Short-Squeeze Rule</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Triggers when a stock has high short interest, high days-to-cover, and (optionally) recent insider buying.
          </p>

          {alertLoading ? (
            <div className="text-sm text-muted-foreground font-data">Loading...</div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Min short % of float</label>
                <Input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={minShortPct}
                  onChange={(e) => setMinShortPct(parseFloat(e.target.value) || 0)}
                  className="font-data"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Min days to cover</label>
                <Input
                  type="number"
                  step="0.5"
                  min="0"
                  value={minDaysToCover}
                  onChange={(e) => setMinDaysToCover(parseFloat(e.target.value) || 0)}
                  className="font-data"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Scan interval (hours)</label>
                <Input
                  type="number"
                  step="1"
                  min="1"
                  max="168"
                  value={interval}
                  onChange={(e) => setIntervalHours(parseInt(e.target.value, 10) || 4)}
                  className="font-data"
                />
              </div>
              <div className="flex items-end gap-2">
                <input
                  id="require-insider"
                  type="checkbox"
                  checked={requireInsiderBuy}
                  onChange={(e) => setRequireInsiderBuy(e.target.checked)}
                  className="accent-primary"
                />
                <label htmlFor="require-insider" className="text-sm text-foreground pb-1">
                  Require recent insider buy
                </label>
              </div>
              <div className="col-span-2 flex gap-2">
                <Button onClick={handleSaveThresholds} disabled={savingThresholds} size="sm">
                  {savingThresholds && <Loader2 className="h-3 w-3 animate-spin mr-1.5" />}
                  Save thresholds
                </Button>
                <Button onClick={handleScanNow} disabled={scanning} size="sm" variant="outline" className="gap-1.5">
                  {scanning ? <Loader2 className="h-3 w-3 animate-spin" /> : <Bell className="h-3 w-3" />}
                  Run scan now
                </Button>
              </div>
            </div>
          )}
        </section>

        {/* Alerts: C-Suite Insider Buy rule */}
        <section className={PANEL_CLASS}>
          <div className="flex items-center gap-2">
            <UserCheck size={16} className="text-primary" />
            <h2 className="text-lg font-semibold text-foreground tracking-wide">C-Level Insider Buy</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Alerts when CEO / CFO / COO / President buys this dollar amount or more in any spin-off entity tracked on the Catalysts page. Buys ≥ $1M are flagged critical (red).
          </p>

          {alertLoading ? (
            <div className="text-sm text-muted-foreground font-data">Loading...</div>
          ) : (
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Min purchase value ($)</label>
                <Input
                  type="number"
                  step="50000"
                  min="0"
                  value={csuiteMinValue}
                  onChange={(e) => setCsuiteMinValue(parseFloat(e.target.value) || 0)}
                  className="font-data"
                />
                <p className="text-[10px] text-muted-foreground font-data">
                  Currently: ${csuiteMinValue.toLocaleString()}
                </p>
              </div>
              <Button onClick={handleSaveCsuite} disabled={savingCsuite} size="sm">
                {savingCsuite && <Loader2 className="h-3 w-3 animate-spin mr-1.5" />}
                Save threshold
              </Button>
            </div>
          )}
        </section>

        {/* Whale funds */}
        <section className={PANEL_CLASS}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Anchor size={18} className="text-primary" />
              <h2 className="text-lg font-semibold text-foreground tracking-wide">Whale Funds</h2>
              <span className="text-[10px] font-data text-muted-foreground uppercase">
                {whaleFunds.length} tracked
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={handleRefreshWhales}
              disabled={whaleRefreshing}
              className="gap-1.5"
              title="Recompute entry prices from latest 13F filings (slow on cold cache)"
            >
              {whaleRefreshing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Anchor className="h-3 w-3" />}
              Refresh entries
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Whales' 13F-tracked entries drive the "vs Whale" column on Watchlist + Discovery and power the
            don't-chase filter (hides ideas trading &gt;20% above the cheapest whale's entry price).
          </p>

          <div className="space-y-2">
            <label className="text-xs uppercase tracking-wider text-muted-foreground">Add a fund</label>
            <Input
              placeholder="Search 13F filer name (min 2 chars)..."
              value={whaleSearchQuery}
              onChange={(e) => setWhaleSearchQuery(e.target.value)}
              className="font-data"
            />
            {whaleSearching && (
              <p className="text-[10px] text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin inline-block mr-1" />Searching…</p>
            )}
            {whaleSearchResults.length > 0 && (
              <div className="border border-primary/20 rounded-md max-h-48 overflow-y-auto bg-card/60">
                {whaleSearchResults.map((c) => (
                  <button
                    key={c.cik}
                    type="button"
                    onClick={() => handleAddWhale(c.cik, c.company)}
                    className="flex items-center justify-between w-full px-2 py-1.5 text-left text-xs hover:bg-primary/10 transition-colors border-b border-primary/10 last:border-b-0"
                  >
                    <span className="truncate">{c.company}</span>
                    <span className="font-data text-[10px] text-muted-foreground ml-2">CIK {c.cik}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {whaleLoading ? (
            <p className="text-sm text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin inline-block mr-2" />Loading…</p>
          ) : whaleFunds.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">No whale funds tracked yet. Use the search above to add some.</p>
          ) : (
            <ul className="space-y-1">
              {whaleFunds.map((w) => (
                <li key={w.id} className="flex items-center justify-between p-2 rounded border border-primary/10 hover:border-primary/30 transition-colors">
                  <div className="flex flex-col">
                    <span className="text-sm font-medium">{w.name}</span>
                    <span className="text-[10px] font-data text-muted-foreground">CIK {w.cik}{w.notes ? ` · ${w.notes}` : ''}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRemoveWhale(w.cik, w.name)}
                    className="h-7 w-7 p-0 hover:text-destructive"
                    title="Remove from whale list"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className={PANEL_CLASS}>
          <div className="flex items-center gap-2">
            <Database size={18} className="text-primary" />
            <h2 className="text-lg font-semibold text-foreground tracking-wide">Cache</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Wipe every in-memory cache (Discovery ideas, pricing, fundamentals, news sentiment,
            whale entries, OpenInsider, etc.). Forces the next page load to recompute fresh —
            useful after fixing a bug or when results look stale. The DB is untouched.
          </p>
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              variant="outline"
              onClick={handleFlushCache}
              disabled={flushingCache}
              className="gap-1.5"
            >
              {flushingCache ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
              Flush all caches
            </Button>
            {lastFlushSummary && (
              <span className="text-xs text-muted-foreground font-data">{lastFlushSummary}</span>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
