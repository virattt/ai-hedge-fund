import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { useToastManager } from '@/hooks/use-toast-manager';
import { scrapingService, Website } from '@/services/scraping-api';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useEffect, useState } from 'react';

const INTERVAL_OPTIONS = [
  { label: 'No scheduled scraping', value: null },
  { label: 'Every 15 minutes', value: 15 },
  { label: 'Every hour', value: 60 },
  { label: 'Every 6 hours', value: 360 },
  { label: 'Every 24 hours', value: 1440 },
];

interface AddWebsiteDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onWebsiteAdded: (website: Website) => void;
  editingWebsite?: Website;
}

export function AddWebsiteDialog({ isOpen, onClose, onWebsiteAdded, editingWebsite }: AddWebsiteDialogProps) {
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [intervalMinutes, setIntervalMinutes] = useState<number | null>(null);
  const [maxDepth, setMaxDepth] = useState(1);
  const [maxPages, setMaxPages] = useState(10);
  const [includeExternal, setIncludeExternal] = useState(false);
  const [crawlSettingsOpen, setCrawlSettingsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const { success, error } = useToastManager();

  const isEditMode = !!editingWebsite;

  useEffect(() => {
    if (isOpen) {
      if (editingWebsite) {
        setUrl(editingWebsite.url);
        setName(editingWebsite.name);
        setIntervalMinutes(editingWebsite.scrape_interval_minutes ?? null);
        setMaxDepth(editingWebsite.max_depth);
        setMaxPages(editingWebsite.max_pages);
        setIncludeExternal(editingWebsite.include_external);
        setCrawlSettingsOpen(editingWebsite.max_depth > 1);
      } else {
        setUrl('');
        setName('');
        setIntervalMinutes(null);
        setMaxDepth(1);
        setMaxPages(10);
        setIncludeExternal(false);
        setCrawlSettingsOpen(false);
      }
    }
  }, [isOpen, editingWebsite]);

  const handleSubmit = async () => {
    if (!url.trim()) {
      error('URL is required');
      return;
    }
    if (!name.trim()) {
      error('Name is required');
      return;
    }

    setIsLoading(true);
    try {
      let website: Website;
      if (isEditMode) {
        website = await scrapingService.updateWebsite(editingWebsite.id, {
          name: name.trim(),
          scrape_interval_minutes: intervalMinutes,
          max_depth: maxDepth,
          max_pages: maxPages,
          include_external: includeExternal,
        });
        success(`"${website.name}" updated`);
      } else {
        website = await scrapingService.createWebsite({
          url: url.trim(),
          name: name.trim(),
          scrape_interval_minutes: intervalMinutes,
          max_depth: maxDepth,
          max_pages: maxPages,
          include_external: includeExternal,
        });
        success(`"${website.name}" added`);
      }
      onWebsiteAdded(website);
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : `Failed to ${isEditMode ? 'update' : 'add'} website`;
      error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (url.trim() && name.trim()) {
        handleSubmit();
      }
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>{isEditMode ? 'Edit Website' : 'Add Website'}</DialogTitle>
          <DialogDescription>
            {isEditMode
              ? 'Update website settings and crawl configuration.'
              : 'Add a website to scrape. Public URLs only (no private IPs or localhost).'}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <label htmlFor="website-url" className="text-sm font-medium">
              URL <span className="text-destructive">*</span>
            </label>
            <Input
              id="website-url"
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="https://example.com"
              autoFocus={!isEditMode}
              disabled={isEditMode}
            />
          </div>

          <div className="grid gap-2">
            <label htmlFor="website-name" className="text-sm font-medium">
              Name <span className="text-destructive">*</span>
            </label>
            <Input
              id="website-name"
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="My Website"
            />
          </div>

          <div className="grid gap-2">
            <label htmlFor="website-interval" className="text-sm font-medium">
              Scrape Interval
            </label>
            <select
              id="website-interval"
              value={intervalMinutes === null ? '' : String(intervalMinutes)}
              onChange={e => setIntervalMinutes(e.target.value === '' ? null : Number(e.target.value))}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {INTERVAL_OPTIONS.map(opt => (
                <option key={String(opt.value)} value={opt.value === null ? '' : String(opt.value)}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Collapsible Crawl Settings */}
          <div className="border rounded-md">
            <button
              type="button"
              className="flex items-center justify-between w-full px-3 py-2 text-sm font-medium hover:bg-accent/50 rounded-md"
              onClick={() => setCrawlSettingsOpen(!crawlSettingsOpen)}
            >
              <span>Crawl Settings</span>
              {crawlSettingsOpen
                ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </button>
            {crawlSettingsOpen && (
              <div className="px-3 pb-3 grid gap-3">
                <div className="grid gap-1">
                  <label htmlFor="max-depth" className="text-xs font-medium">
                    Max Depth
                  </label>
                  <Input
                    id="max-depth"
                    type="number"
                    min={1}
                    max={5}
                    value={maxDepth}
                    onChange={e => setMaxDepth(Math.min(5, Math.max(1, Number(e.target.value) || 1)))}
                  />
                  <p className="text-xs text-muted-foreground">1 = main page only</p>
                </div>
                <div className="grid gap-1">
                  <label htmlFor="max-pages" className="text-xs font-medium">
                    Max Pages
                  </label>
                  <Input
                    id="max-pages"
                    type="number"
                    min={1}
                    max={100}
                    value={maxPages}
                    onChange={e => setMaxPages(Math.min(100, Math.max(1, Number(e.target.value) || 1)))}
                  />
                  <p className="text-xs text-muted-foreground">Maximum pages per run</p>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    id="include-external"
                    type="checkbox"
                    checked={includeExternal}
                    onChange={e => setIncludeExternal(e.target.checked)}
                    className="h-4 w-4 rounded border-input"
                  />
                  <label htmlFor="include-external" className="text-xs font-medium">
                    Include external links
                  </label>
                </div>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isLoading || !url.trim() || !name.trim()}>
            {isLoading ? (isEditMode ? 'Saving...' : 'Adding...') : (isEditMode ? 'Save Changes' : 'Add Website')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
