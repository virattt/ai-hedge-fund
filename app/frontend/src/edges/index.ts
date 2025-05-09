import type { Edge, EdgeTypes } from '@xyflow/react';

export const initialEdges: Edge[] = [
  { id: 'start->warren_buffett', source: 'start', target: 'warren_buffett', animated: false },
  { id: 'warren_buffett->portfolio_manager', source: 'warren_buffett', target: 'portfolio_manager', animated: false },
];

export const edgeTypes = {
  // Add your custom edge types here!
} satisfies EdgeTypes;
