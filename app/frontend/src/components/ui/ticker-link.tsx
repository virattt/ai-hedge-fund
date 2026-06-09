import { Link } from 'react-router-dom';
import { Star } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/utils';
import { useWatchlist } from '@/contexts/watchlist-context';

interface TickerLinkProps {
  ticker: string | null | undefined;
  className?: string;
  /** Render as monospaced data text (default true). */
  mono?: boolean;
  /** Hide the watchlist star (e.g. on the watchlist page itself). */
  hideStar?: boolean;
}

/**
 * Renders a ticker symbol as a clickable HUD-styled link to the
 * Earnings Sentiment page with auto-run enabled. Includes a star button
 * for one-click watchlist add/remove.
 */
export function TickerLink({ ticker, className, mono = true, hideStar = false }: TickerLinkProps) {
  const { isWatched, toggle } = useWatchlist();
  if (!ticker) return <span className="text-muted-foreground">—</span>;
  const t = ticker.toUpperCase();
  const watched = isWatched(t);

  const handleStar = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      const nowWatched = await toggle(t);
      toast.success(nowWatched ? `Added ${t} to watchlist` : `Removed ${t} from watchlist`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Watchlist update failed');
    }
  };

  return (
    <span className="inline-flex items-center gap-1">
      {!hideStar && (
        <button
          type="button"
          onClick={handleStar}
          className="inline-flex items-center justify-center p-0.5 rounded hover:bg-accent/50 transition-colors"
          title={watched ? `Remove ${t} from watchlist` : `Add ${t} to watchlist`}
          aria-label={watched ? `Remove ${t} from watchlist` : `Add ${t} to watchlist`}
        >
          <Star
            className={cn(
              'h-3 w-3 transition-colors',
              watched ? 'fill-primary text-primary' : 'text-muted-foreground/40 hover:text-primary',
            )}
          />
        </button>
      )}
      <Link
        to={`/ticker/${encodeURIComponent(t)}`}
        className={cn(
          'inline-flex items-center px-1.5 py-0.5 rounded border border-primary/30 bg-primary/5 text-primary hover:bg-primary/15 hover:border-primary/60 hover:hud-glow transition-all',
          mono && 'font-data text-xs font-semibold tracking-wide',
          className,
        )}
        title={`Open ${t} detail page`}
      >
        {t}
      </Link>
    </span>
  );
}
