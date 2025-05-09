import { type NodeProps } from '@xyflow/react';
import { Bot } from 'lucide-react';

import { CardContent } from '@/components/ui/card';
import { useNodeStatus } from '@/contexts/node-status-context';
import { type AgentNode } from '../types';
import { getStatusColor } from '../utils';
import { NodeShell } from './node-shell';

export function AgentNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<AgentNode>) {
  const { nodeStates } = useNodeStatus();
  const status = nodeStates[id] || 'IDLE';

  return (
    <NodeShell
      id={id}
      selected={selected}
      isConnectable={isConnectable}
      icon={<Bot className="h-5 w-5" />}
      iconColor={getStatusColor(status)}
      name={data.name || "Agent"}
      description={data.description}
    >
      <CardContent className="p-0">
        <div className="border-t border-border p-3">
          <div className="flex flex-col gap-2">
            <div className="text-subtitle text-muted-foreground flex items-center gap-1">
              Status
            </div>

            <div className={`text-foreground text-xs rounded p-2 ${getStatusColor(status)}`}>
              {status}
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
    </NodeShell>
  );
}
