import { useTabsContext } from '@/contexts/tabs-context';
import { useI18n } from '@/i18n/use-i18n';
import { cn, formatKeyboardShortcut } from '@/lib/utils';
import { TabService } from '@/services/tab-service';
import { FileText, FolderOpen } from 'lucide-react';
import { useEffect } from 'react';

interface TabContentProps {
  className?: string;
}

export function TabContent({ className }: TabContentProps) {
  const { tabs, activeTabId, openTab } = useTabsContext();
  const { t } = useI18n();

  const activeTab = tabs.find(tab => tab.id === activeTabId);
  const activeTabTitle = activeTab?.type === 'settings' ? t('settings.title') : activeTab?.title;

  // Restore content for tabs that don't have it (from localStorage restoration)
  useEffect(() => {
    if (activeTab && !activeTab.content) {
      try {
        const restoredTab = TabService.restoreTab({
          type: activeTab.type,
          title: activeTab.title,
          flow: activeTab.flow,
          metadata: activeTab.metadata,
        });

        // Update the tab with restored content
        openTab({
          id: activeTab.id,
          type: restoredTab.type,
          title: restoredTab.title,
          content: restoredTab.content,
          flow: restoredTab.flow,
          metadata: restoredTab.metadata,
        });
      } catch (error) {
        console.error('Failed to restore tab content:', error);
      }
    }
  }, [activeTab, openTab]);

  if (!activeTab) {
    return (
      <div className={cn(
        "h-full w-full flex items-center justify-center bg-background text-muted-foreground",
        className
      )}>
        <div className="text-center space-y-4">
          <FolderOpen size={48} className="mx-auto text-muted-foreground/50" />
          <div>
            <div className="text-xl font-medium mb-2">{t('tabs.welcomeTitle')}</div>
            <div className="text-sm max-w-md">
              {t('tabs.welcomeDescription', {
                shortcut: formatKeyboardShortcut('B'),
                settingsShortcut: '⌘,',
              })}
            </div>
          </div>
          <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground/70">
            <FileText size={14} />
            <span>{t('tabs.flowsOpenInTabs')}</span>
          </div>
        </div>
      </div>
    );
  }

  // Show loading state if content is being restored
  if (!activeTab.content) {
    return (
      <div className={cn(
        "h-full w-full flex items-center justify-center bg-background text-muted-foreground",
        className
      )}>
        <div className="text-center">
          <div className="text-lg font-medium mb-2">{t('tabs.loading', { title: activeTabTitle || '' })}</div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("h-full w-full bg-background overflow-hidden", className)}>
      {activeTab.content}
    </div>
  );
}
