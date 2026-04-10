import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useToastManager } from '@/hooks/use-toast-manager';
import { scrapingService, Website } from '@/services/scraping-api';
import { Globe, Pencil, RefreshCw, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

interface WebsiteListProps {
  selectedWebsiteId: number | null;
  onSelect: (website: Website) => void;
  onListChange: () => void;
  onEdit: (website: Website) => void;
}

function getStatusBadgeVariant(status: string): 'secondary' | 'outline' | 'success' | 'destructive' {
  switch (status) {
    case 'in_progress':
      return 'secondary';
    case 'idle':
      return 'outline';
    case 'completed':
      return 'success';
    case 'error':
      return 'destructive';
    default:
      return 'outline';
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'in_progress':
      return 'Scraping...';
    case 'idle':
      return 'Idle';
    case 'completed':
      return 'Completed';
    case 'error':
      return 'Error';
    default:
      return status;
  }
}

export function WebsiteList({ selectedWebsiteId, onSelect, onListChange, onEdit }: WebsiteListProps) {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [loading, setLoading] = useState(true);
  const [scrapingIds, setScrapingIds] = useState<Set<number>>(new Set());
  const { success, error } = useToastManager();

  const hasInProgress = websites.some(w => w.scrape_status === 'in_progress');
  const POLL_INTERVAL_MS = hasInProgress ? 5000 : 30000;

  const fetchWebsites = useCallback(async () => {
    try {
      const data = await scrapingService.getWebsites();
      setWebsites(data);
    } catch (err) {
      error('Failed to load websites');
    } finally {
      setLoading(false);
    }
  }, [error]);

  useEffect(() => {
    fetchWebsites();
    const interval = setInterval(fetchWebsites, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchWebsites, POLL_INTERVAL_MS]);

  const handleScrapeNow = async (e: React.MouseEvent, website: Website) => {
    e.stopPropagation();
    setScrapingIds(prev => new Set(prev).add(website.id));
    try {
      await scrapingService.triggerScrape(website.id);
      success(`Scrape started for "${website.name}"`);
      fetchWebsites();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to trigger scrape';
      error(message);
    } finally {
      setScrapingIds(prev => {
        const next = new Set(prev);
        next.delete(website.id);
        return next;
      });
    }
  };

  const handleDelete = async (e: React.MouseEvent, website: Website) => {
    e.stopPropagation();
    try {
      await scrapingService.deleteWebsite(website.id);
      success(`"${website.name}" deleted`);
      onListChange();
      fetchWebsites();
    } catch (err) {
      error('Failed to delete website');
    }
  };

  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map(i => (
          <Skeleton key={i} className="h-20 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (websites.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Globe className="h-10 w-10 text-muted-foreground mb-3" />
        <p className="text-sm font-medium text-foreground">No websites added yet</p>
        <p className="text-xs text-muted-foreground mt-1">
          Add a website above to start scraping.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {websites.map(website => (
        <Card
          key={website.id}
          className={`cursor-pointer transition-colors hover:bg-accent/50 ${
            selectedWebsiteId === website.id ? 'ring-2 ring-primary bg-accent/30' : ''
          }`}
          onClick={() => onSelect(website)}
        >
          <CardContent className="p-3 flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium truncate">{website.name}</span>
                <Badge variant={getStatusBadgeVariant(website.scrape_status)} className="text-xs shrink-0">
                  {getStatusLabel(website.scrape_status)}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground truncate mt-0.5">{website.url}</p>
              {website.max_depth > 1 && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  Depth: {website.max_depth} | Max pages: {website.max_pages}
                </p>
              )}
              {website.last_scraped_at && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  Last scraped: {new Date(website.last_scraped_at).toLocaleString()}
                </p>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                title="Scrape Now"
                disabled={scrapingIds.has(website.id) || website.scrape_status === 'in_progress'}
                onClick={e => handleScrapeNow(e, website)}
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                title="Edit"
                onClick={e => {
                  e.stopPropagation();
                  onEdit(website);
                }}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-destructive hover:text-destructive"
                title="Delete"
                onClick={e => handleDelete(e, website)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
