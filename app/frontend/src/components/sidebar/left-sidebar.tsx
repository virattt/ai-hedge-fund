import { useFlowManagement } from '@/hooks/use-flow-management';
import { useResizable } from '@/hooks/use-resizable';
import { cn } from '@/lib/utils';
import { ReactNode } from 'react';
import { FlowActions } from './flow-actions';
import { FlowCreateDialog } from './flow-create-dialog';
import { FlowList } from './flow-list';

interface LeftSidebarProps {
  children?: ReactNode;
  isCollapsed: boolean;
  onCollapse: () => void;
  onExpand: () => void;
  onToggleCollapse: () => void;
}

export function LeftSidebar({
  isCollapsed,
  onToggleCollapse,
}: LeftSidebarProps) {
  // Use our custom hooks
  const { width, isDragging, elementRef, startResize } = useResizable({
    defaultWidth: 280,
    minWidth: 200,
    maxWidth: 500,
    side: 'left',
  });
  
  // Use flow management hook
  const {
    flows,
    searchQuery,
    isLoading,
    openGroups,
    createDialogOpen,
    filteredFlows,
    recentFlows,
    templateFlows,
    setSearchQuery,
    setCreateDialogOpen,
    handleAccordionChange,
    handleCreateNewFlow,
    handleFlowCreated,
    handleSaveCurrentFlow,
    handleLoadFlow,
    handleDeleteFlow,
    handleRefresh,
  } = useFlowManagement();

  return (
    <div 
      ref={elementRef}
      className={cn(
        "h-full bg-panel flex flex-col relative",
        isCollapsed ? "shadow-lg" : "",
        isDragging ? "select-none" : ""
      )}
      style={{ 
        width: `${width}px`,
        borderRight: isDragging ? 'none' : '1px solid var(--ramp-grey-900)' 
      }}
    >
      <FlowActions
        onSave={handleSaveCurrentFlow}
        onCreate={handleCreateNewFlow}
        onToggleCollapse={onToggleCollapse}
      />
      
      <FlowList
        flows={flows}
        searchQuery={searchQuery}
        isLoading={isLoading}
        openGroups={openGroups}
        filteredFlows={filteredFlows}
        recentFlows={recentFlows}
        templateFlows={templateFlows}
        onSearchChange={setSearchQuery}
        onAccordionChange={handleAccordionChange}
        onLoadFlow={handleLoadFlow}
        onDeleteFlow={handleDeleteFlow}
        onRefresh={handleRefresh}
      />
      
      {/* Resize handle - on the right side for left sidebar */}
      {!isDragging && (
        <div 
          className="absolute top-0 right-0 h-full w-1 cursor-ew-resize transition-all duration-150 z-10"
          onMouseDown={startResize}
        />
      )}

      <FlowCreateDialog
        isOpen={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onFlowCreated={handleFlowCreated}
      />
    </div>
  );
} 