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
}

export function AddWebsiteDialog({ isOpen, onClose, onWebsiteAdded }: AddWebsiteDialogProps) {
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [intervalMinutes, setIntervalMinutes] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { success, error } = useToastManager();

  useEffect(() => {
    if (isOpen) {
      setUrl('');
      setName('');
      setIntervalMinutes(null);
    }
  }, [isOpen]);

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
      const website = await scrapingService.createWebsite({
        url: url.trim(),
        name: name.trim(),
        scrape_interval_minutes: intervalMinutes,
      });
      success(`"${website.name}" added`);
      onWebsiteAdded(website);
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add website';
      error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    setUrl('');
    setName('');
    setIntervalMinutes(null);
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
          <DialogTitle>Add Website</DialogTitle>
          <DialogDescription>
            Add a website to scrape. Public URLs only (no private IPs or localhost).
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
              autoFocus
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
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isLoading || !url.trim() || !name.trim()}>
            {isLoading ? 'Adding...' : 'Add Website'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
