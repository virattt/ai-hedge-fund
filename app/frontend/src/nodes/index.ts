import { Position, type NodeTypes } from '@xyflow/react';

import { AgentNode } from './agent-node';
import { AppNode } from './types';

export const initialNodes: AppNode[] = [
  {
    id: 'a',
    type: 'input',
    position: { x: 0, y: 0 },
    data: { label: 'Input' },
    sourcePosition: Position.Right
  },
  {
    id: 'b',
    type: 'agent',
    position: { x: 200, y: 0 },
    data: {
      id: 'warren_buffett',
      name: 'Warren Buffett',
      description: 'The Oracle of Omaha',
      status: 'Idle'
    },
  },
  {
    id: 'c',
    type: 'agent',
    position: { x: 500, y: 0 },
    data: {
      id: 'portfolio_manager',
      name: 'Portfolio Manager',
      description: 'The Decision Maker',
      status: 'Idle'
    },
  },
];

export const nodeTypes = {
  'agent': AgentNode,
  // Add any of your custom nodes here!
} satisfies NodeTypes;
