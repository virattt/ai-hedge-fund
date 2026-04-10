import React, { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useToastManager } from '@/hooks/use-toast-manager';
import {
  scrapingService,
  ScrapeResult,
  ScrapeResultDetail,
  ScrapeRun,
  Website,
} from '@/services/scraping-api';
import { ChevronDown, ChevronRight, Copy, FileText } from 'lucide-react';

interface ScrapeResultsPanelProps {
  selectedWebsite: Website | null;
}

interface TreeNode {
  result: ScrapeResult;
  children: TreeNode[];
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function buildTree(results: ScrapeResult[]): TreeNode[] {
  const nodeMap = new Map<number, TreeNode>();
  const roots: TreeNode[] = [];

  for (const result of results) {
    nodeMap.set(result.id, { result, children: [] });
  }

  for (const result of results) {
    const node = nodeMap.get(result.id)!;
    if (result.parent_result_id && nodeMap.has(result.parent_result_id)) {
      nodeMap.get(result.parent_result_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

function TreeRow({
  node,
  expandedId,
  expandedDetail,
  loadingDetail,
  onToggle,
}: {
  node: TreeNode;
  expandedId: number | null;
  expandedDetail: ScrapeResultDetail | null;
  loadingDetail: boolean;
  onToggle: (result: ScrapeResult) => void;
}) {
  const { result } = node;
  const isExpanded = expandedId === result.id;
  const depthPadding = result.depth * 20;

  return (
    <>
      <div
        className="flex items-center gap-2 py-2 px-3 cursor-pointer hover:bg-accent/50 border-b border-border/50"
        style={{ paddingLeft: `${12 + depthPadding}px` }}
        onClick={() => onToggle(result)}
      >
        {isExpanded
          ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
        {result.depth > 0 && (
          <span className="text-muted-foreground text-xs shrink-0">{'└'}</span>
        )}
        <span className="text-xs truncate flex-1 font-mono" title={result.page_url || undefined}>
          {result.page_url
            ? new URL(result.page_url).pathname || '/'
            : 'Root page'}
        </span>
        <Badge
          variant={result.status === 'success' ? 'success' : 'destructive'}
          className="text-xs shrink-0"
        >
          {result.status}
        </Badge>
        <span className="text-xs text-muted-foreground shrink-0">
          {formatBytes(result.content_length)}
        </span>
      </div>

      {isExpanded && (
        <div className="border-b border-border/50">
          {loadingDetail ? (
            <div className="p-4 space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-4 w-3/5" />
            </div>
          ) : expandedDetail ? (
            <div className="p-4">
              {expandedDetail.status === 'error' ? (
                <p className="text-sm text-destructive font-medium">
                  {expandedDetail.error_message || 'An error occurred during scraping.'}
                </p>
              ) : (
                <div className="rounded-lg bg-muted/50 border">
                  <div className="flex items-center justify-between px-3 py-1.5 border-b">
                    <span className="text-xs text-muted-foreground font-mono truncate">
                      {expandedDetail.page_url || 'Root page'}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      title="Copy URL"
                      onClick={e => {
                        e.stopPropagation();
                        if (expandedDetail.page_url) {
                          navigator.clipboard.writeText(expandedDetail.page_url);
                        }
                      }}
                    >
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                  <pre className="text-xs text-foreground whitespace-pre-wrap break-words max-h-96 overflow-y-auto font-mono leading-relaxed p-3">
                    {expandedDetail.content || '(No content)'}
                  </pre>
                </div>
              )}
              <Button
                variant="ghost"
                size="sm"
                className="mt-2 h-7 text-xs"
                onClick={e => {
                  e.stopPropagation();
                  onToggle(result);
                }}
              >
                Collapse
              </Button>
            </div>
          ) : null}
        </div>
      )}

      {node.children.map(child => (
        <TreeRow
          key={child.result.id}
          node={child}
          expandedId={expandedId}
          expandedDetail={expandedDetail}
          loadingDetail={loadingDetail}
          onToggle={onToggle}
        />
      ))}
    </>
  );
}

export function ScrapeResultsPanel({ selectedWebsite }: ScrapeResultsPanelProps) {
  const [runs, setRuns] = useState<ScrapeRun[]>([]);
  const [legacyResults, setLegacyResults] = useState<ScrapeResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [runResults, setRunResults] = useState<ScrapeResult[]>([]);
  const [loadingRun, setLoadingRun] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedDetail, setExpandedDetail] = useState<ScrapeResultDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const { error } = useToastManager();

  useEffect(() => {
    if (!selectedWebsite) {
      setRuns([]);
      setLegacyResults([]);
      setExpandedRunId(null);
      setRunResults([]);
      setExpandedId(null);
      setExpandedDetail(null);
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      try {
        const [runsData, allResults] = await Promise.all([
          scrapingService.getRuns(selectedWebsite.id),
          scrapingService.getResults(selectedWebsite.id),
        ]);
        setRuns(runsData);
        setLegacyResults(allResults.filter(r => !r.scrape_run_id));
      } catch {
        error('Failed to load scrape data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    setExpandedRunId(null);
    setRunResults([]);
    setExpandedId(null);
    setExpandedDetail(null);
  }, [selectedWebsite, error]);

  const handleExpandRun = async (runId: string) => {
    if (expandedRunId === runId) {
      setExpandedRunId(null);
      setRunResults([]);
      setExpandedId(null);
      setExpandedDetail(null);
      return;
    }

    setExpandedRunId(runId);
    setRunResults([]);
    setExpandedId(null);
    setExpandedDetail(null);
    setLoadingRun(true);
    try {
      const results = await scrapingService.getRunResults(runId);
      setRunResults(results);
    } catch {
      error('Failed to load run results');
      setExpandedRunId(null);
    } finally {
      setLoadingRun(false);
    }
  };

  const handleToggleDetail = async (result: ScrapeResult) => {
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
    } catch {
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
      <div className="space-y-2 p-4">
        {[1, 2, 3, 4].map(i => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (runs.length === 0 && legacyResults.length === 0) {
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

  const treeNodes = expandedRunId ? buildTree(runResults) : [];

  return (
    <div className="overflow-auto h-full">
      {/* Run list */}
      {runs.map(run => (
        <React.Fragment key={run.scrape_run_id}>
          <div
            className="flex items-center gap-3 py-2.5 px-4 cursor-pointer hover:bg-accent/50 border-b"
            onClick={() => handleExpandRun(run.scrape_run_id)}
          >
            {expandedRunId === run.scrape_run_id
              ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
              : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
            <span className="text-xs whitespace-nowrap">
              {new Date(run.scraped_at).toLocaleString()}
            </span>
            <span className="text-xs text-muted-foreground">
              {run.total_pages} page{run.total_pages !== 1 ? 's' : ''}
            </span>
            <div className="flex gap-1 ml-auto">
              {run.success_count > 0 && (
                <Badge variant="success" className="text-xs">{run.success_count} ok</Badge>
              )}
              {run.error_count > 0 && (
                <Badge variant="destructive" className="text-xs">{run.error_count} err</Badge>
              )}
            </div>
          </div>

          {expandedRunId === run.scrape_run_id && (
            <div className="bg-muted/20">
              {loadingRun ? (
                <div className="p-4 space-y-2">
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                </div>
              ) : (
                treeNodes.map(node => (
                  <TreeRow
                    key={node.result.id}
                    node={node}
                    expandedId={expandedId}
                    expandedDetail={expandedDetail}
                    loadingDetail={loadingDetail}
                    onToggle={handleToggleDetail}
                  />
                ))
              )}
            </div>
          )}
        </React.Fragment>
      ))}

      {/* Legacy results (no scrape_run_id) */}
      {legacyResults.length > 0 && (
        <>
          {runs.length > 0 && (
            <div className="px-4 py-2 text-xs font-medium text-muted-foreground bg-muted/30 border-b">
              Legacy Results
            </div>
          )}
          {legacyResults.map(result => (
            <div key={result.id}>
              <div
                className="flex items-center gap-2 py-2 px-4 cursor-pointer hover:bg-accent/50 border-b border-border/50"
                onClick={() => handleToggleDetail(result)}
              >
                {expandedId === result.id
                  ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                  : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
                <span className="text-xs whitespace-nowrap">
                  {new Date(result.scraped_at).toLocaleString()}
                </span>
                <Badge
                  variant={result.status === 'success' ? 'success' : 'destructive'}
                  className="text-xs"
                >
                  {result.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {formatBytes(result.content_length)}
                </span>
                <span className="text-xs text-muted-foreground max-w-xs truncate ml-auto">
                  {result.status === 'error' ? result.error_message || 'Error' : result.content_preview}
                </span>
              </div>
              {expandedId === result.id && (
                <div className="border-b border-border/50 p-4 bg-muted/20">
                  {loadingDetail ? (
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-full" />
                      <Skeleton className="h-4 w-4/5" />
                    </div>
                  ) : expandedDetail ? (
                    <div>
                      {expandedDetail.status === 'error' ? (
                        <p className="text-sm text-destructive font-medium">
                          {expandedDetail.error_message || 'An error occurred during scraping.'}
                        </p>
                      ) : (
                        <div className="rounded-lg bg-muted/50 border">
                          <pre className="text-xs text-foreground whitespace-pre-wrap break-words max-h-96 overflow-y-auto font-mono leading-relaxed p-3">
                            {expandedDetail.content || '(No content)'}
                          </pre>
                        </div>
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
                </div>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
