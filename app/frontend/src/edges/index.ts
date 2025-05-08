import type { Edge, EdgeTypes } from '@xyflow/react';

export const initialEdges: Edge[] = [
  { id: 'a->b', source: 'a', target: 'b', animated: false },
  { id: 'b->c', source: 'b', target: 'c', animated: false },
];

export const edgeTypes = {
  // Add your custom edge types here!
} satisfies EdgeTypes;
