import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from 'react';
import { watchlistService } from '@/services/watchlist-api';

interface WatchlistContextValue {
  watchedTickers: Set<string>;
  isWatched: (ticker: string) => boolean;
  toggle: (ticker: string) => Promise<boolean>;  // returns new watched state
  refresh: () => Promise<void>;
}

const WatchlistContext = createContext<WatchlistContextValue>({
  watchedTickers: new Set(),
  isWatched: () => false,
  toggle: async () => false,
  refresh: async () => {},
});

export function useWatchlist() {
  return useContext(WatchlistContext);
}

export function WatchlistProvider({ children }: { children: ReactNode }) {
  const [watched, setWatched] = useState<Set<string>>(new Set());

  const refresh = useCallback(async () => {
    try {
      const res = await watchlistService.list();
      setWatched(new Set(res.items.map((i) => i.ticker.toUpperCase())));
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const isWatched = useCallback((ticker: string) => {
    return watched.has(ticker.trim().toUpperCase());
  }, [watched]);

  const toggle = useCallback(async (ticker: string) => {
    const sym = ticker.trim().toUpperCase();
    const wasWatched = watched.has(sym);
    // Optimistic update
    setWatched((prev) => {
      const next = new Set(prev);
      if (wasWatched) next.delete(sym);
      else next.add(sym);
      return next;
    });
    try {
      if (wasWatched) {
        await watchlistService.remove(sym);
      } else {
        await watchlistService.add(sym);
      }
      return !wasWatched;
    } catch (e) {
      // Revert on failure
      setWatched((prev) => {
        const next = new Set(prev);
        if (wasWatched) next.add(sym);
        else next.delete(sym);
        return next;
      });
      throw e;
    }
  }, [watched]);

  return (
    <WatchlistContext.Provider value={{ watchedTickers: watched, isWatched, toggle, refresh }}>
      {children}
    </WatchlistContext.Provider>
  );
}
