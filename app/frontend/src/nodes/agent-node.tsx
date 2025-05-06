import { cn } from '@/lib/utils';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Bot } from 'lucide-react';

import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { type AgentNode } from './types';

export function AgentNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<AgentNode>) {
  return (
    <div
      className={cn(
        "react-flow__node-default relative w-64 select-none cursor-pointer p-0 rounded-lg border transition-all duration-200 hover:border-primary hover:shadow-[0_0_10px_1px_rgba(255,255,255,0.1)]",
        selected && "ring-1 ring-primary dark:ring-offset-background"
      )}
      data-id={id}
      data-nodeid={id}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 rounded-full bg-gray-500 border-2 border-card absolute left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 transition-all duration-200 hover:bg-gray-500 hover:w-4 hover:h-4 hover:shadow-[0_0_5px_2px_rgba(59,130,246,0.3)]"
        isConnectable={isConnectable}
      />
      <div className="overflow-hidden rounded-lg">
        <Card className="bg-card rounded-none overflow-hidden border-none">
          <CardHeader className="p-3 bg-secondary flex flex-row items-center space-x-2 rounded-t-sm">
            <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-chart-1 text-white">
              <Bot className="h-5 w-5" />
            </div>
            <div className="text-title font-semibold text-primary">
              {data.name || "Custom Component"}
            </div>
          </CardHeader>

          <div className="px-3 py-2 text-subtitle text-muted-foreground">
            {data.description}
          </div>

          <CardContent className="p-0">
            <div className="border-t border-border p-3">
              <div className="flex flex-col gap-2">
                <div className="text-subtitle text-muted-foreground flex items-center gap-1">
                  Status
                </div>

                <div className="bg-secondary text-foreground text-xs rounded p-2">
                  Idle
                </div>
              </div>
            </div>

            <div className="border-t border-border p-3 flex justify-end items-center">
              <div className="flex items-center gap-1">
                <div className="text-subtitle text-muted-foreground">Output</div>
                <div className="text-subtitle text-muted-foreground">≡</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Output Handle - Position it outside the overflow hidden container */}
      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 rounded-full bg-gray-500 border-2 border-card absolute right-0 top-1/2 translate-x-1/2 -translate-y-1/2 z-10 transition-all duration-200 hover:bg-gray-500 hover:w-4 hover:h-4 hover:shadow-[0_0_5px_2px_rgba(59,130,246,0.3)]"
        isConnectable={isConnectable}
      />
    </div>
  );
}
