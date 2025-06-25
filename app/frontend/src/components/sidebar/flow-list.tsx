import { Accordion } from '@/components/ui/accordion';
import { useFlowContext } from '@/contexts/flow-context';
import { Flow } from '@/types/flow';
import { FolderOpen } from 'lucide-react';
import { FlowItemGroup } from './flow-item-group';
import { SearchBox } from './search-box';

interface FlowListProps {
  flows: Flow[];
  searchQuery: string;
  isLoading: boolean;
  openGroups: string[];
  filteredFlows: Flow[];
  recentFlows: Flow[];
  templateFlows: Flow[];
  onSearchChange: (query: string) => void;
  onAccordionChange: (value: string[]) => void;
  onLoadFlow: (flow: Flow) => Promise<void>;
  onDeleteFlow: (flow: Flow) => Promise<void>;
  onRefresh: () => Promise<void>;
}

export function FlowList({
  flows,
  searchQuery,
  isLoading,
  openGroups,
  filteredFlows,
  recentFlows,
  templateFlows,
  onSearchChange,
  onAccordionChange,
  onLoadFlow,
  onDeleteFlow,
  onRefresh,
}: FlowListProps) {
  const { currentFlowId } = useFlowContext();

  return (
    <div className="flex-grow overflow-auto text-white scrollbar-thin scrollbar-thumb-ramp-grey-700">
      <SearchBox 
        value={searchQuery} 
        onChange={onSearchChange}
        placeholder="Search flows..."
      />
      
      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <div className="text-gray-400 text-sm">Loading flows...</div>
        </div>
      ) : (
        <Accordion 
          type="multiple" 
          className="w-full" 
          value={openGroups} 
          onValueChange={onAccordionChange}
        >
          {recentFlows.length > 0 && (
            <FlowItemGroup
              key="recent-flows"
              title="Recent Flows"
              flows={recentFlows}
              onLoadFlow={onLoadFlow}
              onDeleteFlow={onDeleteFlow}
              onRefresh={onRefresh}
              currentFlowId={currentFlowId}
            />
          )}
          
          {templateFlows.length > 0 && (
            <FlowItemGroup
              key="templates"
              title="Templates"
              flows={templateFlows}
              onLoadFlow={onLoadFlow}
              onDeleteFlow={onDeleteFlow}
              onRefresh={onRefresh}
              currentFlowId={currentFlowId}
            />
          )}
        </Accordion>
      )}

      {!isLoading && filteredFlows.length === 0 && (
        <div className="text-center py-8 text-gray-400 text-sm">
          {flows.length === 0 ? (
            <div className="space-y-2">
              <FolderOpen size={32} className="mx-auto text-gray-500" />
              <div>No flows saved yet</div>
              <div className="text-xs">Create your first flow to get started</div>
            </div>
          ) : (
            'No flows match your search'
          )}
        </div>
      )}
    </div>
  );
} 