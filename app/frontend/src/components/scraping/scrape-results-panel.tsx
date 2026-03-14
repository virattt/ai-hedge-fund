import React, { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToastManager } from '@/hooks/use-toast-manager';
import { scrapingService, ScrapeResult, ScrapeResultDetail, Website } from '@/services/scraping-api';
import { ChevronDown, ChevronRight, FileText } from 'lucide-react';

interface ScrapeResultsPanelProps {
  selectedWebsite: Website | null;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ScrapeResultsPanel({ selectedWebsite }: ScrapeResultsPanelProps) {
  const [results, setResults] = useState<ScrapeResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedDetail, setExpandedDetail] = useState<ScrapeResultDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const { error } = useToastManager();

  useEffect(() => {
    if (!selectedWebsite) {
      setResults([]);
      setExpandedId(null);
      setExpandedDetail(null);
      return;
    }

    const fetchResults = async () => {
      setLoading(true);
      try {
        const data = await scrapingService.getResults(selectedWebsite.id);
        setResults(data);
      } catch (err) {
        error('Failed to load scrape results');
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
    setExpandedId(null);
    setExpandedDetail(null);
  }, [selectedWebsite, error]);

  const handleToggleExpand = async (result: ScrapeResult) => {
    if (expandedId === result.id) {
      setExpandedId(null);
      setExpandedDetail(null);
      return;
    }

    setExpandedId(result.id);
    setExpandedDetail(null);
    setLoadingDetail(true);
    try {
      const detail = await scrapingService.getResultDetail(result.id);
      setExpandedDetail(detail);
    } catch (err) {
      error('Failed to load result content');
      setExpandedId(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  if (!selectedWebsite) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16 text-center">
        <FileText className="h-10 w-10 text-muted-foreground mb-3" />
        <p className="text-sm font-medium text-foreground">No website selected</p>
        <p className="text-xs text-muted-foreground mt-1">
          Select a website from the list to view its scrape results.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-2 p-1">
        {[1, 2, 3, 4].map(i => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <FileText className="h-10 w-10 text-muted-foreground mb-3" />
        <p className="text-sm font-medium text-foreground">No results yet</p>
        <p className="text-xs text-muted-foreground mt-1">
          Trigger a scrape to see results for "{selectedWebsite.name}".
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8"></TableHead>
            <TableHead>Scraped At</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Preview</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.map(result => (
            <React.Fragment key={result.id}>
              <TableRow
                key={result.id}
                className="cursor-pointer hover:bg-accent/50"
                onClick={() => handleToggleExpand(result)}
              >
                <TableCell className="py-2 px-2">
                  {expandedId === result.id
                    ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                </TableCell>
                <TableCell className="py-2 text-xs whitespace-nowrap">
                  {new Date(result.scraped_at).toLocaleString()}
                </TableCell>
                <TableCell className="py-2">
                  <Badge
                    variant={result.status === 'success' ? 'success' : 'destructive'}
                    className="text-xs"
                  >
                    {result.status}
                  </Badge>
                </TableCell>
                <TableCell className="py-2 text-xs">
                  {formatBytes(result.content_length)}
                </TableCell>
                <TableCell className="py-2 text-xs text-muted-foreground max-w-xs truncate">
                  {result.status === 'error'
                    ? result.error_message || 'Error'
                    : result.content_preview}
                </TableCell>
              </TableRow>
              {expandedId === result.id && (
                <TableRow key={`${result.id}-detail`}>
                  <TableCell colSpan={5} className="py-3 px-4 bg-muted/30">
                    {loadingDetail ? (
                      <div className="space-y-2">
                        <Skeleton className="h-4 w-full" />
                        <Skeleton className="h-4 w-4/5" />
                        <Skeleton className="h-4 w-3/5" />
                      </div>
                    ) : expandedDetail ? (
                      <div>
                        {expandedDetail.status === 'error' ? (
                          <p className="text-sm text-destructive font-medium">
                            {expandedDetail.error_message || 'An error occurred during scraping.'}
                          </p>
                        ) : (
                          <pre className="text-xs text-foreground whitespace-pre-wrap break-words max-h-64 overflow-y-auto font-mono leading-relaxed">
                            {expandedDetail.content || '(No content)'}
                          </pre>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="mt-2 h-7 text-xs"
                          onClick={e => {
                            e.stopPropagation();
                            setExpandedId(null);
                            setExpandedDetail(null);
                          }}
                        >
                          Collapse
                        </Button>
                      </div>
                    ) : null}
                  </TableCell>
                </TableRow>
              )}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
