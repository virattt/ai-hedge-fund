import { Handle, Position, type NodeProps } from '@xyflow/react';

import { type AgentNode } from './types';

export function AgentNode({
  data,
}: NodeProps<AgentNode>) {
  return (
    <div className="react-flow__node-default">
      <Handle
        type="target"
        position={Position.Left}
      />
      {data.agent_name && <div>{data.agent_name}</div>}

      <Handle type="source" position={Position.Right} />
    </div>
  );
}
