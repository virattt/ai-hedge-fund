import { useEffect, useState } from 'react';
import { AlertCircle, AlertTriangle, Bell, CheckCheck, Info, Loader2, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { TickerLink } from '@/components/ui/ticker-link';
import { alertService, type AlertItem } from '@/services/alert-api';
import { cn } from '@/lib/utils';

const POLL_INTERVAL_MS = 60_000;

function severityIcon(severity: string) {
  if (severity === 'critical') return <AlertCircle className="h-4 w-4 text-destructive" />;
  if (severity === 'warning') return <AlertTriangle className="h-4 w-4 text-amber-400" />;
  return <Info className="h-4 w-4 text-primary" />;
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const seconds = Math.floor((Date.now() - then) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    try {
      const res = await alertService.list(20, 0, false);
      setAlerts(res.alerts);
      setUnreadCount(res.unread_count);
    } catch {
      // silent — bell just stays empty
    }
  };

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, []);

  // Refresh again when popover opens (so user sees latest immediately)
  useEffect(() => {
    if (open) refresh();
  }, [open]);

  const handleMarkRead = async (id: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    e?.preventDefault();
    try {
      await alertService.markRead(id);
      setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, is_read: true } : a)));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // ignore
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await alertService.markAllRead();
      setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })));
      setUnreadCount(0);
    } catch {
      // ignore
    }
  };

  const handleScan = async () => {
    setLoading(true);
    try {
      await alertService.scanNow();
      await refresh();
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="relative inline-flex items-center justify-center px-2 py-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
          aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
        >
          <Bell size={14} />
          {unreadCount > 0 && (
            <span className="absolute top-0 right-0 -mt-0.5 -mr-0.5 inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] font-data font-bold">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-96 p-0 border-primary/30 bg-card/90 backdrop-blur-md max-h-[70vh] overflow-hidden flex flex-col"
        align="end"
        sideOffset={8}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
          <div className="flex items-center gap-2">
            <Bell size={14} className="text-primary" />
            <span className="text-sm font-semibold uppercase tracking-wider">Alerts</span>
            {unreadCount > 0 && (
              <span className="text-[10px] font-data text-primary">{unreadCount} new</span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleScan}
              disabled={loading}
              className="h-7 px-2 text-xs"
              title="Run scan now"
            >
              {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Scan'}
            </Button>
            {unreadCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleMarkAllRead}
                className="h-7 px-2 text-xs gap-1"
                title="Mark all as read"
              >
                <CheckCheck className="h-3 w-3" />
              </Button>
            )}
          </div>
        </div>

        {/* List */}
        <div className="overflow-y-auto flex-1">
          {alerts.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">
              No alerts yet. Configure rules in <span className="text-primary">Settings</span>.
            </div>
          ) : (
            alerts.map((a) => (
              <div
                key={a.id}
                className={cn(
                  'px-4 py-3 border-b border-border/30 hover:bg-accent/20 transition-colors',
                  !a.is_read && 'bg-primary/5',
                )}
              >
                <div className="flex items-start gap-2">
                  <div className="mt-0.5 shrink-0">{severityIcon(a.severity)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <TickerLink ticker={a.ticker} />
                      <span className="text-[10px] font-data uppercase tracking-wider text-muted-foreground">
                        {a.rule_type}
                      </span>
                      <span className="text-[10px] text-muted-foreground ml-auto">
                        {timeAgo(a.created_at)}
                      </span>
                    </div>
                    <div className="mt-1 text-xs whitespace-pre-line text-foreground/90">{a.message}</div>
                    {a.sent_to_telegram && (
                      <div className="mt-1 text-[10px] font-data text-primary/70">→ telegram delivered</div>
                    )}
                    {a.telegram_error && (
                      <div className="mt-1 text-[10px] font-data text-destructive/80">
                        telegram error: {a.telegram_error}
                      </div>
                    )}
                  </div>
                  {!a.is_read && (
                    <button
                      type="button"
                      onClick={(e) => handleMarkRead(a.id, e)}
                      className="text-muted-foreground hover:text-foreground p-0.5 rounded"
                      title="Mark as read"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
