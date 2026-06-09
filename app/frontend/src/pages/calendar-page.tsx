import { useEffect, useMemo, useState, Fragment } from 'react';
import { Calendar, Loader2, RefreshCw, Star } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TickerLink } from '@/components/ui/ticker-link';
import { useWatchlist } from '@/contexts/watchlist-context';
import { calendarService, type EarningsCalendarItem } from '@/services/calendar-api';
import { cn } from '@/lib/utils';

function isoDateInput(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function todayPlus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return isoDateInput(d);
}

function formatDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z');
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

function hourBadge(hour: string | null) {
  if (!hour) return <span className="text-muted-foreground">—</span>;
  const h = hour.toLowerCase();
  const label = h === 'bmo' ? 'BMO' : h === 'amc' ? 'AMC' : h === 'dmh' ? 'DMH' : h.toUpperCase();
  const cls =
    h === 'bmo' ? 'border-primary/40 bg-primary/10 text-primary'
    : h === 'amc' ? 'border-accent-foreground/40 bg-accent text-accent-foreground'
    : 'border-border bg-muted text-muted-foreground';
  return (
    <span className={cn('inline-flex items-center font-data text-[10px] uppercase tracking-wider px-2 py-0.5 rounded border', cls)}>
      {label}
    </span>
  );
}

function formatEps(n: number | null): string {
  if (n == null) return '—';
  return `$${n.toFixed(2)}`;
}

export function CalendarPage() {
  const { isWatched } = useWatchlist();
  const [dateFrom, setDateFrom] = useState(isoDateInput(new Date()));
  const [dateTo, setDateTo] = useState(todayPlus(14));
  const [items, setItems] = useState<EarningsCalendarItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [watchlistOnly, setWatchlistOnly] = useState(false);

  const load = async (df: string, dt: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await calendarService.getEarnings(df, dt);
      setItems(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load calendar');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(dateFrom, dateTo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleApply = () => load(dateFrom, dateTo);

  const setRange = (df: string, dt: string) => {
    setDateFrom(df);
    setDateTo(dt);
    load(df, dt);
  };

  const filtered = useMemo(() => {
    let list = items;
    if (watchlistOnly) {
      list = list.filter((i) => isWatched(i.ticker));
    }
    return [...list].sort((a, b) => {
      if (a.date !== b.date) return a.date.localeCompare(b.date);
      return a.ticker.localeCompare(b.ticker);
    });
  }, [items, watchlistOnly, isWatched]);

  // Group by date for visual grouping
  const grouped = useMemo(() => {
    const map = new Map<string, EarningsCalendarItem[]>();
    for (const item of filtered) {
      const arr = map.get(item.date) || [];
      arr.push(item);
      map.set(item.date, arr);
    }
    return Array.from(map.entries());
  }, [filtered]);

  const watchedCount = useMemo(
    () => items.filter((i) => isWatched(i.ticker)).length,
    [items, isWatched],
  );

  return (
    <div className="flex-1 overflow-auto p-6 space-y-4">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Calendar size={22} className="text-primary" />
            <h1 className="text-2xl font-bold text-foreground tracking-wide uppercase">Earnings Calendar</h1>
            <span className="text-[10px] font-data uppercase tracking-widest text-primary/70">
              // {filtered.length} report{filtered.length === 1 ? '' : 's'}
              {watchlistOnly ? '' : ` · ${watchedCount} watched`}
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleApply}
            disabled={loading}
            className="gap-1.5"
          >
            {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
            Refresh
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          Upcoming earnings reports. Click a ticker to run sentiment analysis. Star to add to watchlist.
        </p>
        <div className="hud-divider" />
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-3 p-4 border border-primary/25 bg-card/60 backdrop-blur-md rounded-md">
        <div className="space-y-1">
          <label className="text-xs uppercase tracking-wider text-muted-foreground">From</label>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="font-data h-8"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs uppercase tracking-wider text-muted-foreground">To</label>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="font-data h-8"
          />
        </div>
        <Button onClick={handleApply} disabled={loading} size="sm">Apply</Button>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setRange(isoDateInput(new Date()), todayPlus(7))}
            className="text-xs"
          >
            This week
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setRange(todayPlus(7), todayPlus(14))}
            className="text-xs"
          >
            Next week
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setRange(isoDateInput(new Date()), todayPlus(30))}
            className="text-xs"
          >
            This month
          </Button>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <input
            id="watchlist-only"
            type="checkbox"
            checked={watchlistOnly}
            onChange={(e) => setWatchlistOnly(e.target.checked)}
            className="accent-primary"
          />
          <label htmlFor="watchlist-only" className="text-sm text-foreground inline-flex items-center gap-1">
            <Star className="h-3 w-3 fill-primary text-primary" /> Watchlist only
          </label>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="border border-destructive/40 bg-destructive/10 text-destructive px-4 py-3 rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Empty / Finnhub not configured hint */}
      {!loading && items.length === 0 && !error && (
        <div className="border border-primary/30 bg-primary/5 text-foreground px-4 py-6 rounded-md text-sm space-y-1">
          <p className="font-medium">No earnings data returned.</p>
          <p className="text-muted-foreground">
            The calendar requires <span className="font-data text-primary">FINNHUB_API_KEY</span> in your <code>.env</code>.
            Get a free key at <a href="https://finnhub.io" target="_blank" rel="noreferrer" className="text-primary underline">finnhub.io</a> (60 req/min on the free tier) and restart the backend.
          </p>
        </div>
      )}

      {/* Table */}
      {filtered.length > 0 && (
        <div className="border border-primary/25 bg-card/60 backdrop-blur-md rounded-md overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="uppercase text-xs tracking-wider">Date</TableHead>
                <TableHead className="uppercase text-xs tracking-wider">Ticker</TableHead>
                <TableHead className="uppercase text-xs tracking-wider">Hour</TableHead>
                <TableHead className="uppercase text-xs tracking-wider text-right">EPS Est.</TableHead>
                <TableHead className="uppercase text-xs tracking-wider text-right">EPS Actual</TableHead>
                <TableHead className="uppercase text-xs tracking-wider">Quarter</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {grouped.map(([date, dateItems]) => (
                <Fragment key={`group-${date}`}>
                  <TableRow className="bg-primary/5 hover:bg-primary/5">
                    <TableCell colSpan={6} className="text-xs font-data uppercase tracking-wider text-primary py-1.5">
                      {formatDate(date)} <span className="text-muted-foreground">· {dateItems.length} report{dateItems.length === 1 ? '' : 's'}</span>
                    </TableCell>
                  </TableRow>
                  {dateItems.map((item) => {
                    const watched = isWatched(item.ticker);
                    return (
                      <TableRow
                        key={`${item.date}-${item.ticker}`}
                        className={cn(watched && 'border-l-2 border-l-primary')}
                      >
                        <TableCell className="font-data text-xs text-muted-foreground">{item.date}</TableCell>
                        <TableCell><TickerLink ticker={item.ticker} /></TableCell>
                        <TableCell>{hourBadge(item.hour)}</TableCell>
                        <TableCell className="font-data text-sm text-right">{formatEps(item.eps_estimate)}</TableCell>
                        <TableCell className="font-data text-sm text-right">{formatEps(item.eps_actual)}</TableCell>
                        <TableCell className="font-data text-xs text-muted-foreground">
                          {item.quarter ? `Q${item.quarter}${item.fiscal_year ? ` ${item.fiscal_year}` : ''}` : '—'}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
