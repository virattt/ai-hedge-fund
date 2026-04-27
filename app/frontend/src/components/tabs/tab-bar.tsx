import { Button } from '@/components/ui/button';
import { useTabsContext } from '@/contexts/tabs-context';
import { cn } from '@/lib/utils';
import { FileText, Layout, Settings, X } from 'lucide-react';
import { ReactNode, useState } from 'react';

interface TabBarProps {
  className?: string;
}

// Get icon for tab type
const getTabIcon = (type: string): ReactNode => {
  switch (type) {
    case 'flow':
      return <FileText size={13} />;
    case 'settings':
      return <Settings size={13} />;
    default:
      return <Layout size={13} />;
  }
};

export function TabBar({ className }: TabBarProps) {
  const { tabs, activeTabId, setActiveTab, closeTab, reorderTabs } = useTabsContext();
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  if (tabs.length === 0) {
    return null;
  }

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', ''); // Required for some browsers
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    
    if (draggedIndex !== null && draggedIndex !== index) {
      setDragOverIndex(index);
    }
  };

  const handleDragLeave = () => {
    setDragOverIndex(null);
  };

  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    
    if (draggedIndex !== null && draggedIndex !== dropIndex) {
      reorderTabs(draggedIndex, dropIndex);
    }
    
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  return (
    <div className={cn(
      "flex items-center bg-panel border-b overflow-x-auto",
      className
    )}>
      <div className="flex items-center min-w-0">
        {tabs.map((tab, index) => (
          <div
            key={tab.id}
            draggable
            onDragStart={(e) => handleDragStart(e, index)}
            onDragOver={(e) => handleDragOver(e, index)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, index)}
            onDragEnd={handleDragEnd}
            className={cn(
              "group relative flex items-center gap-2 px-4 py-2.5 cursor-pointer transition-all duration-150 min-w-0 max-w-52 select-none last:border-r-0",
              // Active tab styling - VSCode style
              activeTabId === tab.id 
                ? "bg-panel before:absolute before:bottom-0 before:left-0 before:right-0 before:h-0.5 before:content-['']" 
                : "bg-panel hover:bg-[var(--tab-hover-background)]",
              // Drag states
              draggedIndex === index && "opacity-60 scale-[0.98]",
              dragOverIndex === index && "ring-1 ring-[var(--tab-accent)]/30",
              "hover:cursor-grab active:cursor-grabbing"
            )}
            style={{
              borderRight: `1px solid var(--tab-border)`,
              color: activeTabId === tab.id ? 'var(--tab-active-text)' : 'var(--tab-inactive-text)',
              backgroundColor: dragOverIndex === index ? 'var(--tab-hover-background)' : undefined,
            }}
            onMouseEnter={(e) => {
              if (activeTabId !== tab.id) {
                e.currentTarget.style.color = 'var(--tab-hover-text)';
              }
            }}
            onMouseLeave={(e) => {
              if (activeTabId !== tab.id) {
                e.currentTarget.style.color = 'var(--tab-inactive-text)';
              }
            }}
            onClick={() => setActiveTab(tab.id)}
          >
            {/* Active tab accent bar */}
            {activeTabId === tab.id && (
              <div 
                className="absolute bottom-0 left-0 right-0 h-0.5"
                style={{ backgroundColor: 'var(--tab-accent)' }}
              />
            )}

            {/* Tab Icon */}
            <div className={cn(
              "flex-shrink-0 transition-colors duration-150",
              activeTabId === tab.id ? "text-primary" : ""
            )}
            style={{
              color: activeTabId === tab.id ? 'var(--tab-icon-active)' : 'var(--tab-icon-inactive)'
            }}>
              {getTabIcon(tab.type)}
            </div>

            {/* Tab Title */}
            <span className={cn(
              "text-[13px] font-normal truncate min-w-0 transition-colors duration-150"
            )}>
              {tab.title}
            </span>

            {/* Close Button */}
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                "h-5 w-5 p-0 flex-shrink-0 ml-1 rounded-sm transition-all duration-150",
                "opacity-0 group-hover:opacity-100 focus:opacity-100 focus:outline-none",
                activeTabId === tab.id && "opacity-70 hover:opacity-100"
              )}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--tab-close-hover)';
                e.currentTarget.style.color = 'var(--tab-hover-text)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.color = 'inherit';
              }}
              onClick={(e) => {
                e.stopPropagation();
                closeTab(tab.id);
              }}
              onMouseDown={(e) => e.stopPropagation()} // Prevent drag when clicking close button
              title="Close tab"
            >
              <X size={11} className="transition-transform duration-150 hover:scale-110" />
            </Button>

            {/* Modified indicator dot for unsaved changes - VSCode style */}
            {/* You can add this when you implement unsaved changes tracking */}
            {/* <div className="absolute top-1/2 left-1 w-1.5 h-1.5 rounded-full transform -translate-y-1/2" style={{ backgroundColor: 'var(--tab-active-text)' }} /> */}
          </div>
        ))}
      </div>
    </div>
  );
} 