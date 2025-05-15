import { type NodeTypes, Edge, MarkerType } from '@xyflow/react';

import { AgentNode } from './components/agent-node';
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
  {
    id: 'text-output-node',
    type: 'output-node',
    position: { x: 600, y: 0 },
    data: {
      name: 'Output',
      description: 'Output Node',
      status: 'Idle',
    },
  },
  {
    id: 'warren_buffett',
    type: 'agent-node',
    position: { x: 300, y: 0 },
    data: {
      name: 'Warren Buffett',
      description: 'The Oracle of Omaha',
      status: 'Idle',
    },
  },
];

// TODO (virat) temporary, delete after testing
export const initialEdges: Edge[] = [
  {
    id: 'start-to-warren',
    source: 'text-input-node',
    target: 'warren_buffett',
    markerEnd: {
      type: MarkerType.ArrowClosed,
    },
  },
  {
    id: 'warren-to-output',
    source: 'warren_buffett',
    target: 'text-output-node',
    markerEnd: {
      type: MarkerType.ArrowClosed,
    },
  },
];

export const nodeTypes = {
  'agent-node': AgentNode,
  'input-node': TextInputNode,
  'output-node': TextOutputNode,
} satisfies NodeTypes;
