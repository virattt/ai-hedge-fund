import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { AddWebsiteDialog } from '@/components/scraping/add-website-dialog';
import { ScrapeResultsPanel } from '@/components/scraping/scrape-results-panel';
import { WebsiteList } from '@/components/scraping/website-list';
import { Website } from '@/services/scraping-api';
import { Plus } from 'lucide-react';
import { useState } from 'react';

export function ScrapingResultsPage() {
  const [selectedWebsite, setSelectedWebsite] = useState<Website | null>(null);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [editingWebsite, setEditingWebsite] = useState<Website | undefined>(undefined);
  const [listKey, setListKey] = useState(0);

  const handleWebsiteAdded = (website: Website) => {
    setListKey(k => k + 1);
    setSelectedWebsite(website);
  };

  const handleListChange = () => {
    if (selectedWebsite) {
      setSelectedWebsite(null);
    }
  };

  const handleEdit = (website: Website) => {
    setEditingWebsite(website);
    setIsAddDialogOpen(true);
  };

  const handleDialogClose = () => {
    setIsAddDialogOpen(false);
    setEditingWebsite(undefined);
  };

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      {/* Left column - website list */}
      <div className="w-80 shrink-0 flex flex-col border-r border-border">
        <div className="flex items-center justify-between px-4 py-3 shrink-0">
          <h2 className="text-sm font-semibold text-foreground">Websites</h2>
          <Button
            size="sm"
            variant="outline"
            className="h-7 gap-1 text-xs"
            onClick={() => setIsAddDialogOpen(true)}
          >
            <Plus className="h-3.5 w-3.5" />
            Add
          </Button>
        </div>
        <Separator />
        <div className="flex-1 overflow-y-auto p-3">
          <WebsiteList
            key={listKey}
            selectedWebsiteId={selectedWebsite?.id ?? null}
            onSelect={setSelectedWebsite}
            onListChange={handleListChange}
            onEdit={handleEdit}
          />
        </div>
      </div>

      {/* Right column - scrape results */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center px-4 py-3 shrink-0">
          <h2 className="text-sm font-semibold text-foreground">
            {selectedWebsite ? `Results: ${selectedWebsite.name}` : 'Scrape Results'}
          </h2>
        </div>
        <Separator />
        <div className="flex-1 overflow-hidden">
          <ScrapeResultsPanel selectedWebsite={selectedWebsite} />
        </div>
      </div>

      <AddWebsiteDialog
        isOpen={isAddDialogOpen}
        onClose={handleDialogClose}
        onWebsiteAdded={handleWebsiteAdded}
        editingWebsite={editingWebsite}
      />
    </div>
  );
}
