import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useFlowConnectionState } from '@/hooks/use-flow-connection';
import { cn } from '@/lib/utils';
import { flowService } from '@/services/flow-service';
import { Flow } from '@/types/flow';
import {
  Calendar,
  FileText,
  Layout,
  MoreHorizontal,
  Zap
} from 'lucide-react';
import { useState } from 'react';
import { FlowContextMenu } from './flow-context-menu';
import { FlowEditDialog } from './flow-edit-dialog';

interface FlowItemProps {
  flow: Flow;
  onLoadFlow: (flow: Flow) => Promise<void>;
  onDeleteFlow: (flow: Flow) => Promise<void>;
  onRefresh: () => Promise<void>;
  isActive?: boolean;
}

export default function FlowItem({ flow, onLoadFlow, onDeleteFlow, onRefresh, isActive = false }: FlowItemProps) {
  const [contextMenu, setContextMenu] = useState<{ isOpen: boolean; position: { x: number; y: number } }>({
    isOpen: false,
    position: { x: 0, y: 0 }
  });
  const [editDialog, setEditDialog] = useState(false);

  // Check if this flow has an active connection
  const connectionState = useFlowConnectionState(flow.id.toString());
  const hasActiveConnection = connectionState && 
    (connectionState.state === 'connecting' || connectionState.state === 'connected');

  const handleLoadFlow = async () => {
    await onLoadFlow(flow);
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    setContextMenu({
      isOpen: true,
      position: { x: e.clientX, y: e.clientY }
    });
  };

  const handleMenuClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    
    // Get the button's position for the menu
    const rect = e.currentTarget.getBoundingClientRect();
    setContextMenu({
      isOpen: true,
      position: { x: rect.right - 160, y: rect.bottom } // Offset menu to the left of the button
    });
  };

  const closeContextMenu = () => {
    setContextMenu(prev => ({ ...prev, isOpen: false }));
  };

  const handleEdit = () => {
    setEditDialog(true);
  };

  const handleDuplicateFlow = async () => {
    try {
      await flowService.duplicateFlow(flow.id);
      onRefresh();
    } catch (error) {
      console.error('Failed to duplicate flow:', error);
    }
  };

  const handleDeleteFlow = async () => {
    if (window.confirm(`Are you sure you want to delete "${flow.name}"?`)) {
      try {
        await onDeleteFlow(flow);
      } catch (error) {
        console.error('Failed to delete flow:', error);
      }
    }
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  };

  // Filter out "default" tag
  const filteredTags = flow.tags?.filter(tag => tag !== 'default') || [];

  return (
    <>
      <div 
        className={cn(
          "group flex items-center justify-between px-4 py-3 transition-colors cursor-pointer",
          isActive 
            ? "border-l-2 border-blue-400" 
            : "hover:bg-ramp-grey-700"
        )}
        onClick={handleLoadFlow}
        onContextMenu={handleContextMenu}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="flex items-center gap-1 min-w-0">
              {flow.is_template ? (
                <Layout size={14} className="text-blue-400 flex-shrink-0" />
              ) : (
                <FileText size={14} className={cn(
                  "flex-shrink-0",
                  isActive ? "text-blue-400" : "text-gray-400"
                )} />
              )}
              <span
                className={cn(
                  "text-subtitle font-medium text-left truncate",
                  isActive 
                    ? "text-blue-300" 
                    : "text-white"
                )}
                title={flow.name}
              >
                {flow.name}
              </span>
            </div>
            
            {/* Active connection indicator - right aligned */}
            {hasActiveConnection && (
              <div className="flex items-center gap-1 flex-shrink-0">
                <Zap className="h-3 w-3 text-yellow-400 animate-pulse" />
                <span className="text-xs text-yellow-400 font-medium">Running</span>
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Calendar size={10} />
            <span>{formatDateTime(flow.created_at)}</span>
          </div>
          
          {filteredTags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {filteredTags.slice(0, 2).map(tag => (
                <Badge key={tag} variant="secondary" className="text-xs px-1 py-0">
                  {tag}
                </Badge>
              ))}
              {filteredTags.length > 2 && (
                <Badge variant="secondary" className="text-xs px-1 py-0">
                  +{filteredTags.length - 2}
                </Badge>
              )}
            </div>
          )}
        </div>
        
        <div className="flex items-center">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleMenuClick}
            className="h-6 w-6 text-gray-400 hover:text-white hover:bg-ramp-grey-600 opacity-0 group-hover:opacity-100 transition-opacity"
            title="More options"
          >
            <MoreHorizontal size={14} />
          </Button>
        </div>
      </div>

      <FlowContextMenu
        isOpen={contextMenu.isOpen}
        position={contextMenu.position}
        onClose={closeContextMenu}
        onEdit={handleEdit}
        onDuplicate={handleDuplicateFlow}
        onDelete={handleDeleteFlow}
      />

      <FlowEditDialog
        flow={flow}
        isOpen={editDialog}
        onClose={() => setEditDialog(false)}
        onFlowUpdated={onRefresh}
      />
    </>
  );
} 