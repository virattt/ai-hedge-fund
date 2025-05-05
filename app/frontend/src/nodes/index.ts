import { Position, type NodeTypes } from '@xyflow/react';

import { AgentNode } from './AgentNode';
import { PositionLoggerNode } from './PositionLoggerNode';
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
    data: { agent_name: 'Warren Buffett', agent_id: 'warren_buffett' },
  },
  {
    id: 'c',
    type: 'agent',
    position: { x: 400, y: 0 },
    data: { agent_name: 'Portfolio Manager', agent_id: 'portfolio_manager' },
  },
];

export const nodeTypes = {
  'position-logger': PositionLoggerNode,
  'agent': AgentNode,
  // Add any of your custom nodes here!
} satisfies NodeTypes;
