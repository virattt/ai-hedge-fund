import { useEffect, useState } from 'react';

import { useI18n } from '@/i18n/use-i18n';

// Research-only Observing Pools view: ranked per-platform pool + opportunity
// reports, fully EN/CN via the existing i18n hook. Read-only; loopback API.

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const PLATFORMS = ['ai', 'robotics', 'energy_storage', 'blockchain', 'multiomic_sequencing'] as const;

interface PoolEntry {
  ticker: string;
  rank: number | null;
  composite_score: number | null;
  composite_formula_version: string | null;
  components: {
    platform_fit: number | null;
    value_investor: number | null;
    innovation_growth: number | null;
    risk_adjusted_momentum: number | null;
    serenity_bottleneck: number | null;
  };
  rationale: string | null;
}

interface OpportunityReport {
  id: number;
  ticker: string;
  label: string;
  confidence: number | null;
  degraded: boolean;
  summary: string | null;
  disclaimer: string;
  disclaimer_version: string;
}

const fmt = (v: number | null | undefined): string => (v == null ? '—' : v.toFixed(0));

export function ObservingPoolsView() {
  const { t, locale, toggleLocale } = useI18n();
  const [platform, setPlatform] = useState<string>('ai');
  const [entries, setEntries] = useState<PoolEntry[]>([]);
  const [reports, setReports] = useState<OpportunityReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    Promise.all([
      fetch(`${API_BASE_URL}/observing-pools/${platform}`).then((r) => r.json()),
      fetch(`${API_BASE_URL}/opportunity-reports`).then((r) => r.json()),
    ])
      .then(([pool, reps]) => {
        if (cancelled) return;
        setEntries(pool?.entries ?? []);
        setReports(Array.isArray(reps) ? reps : []);
      })
      .catch(() => !cancelled && setError(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [platform]);

  return (
    <div className="p-4 space-y-4 text-sm">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">{t('observingPools.title')}</h2>
          <p className="text-muted-foreground">{t('observingPools.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="border rounded px-2 py-1 bg-background"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
          >
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <button className="border rounded px-2 py-1" onClick={toggleLocale}>
            {t('observingPools.toggleLanguage')} ({locale})
          </button>
        </div>
      </div>

      {loading && <div>{t('observingPools.loading')}</div>}
      {error && <div className="text-red-500">{t('observingPools.error')}</div>}

      {!loading && !error && (
        <>
          <table className="w-full border-collapse">
            <thead>
              <tr className="text-left border-b">
                <th className="py-1 pr-2">{t('observingPools.rank')}</th>
                <th className="py-1 pr-2">{t('observingPools.ticker')}</th>
                <th className="py-1 pr-2">{t('observingPools.composite')}</th>
                <th className="py-1 pr-2">{t('observingPools.platformFit')}</th>
                <th className="py-1 pr-2">{t('observingPools.value')}</th>
                <th className="py-1 pr-2">{t('observingPools.growth')}</th>
                <th className="py-1 pr-2">{t('observingPools.momentum')}</th>
                <th className="py-1 pr-2">{t('observingPools.serenity')}</th>
                <th className="py-1 pr-2">{t('observingPools.formula')}</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.ticker} className="border-b hover:bg-muted/40" title={e.rationale ?? ''}>
                  <td className="py-1 pr-2">{e.rank}</td>
                  <td className="py-1 pr-2 font-medium">{e.ticker}</td>
                  <td className="py-1 pr-2">{e.composite_score?.toFixed(1) ?? '—'}</td>
                  <td className="py-1 pr-2">{fmt(e.components.platform_fit)}</td>
                  <td className="py-1 pr-2">{fmt(e.components.value_investor)}</td>
                  <td className="py-1 pr-2">{fmt(e.components.innovation_growth)}</td>
                  <td className="py-1 pr-2">{fmt(e.components.risk_adjusted_momentum)}</td>
                  <td className="py-1 pr-2">{fmt(e.components.serenity_bottleneck)}</td>
                  <td className="py-1 pr-2 text-muted-foreground">{e.composite_formula_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {entries.length === 0 && <div className="text-muted-foreground">{t('observingPools.empty')}</div>}

          <h3 className="text-base font-semibold pt-2">{t('observingPools.reportsTitle')}</h3>
          {reports.length === 0 && <div className="text-muted-foreground">{t('observingPools.noReports')}</div>}
          <div className="space-y-2">
            {reports.map((r) => (
              <div key={r.id} className="border rounded p-2">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{r.ticker}</span>
                  <span className="px-2 py-0.5 rounded bg-muted text-xs">{r.label}</span>
                  {r.degraded && <span className="text-amber-500 text-xs">{t('observingPools.degraded')}</span>}
                  <span className="text-muted-foreground text-xs">
                    {t('observingPools.confidence')}: {fmt(r.confidence)}
                  </span>
                </div>
                {r.summary && <p className="text-muted-foreground mt-1">{r.summary}</p>}
                <p className="text-[10px] text-muted-foreground mt-1 italic">
                  {r.disclaimer} ({r.disclaimer_version})
                </p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
