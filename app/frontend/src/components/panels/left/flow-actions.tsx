import { Button } from '@/components/ui/button';
import { useFlowContext } from '@/contexts/flow-context';
import { cn } from '@/lib/utils';
import { Plus, Save } from 'lucide-react';

interface FlowActionsProps {
  onSave: () => Promise<void>;
  onCreate: () => void;
  onToggleCollapse: () => void;
}

export function FlowActions({ onSave, onCreate, onToggleCollapse }: FlowActionsProps) {
  const { currentFlowName, isUnsaved } = useFlowContext();

  return (
    <div className="p-2 flex justify-between flex-shrink-0 items-center border-b border-ramp-grey-700 mt-4">
      <span className="text-white text-sm font-medium ml-4">
        Flows
        {isUnsaved && <span className="text-yellow-400 ml-1">*</span>}
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          onClick={onSave}
          className={cn(
            "h-6 w-6 text-white hover:bg-ramp-grey-700",
            isUnsaved && "text-yellow-400"
          )}
          title={`Save "${currentFlowName}"`}
        >
          <Save size={14} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onCreate}
          className="h-6 w-6 text-white hover:bg-ramp-grey-700"
          title="Create new flow"
        >
          <Plus size={14} />
        </Button>
      </div>
    </div>
  );
} 