import { Flow } from '@/components/flow';
import { useFlowContext } from '@/contexts/flow-context';
import { useTabsContext } from '@/contexts/tabs-context';
import { cn } from '@/lib/utils';
import { flowService } from '@/services/flow-service';
import { Flow as FlowType } from '@/types/flow';
import { useEffect } from 'react';

interface FlowTabContentProps {
  flow: FlowType;
  className?: string;
}

export function FlowTabContent({ flow, className }: FlowTabContentProps) {
  const { loadFlow } = useFlowContext();
  const { activeTabId } = useTabsContext();

  // Fetch the latest flow state when this tab becomes active
  useEffect(() => {
    const isThisTabActive = activeTabId === `flow-${flow.id}`;
    
    if (isThisTabActive) {
      const fetchAndLoadFlow = async () => {
        try {
          // Fetch the latest flow data from the backend
          const latestFlow = await flowService.getFlow(flow.id);
          // Load the fresh flow data
          await loadFlow(latestFlow);
        } catch (error) {
          console.error('Failed to fetch latest flow state:', error);
          // Fallback to loading the cached flow data
          await loadFlow(flow);
        }
      };

      fetchAndLoadFlow();
    }
  }, [activeTabId, flow.id, flow, loadFlow]);

  return (
    <div className={cn("h-full w-full", className)}>
      <Flow />
    </div>
  );
} 