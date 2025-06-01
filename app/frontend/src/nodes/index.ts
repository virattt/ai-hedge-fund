import { type NodeTypes } from '@xyflow/react';

import { AgentNode } from './components/agent-node';
import { JsonOutputNode } from './components/json-output-node';
import { TextInputNode } from './components/text-input-node';
import { TextOutputNode } from './components/text-output-node';
import { type AppNode } from './types';

// Types
export * from './types';

export const initialNodes: AppNode[] = [
  {
    id: 'text-input-node',
    type: 'input-node',
    position: { x: 0, y: 0 },
    data: {
      name: 'Input',
      description: 'Start Node',
      status: 'Idle',
    },
  },
];

export const nodeTypes = {
  'agent-node': AgentNode,
  'input-node': TextInputNode,
  'text-output-node': TextOutputNode,
  'json-output-node': JsonOutputNode,
} satisfies NodeTypes;
