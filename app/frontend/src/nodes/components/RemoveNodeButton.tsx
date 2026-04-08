import { useReactFlow } from '@xyflow/react';
import { X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export interface RemoveNodeButtonProps {
  nodeId: string;
  onRemove?: () => void;
  className?: string;
}

export function RemoveNodeButton({ nodeId, onRemove, className }: RemoveNodeButtonProps) {
  const { deleteElements } = useReactFlow();

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onRemove) {
      onRemove();
    } else {
      deleteElements({ nodes: [{ id: nodeId }] });
    }
  };

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          size="icon"
          variant="ghost"
          className={cn(
            'absolute top-2 right-2 z-20 h-6 w-6 opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity',
            className
          )}
          onClick={handleClick}
          aria-label="Remove node"
        >
          <X className="h-3 w-3" />
        </Button>
      </TooltipTrigger>
      <TooltipContent side="top">Remove node</TooltipContent>
    </Tooltip>
  );
}
